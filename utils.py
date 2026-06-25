"""Shared utilities for PadelLens — data loading, theming, helpers.

Kept deliberately small so the page files stay readable. Anything that's
called from more than one page lives here.
"""
import datetime
import os
import time
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

DATA_DIR = Path(__file__).parent / "data"

# Data colors — used for marks (bars, lines). These stay the same in both
# themes; only the *chrome* (backgrounds, text, gridlines) changes with mode.
BLUE = "#0EA5E9"
RED = "#EF4444"
GREEN = "#22C55E"
ORANGE = "#F97316"
GRAY = "#94A3B8"
INK = "#1F2937"
MUTED = "#6B7280"

SHOT_TYPES = ["forehand", "backhand", "smash", "volley", "bandeja"]


# ---------------------------------------------------------------------------
# Theme system — one dict per mode. Everything that changes between light and
# dark lives here, so pages just ask for get_theme()[...] instead of hardcoding.
# ---------------------------------------------------------------------------

THEMES = {
    "light": {
        "page": "#FFFFFF",     # app background
        "card": "#FFFFFF",     # card / chart background
        "sidebar": "#F6F8FA",  # sidebar background
        "border": "#CFD6DD",   # card borders
        "ink": "#1F2937",      # primary text
        "muted": "#6B7280",    # secondary text
        "grid": "#EEF0F3",     # chart gridlines
        "zero": "#7B8694",     # chart zero / divider lines
        "h2": "#2A3340",       # subheading color
        # semantic tints for the Compare page gap cards
        "bad_bg": "#FEF2F2", "bad_br": "#FECACA", "bad_fg": "#B91C1C",
        "warn_bg": "#FFF7ED", "warn_br": "#FED7AA", "warn_fg": "#C2410C",
        "good_bg": "#F0FDF4", "good_br": "#BBF7D0", "good_fg": "#15803D",
    },
    "dark": {
        "page": "#0E1117",
        "card": "#1B2129",
        "sidebar": "#161A21",
        "border": "#2A313C",
        "ink": "#E6EAF0",
        "muted": "#9BA4B0",
        "grid": "#262C36",
        "zero": "#4B5563",
        "h2": "#C5CDD8",
        "bad_bg": "#2A1416", "bad_br": "#5B2327", "bad_fg": "#F87171",
        "warn_bg": "#2A1D10", "warn_br": "#5B3D1F", "warn_fg": "#FB923C",
        "good_bg": "#102218", "good_br": "#1F4A31", "good_fg": "#4ADE80",
    },
}


def is_dark() -> bool:
    """True when the user has the dark-mode switch on (persists via session_state)."""
    return bool(st.session_state.get("dark_mode", False))


def get_theme() -> dict:
    """Return the active theme dict. Read this at the top of every page."""
    return THEMES["dark"] if is_dark() else THEMES["light"]


# ---------------------------------------------------------------------------
# Data loading (cached so reruns don't reread the CSVs)
# ---------------------------------------------------------------------------

@st.cache_data
def load_pro_players() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "pro_players.csv")


@st.cache_data
def load_pro_matches() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "pro_matches.csv")
    df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_data
def load_my_matches() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "my_matches.csv")
    df["date"] = pd.to_datetime(df["date"])
    df["won"] = df["result"] == "W"
    # Pre-compute per-shot net balance so charts don't have to.
    for s in SHOT_TYPES:
        df[f"net_{s}"] = df[f"winners_{s}"] - df[f"errors_{s}"]
    return df.sort_values("date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Live Pro Tour rankings — Padel API (https://padelapi.org)
#
# The rankings table is fetched live from the official Premier Padel / FIP feed
# so the app always shows the current week, for BOTH the men's and women's tour.
# Every successful fetch is written to a snapshot CSV in data/; that snapshot is
# the fallback used when the API is unreachable (no token, no network, rate
# limited) so the demo never breaks. This is the live path the README and
# 02_Data/api_client.py always referenced — now wired into the app.
# ---------------------------------------------------------------------------

PADEL_API_BASE = "https://padelapi.org/api"

# padelapi.org sits behind Cloudflare, which rejects the default python-requests
# user-agent with HTTP 403 (error 1010). A browser-like UA is required or every
# request fails — so it is not optional.
_PADEL_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# The API uses drive / backhand; the app already labels these Drive / Reves.
_SIDE_LABEL = {"drive": "Drive", "backhand": "Reves"}

RANKING_COLUMNS = ["ranking", "name", "nationality", "side",
                   "points", "ranking_diff", "points_diff", "date"]


def _padel_token():
    """Return the API token from st.secrets or the PADEL_API_TOKEN env var.

    Returns None when no real token is configured (e.g. the placeholder is still
    in secrets.toml), which sends the data layer down the offline-fallback path
    instead of raising.
    """
    placeholder = "PASTE_YOUR_TOKEN_HERE"
    try:
        tok = st.secrets.get("PADEL_API_TOKEN")
        if tok and tok != placeholder:
            return tok
    except Exception:
        pass  # no secrets.toml at all — fall through to the env var
    return os.environ.get("PADEL_API_TOKEN") or None


def _padel_get(path: str, params: dict) -> dict:
    """One authenticated GET against the Padel API. Raises on any failure.

    Retries once on a 429 (rate limit) or 5xx — the free tier allows 10
    requests/minute, so a cold page load that fans out a few pages can briefly
    trip it. One short backoff usually clears it; anything still failing raises
    and the caller falls back to its cached snapshot.
    """
    token = _padel_token()
    if not token:
        raise RuntimeError("PADEL_API_TOKEN not configured")
    headers = {"Authorization": f"Bearer {token}",
               "Accept": "application/json",
               "User-Agent": _PADEL_UA}
    for attempt in range(2):
        r = requests.get(f"{PADEL_API_BASE}{path}", params=params,
                         headers=headers, timeout=20)
        if r.status_code in (429, 500, 502, 503) and attempt == 0:
            time.sleep(5)
            continue
        r.raise_for_status()
        return r.json()


def _padel_paged(path: str, params: dict, want: int) -> list:
    """Collect up to `want` rows, following the API's `links.next` pages."""
    rows, page = [], 1
    while len(rows) < want:
        payload = _padel_get(path, {**params, "page": page})
        batch = payload.get("data", [])
        if not batch:
            break
        rows.extend(batch)
        if not (payload.get("links") or {}).get("next"):
            break
        page += 1
    return rows[:want]


def _fetch_rankings_live(category: str, top_n: int) -> pd.DataFrame:
    """Build the rankings table for one tour ('men' / 'women') from the API.

    Joins two endpoints on the player id: /rankings gives the ranked order,
    points and the weekly movement (points_diff / ranking_diff); /players adds
    the playing side. Pairs legitimately share a rank, exactly as on the
    official FIP site.
    """
    ranks = _padel_paged("/rankings",
                         {"type": "official", "category": category}, top_n)
    players = _padel_paged("/players",
                          {"category": category, "sort_by": "ranking",
                           "order_by": "asc"}, top_n)
    side_by_id = {p["id"]: _SIDE_LABEL.get(p.get("side"), p.get("side") or "")
                  for p in players}
    rows = [{
        "ranking": r["ranking"],
        "name": r["name"],
        "nationality": r["nationality"],
        "side": side_by_id.get(r["id"], ""),
        "points": r["points"],
        "ranking_diff": r.get("ranking_diff"),
        "points_diff": r.get("points_diff"),
        "date": r.get("date"),
    } for r in ranks]
    return pd.DataFrame(rows, columns=RANKING_COLUMNS)


def _legacy_rankings() -> pd.DataFrame:
    """Adapt the bundled pro_players.csv into the rankings schema (men only).

    Last-resort fallback so the men's table still renders with no token and no
    saved snapshot yet.
    """
    pp = load_pro_players().sort_values("ranking_points", ascending=False)
    return pd.DataFrame({
        "ranking": range(1, len(pp) + 1),
        "name": pp["name"].values,
        "nationality": pp["country"].values,
        "side": pp["side"].map({"D": "Drive", "R": "Reves"}).values,
        "points": pp["ranking_points"].values,
        "ranking_diff": None,
        "points_diff": None,
        "date": "archive",
    })


@st.cache_data(ttl=3600, show_spinner="Loading live Pro Tour rankings…")
def load_rankings(category: str = "men", top_n: int = 30):
    """Return (DataFrame, meta) for the current top-N ranking of one tour.

    Tries the live API first; on any failure falls back to the last saved
    snapshot CSV, then (men only) to the bundled pro_players.csv archive. `meta`
    tells the page whether the data is live, what week it is from, and why if
    it had to fall back. Cached for an hour so reruns don't burn the rate limit.
    """
    snapshot = DATA_DIR / f"rankings_{category}.csv"
    try:
        df = _fetch_rankings_live(category, top_n)
        if df.empty:
            raise RuntimeError("API returned no rows")
        df.to_csv(snapshot, index=False)              # refresh offline cache
        return df, {"live": True, "as_of": df["date"].iloc[0],
                    "source": "Padel API (live)"}
    except Exception as exc:
        if snapshot.exists():
            df = pd.read_csv(snapshot)
            as_of = df["date"].iloc[0] if "date" in df and len(df) else "-"
            return df, {"live": False, "as_of": as_of,
                        "source": "cached snapshot", "error": str(exc)}
        if category == "men":
            return _legacy_rankings(), {"live": False, "as_of": "2025 archive",
                                        "source": "bundled CSV",
                                        "error": str(exc)}
        return (pd.DataFrame(columns=RANKING_COLUMNS),
                {"live": False, "as_of": "-", "source": "unavailable",
                 "error": str(exc)})


# ---------------------------------------------------------------------------
# Live match results — Padel API /matches (both tours, up to today)
#
# /matches returns finished, retired, scheduled and bye entries; we keep only
# played matches (finished / retired) with a score. Tournament names are not on
# the match object, so we look them up once from /tournaments and join by id.
# NOTE: the API does NOT expose court surface (indoor/outdoor) — court_type and
# venue are null — so the old "Surface effect" analysis can't be made live; the
# Pro Tour page analyses tournament tier instead (see 1_Pro_Tour.py).
# ---------------------------------------------------------------------------

# API tournament-tier codes → display labels (also the old P1/P2/Major/Finals).
_LEVEL_LABEL = {"finals": "Finals", "major": "Major", "p1": "P1", "p2": "P2",
                "fip_platinum": "FIP Platinum", "fip_gold": "FIP Gold",
                "fip_silver": "FIP Silver", "fip_bronze": "FIP Bronze"}

MATCH_COLUMNS = ["date", "tournament", "level", "round", "round_name",
                 "team1", "team2", "score", "winner", "duration_min",
                 "n_sets", "status", "category"]


def _duration_to_min(s):
    """'HH:MM' → integer minutes; None / malformed → NaN."""
    if not s or ":" not in str(s):
        return None
    h, m = str(s).split(":")[:2]
    try:
        return int(h) * 60 + int(m)
    except ValueError:
        return None


def _format_score(score) -> str:
    """[{'team_1':'6','team_2':'4'}, …] → '6-4 · 7-6(6)'."""
    if not isinstance(score, list):
        return ""
    return " · ".join(f"{s.get('team_1', '')}-{s.get('team_2', '')}"
                      for s in score)


def _team_names(team) -> str:
    return " / ".join(p.get("name", "") for p in (team or []))


def _tournament_id(connections) -> str:
    """Pull the numeric id out of connections.tournament ('/api/tournaments/736')."""
    if not isinstance(connections, dict):
        return ""
    url = connections.get("tournament", "") or ""
    return url.rstrip("/").split("/")[-1] if url else ""


@st.cache_data(ttl=86400, show_spinner=False)
def _tournament_info(tid: str) -> dict:
    """Name + tier for a tournament id. Cached a day — this metadata is static,
    and recent matches come from only a handful of tournaments, so this keeps us
    well inside the rate limit.
    """
    try:
        d = _padel_get(f"/tournaments/{tid}", {})
        obj = d.get("data") if isinstance(d, dict) and "data" in d else d
        return {"name": obj.get("name"), "level": obj.get("level") or ""}
    except Exception:
        return {}


def _fetch_matches_live(category: str, want: int, max_pages: int = 5) -> pd.DataFrame:
    """Recent played matches for one tour, newest first, mapped to a tidy frame."""
    today = datetime.date.today().isoformat()
    raw = []
    for page in range(1, max_pages + 1):
        payload = _padel_get("/matches",
                            {"category": category, "before_date": today,
                             "sort_by": "played_at", "order_by": "desc",
                             "page": page})
        batch = payload.get("data", [])
        if not batch:
            break
        for m in batch:
            if m.get("status") in ("finished", "retired") and m.get("score"):
                raw.append(m)
        if len(raw) >= want:
            break
        if not (payload.get("links") or {}).get("next"):
            break

    # Resolve the few unique tournaments these matches belong to (id → name/tier).
    tids = {_tournament_id(m.get("connections")) for m in raw}
    tmap = {tid: _tournament_info(tid) for tid in tids if tid}

    rows = []
    for m in raw:
        players = m.get("players", {}) or {}
        tinfo = tmap.get(_tournament_id(m.get("connections")), {}) or {}
        level = tinfo.get("level") or ""
        score = m.get("score")
        rows.append({
            "date": m.get("played_at"),
            "tournament": tinfo.get("name") or _LEVEL_LABEL.get(level, level) or "-",
            "level": _LEVEL_LABEL.get(level, level or "-"),
            "round": m.get("round"),
            "round_name": m.get("round_name"),
            "team1": _team_names(players.get("team_1")),
            "team2": _team_names(players.get("team_2")),
            "score": _format_score(score),
            "winner": _team_names(players.get(m.get("winner")))
                      if m.get("winner") else "",
            "duration_min": _duration_to_min(m.get("duration")),
            "n_sets": len(score) if isinstance(score, list) else None,
            "status": m.get("status"),
            "category": category,
        })
    df = pd.DataFrame(rows, columns=MATCH_COLUMNS)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def _legacy_matches() -> pd.DataFrame:
    """Adapt bundled pro_matches.csv into the live match schema (men only).

    Offline fallback so the men's Matches tab is never empty without a token.
    """
    pm = load_pro_matches()
    score = (pm["set1"].fillna("").astype(str) + " · "
             + pm["set2"].fillna("").astype(str))
    score = score.where(pm["set3"].isna() | (pm["set3"] == ""),
                        score + " · " + pm["set3"].fillna("").astype(str))
    return pd.DataFrame({
        "date": pm["date"],
        "tournament": pm["tournament"],
        "level": pm["category"],
        "round": pm["round"],
        "round_name": pm["round"],
        "team1": pm["team1_p1"] + " / " + pm["team1_p2"],
        "team2": pm["team2_p1"] + " / " + pm["team2_p2"],
        "score": score,
        "winner": pm.apply(lambda r: (r["team1_p1"] + " / " + r["team1_p2"])
                           if r["winner_team"] == 1
                           else (r["team2_p1"] + " / " + r["team2_p2"]), axis=1),
        "duration_min": pm["duration_min"],
        "n_sets": pm[["set1", "set2", "set3"]].notna().sum(axis=1),
        "status": "finished",
        "category": "men",
    })


@st.cache_data(ttl=3600, show_spinner="Loading live match results…")
def load_matches(category: str = "men", want: int = 80):
    """Return (DataFrame, meta) of recent played matches for one tour.

    Live API first; falls back to the last snapshot CSV, then (men only) to the
    bundled pro_matches.csv archive. Cached an hour so reruns stay well inside
    the free-tier rate limit.
    """
    snapshot = DATA_DIR / f"matches_{category}.csv"
    try:
        df = _fetch_matches_live(category, want=want)
        if df.empty:
            raise RuntimeError("API returned no played matches")
        df.to_csv(snapshot, index=False)
        return df, {"live": True, "source": "Padel API (live)"}
    except Exception as exc:
        if snapshot.exists():
            df = pd.read_csv(snapshot, parse_dates=["date"])
            return df, {"live": False, "source": "cached snapshot",
                        "error": str(exc)}
        if category == "men":
            return _legacy_matches(), {"live": False, "source": "2025 archive",
                                       "error": str(exc)}
        return (pd.DataFrame(columns=MATCH_COLUMNS),
                {"live": False, "source": "unavailable", "error": str(exc)})


# ---------------------------------------------------------------------------
# Small visual helpers
# ---------------------------------------------------------------------------

def kpi(label: str, value: str, sub: str = "", color: str = None):
    """Render a labeled KPI block matching the wireframes (theme-aware)."""
    t = get_theme()
    if color is None:
        color = t["ink"]
    st.markdown(
        f"""
        <div style="padding:16px 20px; background:{t['card']}; border:1px solid {t['border']};
                    border-radius:10px; height:100px;">
            <div style="font-size:11px; color:{t['muted']}; letter-spacing:0.5px;">{label}</div>
            <div style="font-size:30px; font-weight:700; color:{color};
                        margin-top:4px; line-height:1.1;">{value}</div>
            <div style="font-size:11px; color:{t['muted']}; margin-top:4px;">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_caption(text: str):
    """Italic muted caption for editorial annotations (theme-aware)."""
    t = get_theme()
    st.markdown(
        f"<p style='color:{t['muted']}; font-style:italic; font-size:12px; "
        f"margin-top:4px;'>{text}</p>",
        unsafe_allow_html=True,
    )


def theme_toggle():
    """Render the dark-mode switch. Call inside the sidebar.

    The value is stored in st.session_state['dark_mode'] under the widget key,
    so every page reads the same choice and it persists across navigation.
    """
    st.toggle(
        "🌙 Dark mode",
        key="dark_mode",
        help="Switch the whole app between light and dark.",
    )


def inject_theme_css():
    """Apply the active theme to the page. Call once at the very top of a page,
    before rendering content, so backgrounds and text colors are set up front.

    This replaces the per-page <style> blocks: it keeps the same layout tweaks
    (top padding, header sizes) and adds the light/dark coloring on top.
    """
    t = get_theme()
    st.markdown(
        f"""
    <style>
      /* layout tweaks (kept from the original per-page styles) */
      .block-container {{padding-top: 2rem;}}
      h1 {{font-size: 1.6rem !important; margin-bottom: 0.5rem;}}
      h2 {{font-size: 1.1rem !important; color: {t['h2']};}}

      /* app shell */
      .stApp {{background-color: {t['page']}; color: {t['ink']};}}
      [data-testid="stHeader"] {{background-color: {t['page']};}}
      section[data-testid="stSidebar"] {{background-color: {t['sidebar']};}}

      /* text — override Streamlit's fixed (light) text color in dark mode.
         Inline-styled card text wins over these rules, so cards keep their
         own theme colors. */
      [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] *,
      [data-testid="stHeading"], [data-testid="stWidgetLabel"],
      [data-testid="stWidgetLabel"] *, [data-testid="stCaptionContainer"],
      .stApp h1, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {{
          color: {t['ink']};
      }}

      /* form controls */
      [data-baseweb="input"], [data-baseweb="textarea"],
      [data-baseweb="select"] > div, [data-baseweb="base-input"] {{
          background-color: {t['card']};
      }}
      [data-baseweb="input"] input, [data-baseweb="textarea"] textarea,
      [data-baseweb="select"] {{ color: {t['ink']}; }}

      /* expander — keep the page background when opened instead of Streamlit's
         default light panel, so toggling it just reveals the content without
         the header/box flashing white. */
      [data-testid="stExpander"] details,
      [data-testid="stExpander"] details > summary {{
          background-color: {t['page']} !important;
          border-color: {t['border']};
          color: {t['ink']};
      }}
      [data-testid="stExpander"] details > summary:hover {{
          color: {t['ink']};
      }}
      [data-testid="stExpander"] details > summary svg {{ fill: {t['ink']}; }}

      /* dataframe (glide-data-grid reads these CSS custom properties) */
      [data-testid="stDataFrame"], [data-testid="stDataFrameResizable"] {{
          --gdg-bg-cell: {t['card']};
          --gdg-bg-cell-medium: {t['sidebar']};
          --gdg-bg-header: {t['sidebar']};
          --gdg-bg-header-hovered: {t['border']};
          --gdg-bg-header-has-focus: {t['border']};
          --gdg-text-dark: {t['ink']};
          --gdg-text-medium: {t['muted']};
          --gdg-text-light: {t['muted']};
          --gdg-text-header: {t['muted']};
          --gdg-border-color: {t['border']};
          --gdg-horizontal-border-color: {t['border']};
      }}
    </style>
    """,
        unsafe_allow_html=True,
    )


def themed_fig(fig):
    """Recolor a Plotly figure's chrome (background, text, gridlines) for the
    active theme. Wrap charts at render time: st.plotly_chart(themed_fig(fig)).

    Data colors set on the traces (BLUE bars, RED lines, etc.) are untouched.
    """
    t = get_theme()
    fig.update_layout(
        paper_bgcolor=t["card"],
        plot_bgcolor=t["card"],
        font=dict(color=t["ink"]),
        legend=dict(font=dict(color=t["ink"])),
    )
    # Cartesian axes (no-op on polar-only figures, so it's safe to call always).
    fig.update_xaxes(gridcolor=t["grid"], zerolinecolor=t["zero"])
    fig.update_yaxes(gridcolor=t["grid"], zerolinecolor=t["zero"])
    return fig


def sidebar_player_name() -> str:
    """Render player-name input in the sidebar; returns the current name.

    Uses session_state so the value persists across all pages without
    requiring a separate persistence layer.
    """
    if "player_name" not in st.session_state:
        st.session_state["player_name"] = "Marco"
    theme_toggle()
    st.markdown("---")
    name = st.text_input(
        "Your name",
        key="player_name",
        help="Change to personalise your stats across all pages",
    )
    return name or "Player"


def apply_theme(fig):
    """Apply the shared Plotly theme to any figure (theme-aware). Plotly only."""
    t = get_theme()
    fig.update_layout(
        font=dict(family="Inter, Arial, sans-serif", color=t["ink"], size=12),
        paper_bgcolor=t["card"],
        plot_bgcolor=t["card"],
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=True, gridcolor=t["grid"], zeroline=False),
    )
    return fig


# ---------------------------------------------------------------------------
# Domain helpers
# ---------------------------------------------------------------------------

def partner_win_rate(my_matches: pd.DataFrame) -> pd.DataFrame:
    """Return a tidy frame: partner, matches, wins, win_rate, is_best, is_worst."""
    g = (my_matches.groupby("partner")["won"]
                   .agg(["sum", "count"])
                   .reset_index()
                   .rename(columns={"sum": "wins", "count": "matches"}))
    g["win_rate"] = g["wins"] / g["matches"]
    g = g.sort_values("win_rate", ascending=False).reset_index(drop=True)
    g["is_best"] = False
    g["is_worst"] = False
    if len(g):
        g.loc[g.index[0], "is_best"] = True
        g.loc[g.index[-1], "is_worst"] = True
    return g


def shot_dna(my_matches: pd.DataFrame) -> pd.DataFrame:
    """Return per-shot winners, errors and net for the personal log."""
    rows = []
    for s in SHOT_TYPES:
        w = int(my_matches[f"winners_{s}"].sum())
        e = int(my_matches[f"errors_{s}"].sum())
        rows.append({"shot": s.title(), "winners": w, "errors": e, "net": w - e})
    return pd.DataFrame(rows).sort_values("net", ascending=False).reset_index(drop=True)


def rolling_win_rate(my_matches: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    """Return date + rolling win rate (% wins over last `window` matches)."""
    df = my_matches.copy()
    df["rolling"] = df["won"].rolling(window=window, min_periods=1).mean()
    return df[["date", "rolling"]]


def pro_player_form(pro_matches: pd.DataFrame, player: str, n: int = 10) -> list:
    """Return last n match results for a player: 1 = win, 0 = loss."""
    m = pro_matches[
        (pro_matches.team1_p1 == player) | (pro_matches.team1_p2 == player) |
        (pro_matches.team2_p1 == player) | (pro_matches.team2_p2 == player)
    ].sort_values("date", ascending=False).head(n)
    out = []
    for _, row in m.iterrows():
        on_team1 = row.team1_p1 == player or row.team1_p2 == player
        out.append(1 if (on_team1 and row.winner_team == 1) or
                   (not on_team1 and row.winner_team == 2) else 0)
    return list(reversed(out))
