"""Pro Tour Explorer — live rankings, results and match dynamics (men & women)."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import (BLUE, GRAY, inject_theme_css, load_matches,
                   load_pro_matches, load_pro_players, load_rankings,
                   render_form_sparklines, render_table, section_caption,
                   sidebar_player_name, themed_fig)

st.set_page_config(page_title="Pro Tour · PadelLens",
                   page_icon="🏆", layout="wide")
inject_theme_css()

st.title("Pro Tour")
st.caption("Live Premier Padel rankings and results, men's and women's tours.")

# ---- Sidebar filters
with st.sidebar:
    player_name = sidebar_player_name()
    st.markdown("---")
    st.markdown("### Filters")

    # Men's vs women's tour — both pull live. Drives every table on the page:
    # rankings, the country list, and the live match results below.
    tour = st.radio("Tour", ["Men", "Women"], horizontal=True,
                    help="Switch between the men's and women's Premier Padel "
                         "tour. Rankings and results both pull live.")
    category = "men" if tour == "Men" else "women"
    rk_df, rk_meta = load_rankings(category)
    mt_df, mt_meta = load_matches(category)

    countries = ["All"] + sorted(rk_df["nationality"].dropna().unique().tolist())
    country = st.selectbox("Country", countries)

    # Match filters come from the live results (tournament tier + date window).
    if not mt_df.empty:
        levels = sorted(mt_df["level"].dropna().unique().tolist())
        tiers = st.multiselect("Tournament tier", levels, default=levels)
        d_min, d_max = mt_df["date"].min().date(), mt_df["date"].max().date()
        date_range = st.date_input("Date range", value=(d_min, d_max),
                                   min_value=d_min, max_value=d_max)
    else:
        tiers, date_range = [], None

    if st.button("Reset filters"):
        st.cache_data.clear()   # forces a fresh live fetch of rankings + results
        st.rerun()

# ---- Apply filters
# Rankings: by country.
rk_f = rk_df if country == "All" else rk_df[rk_df["nationality"] == country]

# Matches: by tournament tier + date window.
mt_f = mt_df.copy()
if not mt_f.empty:
    if tiers:
        mt_f = mt_f[mt_f["level"].isin(tiers)]
    if isinstance(date_range, tuple) and len(date_range) == 2:
        mt_f = mt_f[(mt_f["date"].dt.date >= date_range[0]) &
                    (mt_f["date"].dt.date <= date_range[1])]

# ---- Tabs (rankings / results / match dynamics)
tab1, tab2, tab3 = st.tabs(["Rankings", "Matches", "Match dynamics"])

with tab1:
    label = "Men's" if category == "men" else "Women's"
    st.markdown(f"##### Premier Padel · {label} · top {len(rk_f)} players")

    def _delta(d):
        """Weekly points change as a signed string ('-' when not reported)."""
        if pd.isna(d):
            return "-"
        d = int(d)
        return f"{d:+,}" if d else "0"

    table_df = pd.DataFrame({
        "#": rk_f["ranking"],
        "Player": rk_f["name"],
        "Country": rk_f["nationality"],
        "Side": rk_f["side"],
        "Points": rk_f["points"].map(lambda p: f"{int(p):,}"),
        "Δ pts (wk)": rk_f["points_diff"].map(_delta),
    })
    render_table(
        table_df,
        height=560,
        header_tooltips={
            "Δ pts (wk)": "Ranking points gained or lost since last week's snapshot.",
        },
    )

    if rk_meta["live"]:
        section_caption(
            f"Live from the Padel API: official FIP ranking, week of "
            f"<b>{rk_meta['as_of']}</b>. Pairs share a rank, exactly as on the "
            f"official site. ‘Δ pts’ is the change since the previous weekly "
            f"snapshot, momentum without breaking the row.")
    else:
        section_caption(
            f"⚠ Offline: showing the {rk_meta['source']} ({rk_meta['as_of']}). "
            f"Add a valid token in <code>.streamlit/secrets.toml</code> to go live.")

    # ---- Form sparklines: the "rankings + form" card, built for real.
    # Pairs the marquee field with each player's recent form. Form comes from the
    # logged pro-match dataset (the men's draw), so it's gated to the men's tour;
    # the live table above still covers both tours.
    if category == "men":
        st.markdown("##### Top 12 · recent form")
        top12 = load_pro_players().sort_values(
            "ranking_points", ascending=False).head(12)
        render_form_sparklines(top12, load_pro_matches())
        section_caption(
            "Form is the rolling win rate over each player's last 10 logged pro "
            "matches — the same metric as your personal form trend. The line "
            "turns <b>red</b> when recent form is trending down, blue otherwise.")

with tab2:
    tour_label = "Men's" if category == "men" else "Women's"
    st.markdown(f"##### {tour_label} recent results · {len(mt_f)} matches")
    if mt_f.empty:
        st.info("No live match results available right now. Check the API token "
                "in `.streamlit/secrets.toml`, or try again during a tournament "
                "week.")
    else:
        show = mt_f.sort_values("date", ascending=False).copy()
        show["Date"] = show["date"].dt.strftime("%d %b %Y")
        out = show[["Date", "tournament", "round_name", "team1", "team2",
                    "score", "winner", "duration_min"]]
        out.columns = ["Date", "Tournament", "Round", "Team 1", "Team 2",
                       "Score", "Winner", "Duration (min)"]
        render_table(out.head(80), height=560)
        src = ("Live from the Padel API" if mt_meta["live"]
               else f"⚠ Offline: {mt_meta['source']}")
        section_caption(
            f"{src}. Played matches only (finished & retired), newest first, "
            f"right up to today.")

with tab3:
    st.markdown("##### Match dynamics by tournament tier")
    fin = mt_f[mt_f["status"] == "finished"].copy() if not mt_f.empty else mt_f
    if mt_f.empty or fin.empty:
        st.info("Not enough live match data yet to chart dynamics. Widen the "
                "date range, or check back during a tournament week.")
    else:
        col_a, col_b = st.columns(2)

        with col_a:
            # Straight-set rate (won 2–0) per tournament tier.
            fin["straight"] = fin["n_sets"] == 2
            rates = (fin.groupby("level")["straight"].mean()
                        .reset_index().sort_values("straight", ascending=False))
            rates["rate_pct"] = rates["straight"] * 100
            fig = go.Figure(go.Bar(
                x=rates["level"], y=rates["rate_pct"], marker_color=BLUE,
                text=[f"{v:.0f}%" for v in rates["rate_pct"]],
                textposition="outside"))
            fig.update_layout(
                title="Straight-set rate by tier", height=320,
                margin=dict(l=20, r=20, t=50, b=20),
                yaxis=dict(range=[0, 100], showgrid=True),
                xaxis=dict(showgrid=False, title=""))
            st.plotly_chart(themed_fig(fig), use_container_width=True,
                            config={"displayModeBar": False})

        with col_b:
            dur = mt_f[mt_f["duration_min"].notna()]
            fig = px.box(dur, x="level", y="duration_min", points=False,
                         color_discrete_sequence=[GRAY])
            fig.update_layout(
                title="Match duration by tier", height=320,
                margin=dict(l=20, r=20, t=50, b=20), showlegend=False,
                yaxis=dict(showgrid=True, title="minutes"),
                xaxis=dict(title=""))
            st.plotly_chart(themed_fig(fig), use_container_width=True,
                            config={"displayModeBar": False})

    section_caption(
        "Court surface (indoor/outdoor) isn't exposed by the live API, so we "
        "compare by tournament tier instead. Straight-set rate = share won 2–0; "
        "higher tiers tend to produce tighter matches.")
