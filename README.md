# PadelLens

**Data Visualization for Sport, Exam Project, Politecnico Milano AY 2025/2026**

A Streamlit web application for amateur padel players. It has two complementary halves:

- **Pro Tour Insights**: explore **live** Premier Padel rankings for both the men's and women's tours (pulled from the Padel API), plus match results and tournament statistics.
- **My Match Log**: log your own matches and surface patterns (partner effects, shot tendencies, fatigue curves) that are invisible during play.

---

## Quick Start

```bash
# 1. Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) Enable live rankings, paste a free Padel API token
#    Get one at https://padelapi.org, then in .streamlit/secrets.toml set:
#    PADEL_API_TOKEN = "your-token-here"
#    Without a token the app still runs from the bundled ranking snapshots.

# 4. Run
streamlit run Dashboard.py
```

App opens at **http://localhost:8501**

---

## Project Layout

```
05_App/
├── Dashboard.py               Home page — landing dashboard
├── utils.py                   Shared data loaders, helpers, chart theme
├── requirements.txt           Python dependencies
├── .streamlit/
│   ├── config.toml            UI theme (colors, font, background)
│   └── secrets.toml           Padel API token (git-ignored; you create this)
├── pages/
│   ├── 1_Pro_Tour.py          Premier Padel explorer (rankings + matches + surface)
│   ├── 2_My_Stats.py          Personal analytics dashboard
│   ├── 3_Log_Match.py         Match entry form (appends to CSV)
│   └── 4_Compare.py           Personal shot profile vs pro reference (radar)
└── data/
    ├── rankings_men.csv       Cached live snapshot — men's top 30 (auto-refreshed)
    ├── rankings_women.csv     Cached live snapshot — women's top 30 (auto-refreshed)
    ├── matches_men.csv        Cached live snapshot — recent men's results (auto-refreshed)
    ├── matches_women.csv      Cached live snapshot — recent women's results (auto-refreshed)
    ├── pro_players.csv        Offline fallback — top 30 male players
    ├── pro_matches.csv        Offline fallback — 276 men's matches (Feb 2024 onward)
    └── my_matches.csv         40 personal match seed records for demo user "Marco"
```

Streamlit automatically turns every file in `pages/` into a sidebar route. The numeric prefix controls display order.

---

## Pages

### Dashboard (`Dashboard.py`)

The landing dashboard. Designed to answer *"How am I doing and what should I work on?"* in under 10 seconds.

| Section | What It Shows |
|---|---|
| KPI block | Last-10 win rate + delta vs previous 10 |
| Sparkline | Rolling 5-match win rate trend (15 matches) |
| Pro #1 card | Current World No.1 and No.2 from rankings |
| Partner effect | Horizontal bar — win rate per partner, best/worst highlighted |
| Shot DNA | Diverging bar — winners (right) vs errors (left) per shot type |
| Weekly recommendation | Auto-generated drill tip based on lowest net-balance shot |
| Recent matches | Last 6 matches: date, partner, opponents, score |

---

### Pro Tour (`pages/1_Pro_Tour.py`)

Three **fully live** tabs driven by a shared sidebar (Tour = Men/Women, country, tournament tier, date range). Picking a tour re-fetches everything for that circuit.

**Rankings**: live top-30 table for the **men's or women's** tour, fetched from the Padel API. Columns: rank, player, country, side, current points, and the weekly points movement (Δ pts). Pairs share a rank exactly as on the official FIP site. The caption shows the snapshot week, and the table falls back to a cached snapshot if the API is unreachable.

**Matches**: live played results (finished & retired) for the selected tour, newest first, **up to today**. Columns: date, tournament, round, both teams, set score, winner, duration. Filterable by tournament tier and date.

**Match dynamics**: two charts on the same live results:
- Straight-set rate (% won 2-0) **per tournament tier**
- Match duration distribution (box plot) **per tournament tier**
- *Why tier, not surface?* The API does not expose court surface (indoor/outdoor). `court_type`/`venue` are null, so the analysis groups by tournament tier instead. Editorial reading: higher tiers tend to produce tighter matches.

---

### My Stats (`pages/2_My_Stats.py`)

Detailed personal analytics with a time-window filter (All time / Last 30 / 60 / 90 days) in the sidebar.

**KPI row:** Total matches · Win rate (W-L) · 3-set fade (win rate in deciding sets) · Current streak

**Chart grid (2×2):**
- Rolling win rate — 5-match window with 50% reference line and shaded fill
- Win rate by partner — sorted horizontal bars
- Shot DNA — diverging bar (winners vs errors per shot)
- Set-by-set fatigue — 2-set win rate vs 3-set win rate with delta annotation

**Bottom:** Full filtered match table + CSV download button.

---

### Log Match (`pages/3_Log_Match.py`)

Data entry form targeting under 90 seconds to complete.

- Club and partner names autocomplete from existing match history
- Set 3 score inputs are disabled unless Sets 1–2 are split (automatic validation)
- Real-time result preview updates as you type scores
- Shot tallies (winners/errors per shot) are optional, wrapped in a collapsible expander
- On submit: appends a new row to `data/my_matches.csv` and clears the Streamlit data cache so all charts refresh immediately

---

### Compare (`pages/4_Compare.py`)

Radar chart (polar plot) comparing your average winners per match against a professional reference across 5 shot types: forehand, backhand, smash, volley, bandeja.

**Pro reference values** are aggregate averages derived from documented Premier Padel performance studies:

```python
PRO_AVG = {
    "forehand": 5.2,
    "backhand": 5.8,
    "smash":    4.1,
    "volley":   6.5,
    "bandeja":  4.2
}
```

**Gap analysis cards**: one per shot, sorted worst-first, color-coded (red / orange / green). Each card includes a specific drill recommendation tailored to that shot.

---

## Data

All Pro Tour data is **live** from the [Padel API](https://padelapi.org); the CSVs below are auto-written snapshots used as offline fallbacks so the demo never breaks.

### `data/rankings_men.csv` · `data/rankings_women.csv`
Snapshots of the live top-30 ranking for each tour, rewritten on every successful fetch by `load_rankings()`. Columns: `ranking`, `name`, `nationality`, `side`, `points`, `ranking_diff`, `points_diff`, `date`.

### `data/matches_men.csv` · `data/matches_women.csv`
Snapshots of the live recent results for each tour, rewritten by `load_matches()`. Columns: `date`, `tournament`, `level`, `round`, `round_name`, `team1`, `team2`, `score`, `winner`, `duration_min`, `n_sets`, `status`, `category`.

### `data/pro_players.csv`
30 rows. Columns: `player_id`, `name`, `country`, `side` (D=Drive / R=Reves), `hand`, `height_cm`, `birth_year`, `ranking_points`.
Source: [Padel API](https://padelapi.org) free tier. Now the **last-resort** men's ranking fallback (API + snapshot both unavailable) and the Compare page's player picker.

### `data/pro_matches.csv`
276 rows, Feb 2024 onward. The **last-resort** men's match fallback, adapted into the live schema by `load_matches()` when the API and snapshot are both unavailable.

### `data/my_matches.csv`
40 seed rows for demo user "Marco" (Nov 2024 onward). Columns: `match_id`, `date`, `partner`, `opponents`, `club`, `surface`, `sets_played`, set scores (up to 3 sets), `result` (W/L), winners and errors per shot (10 columns), `duration_min`, `notes`.
Real users replace this file entirely via the Log Match page.

---

## Shared Utilities (`utils.py`)

All pages import from `utils.py`. Key contents:

| Name | Type | Purpose |
|---|---|---|
| `load_pro_players()` | cached loader | Reads `pro_players.csv` |
| `load_pro_matches()` | cached loader | Reads `pro_matches.csv`, parses dates |
| `load_my_matches()` | cached loader | Reads `my_matches.csv`, parses dates, adds `won` boolean, pre-calculates shot net balance |
| `load_rankings(category)` | cached live loader | Fetches the current men's/women's top-30 from the Padel API (merging `/rankings` + `/players`); writes a snapshot CSV and falls back to it, then to `pro_players.csv`, when offline |
| `load_matches(category)` | cached live loader | Fetches recent played men's/women's results from `/matches` (tournament names joined from `/tournaments`); snapshot + `pro_matches.csv` fallback |
| `BLUE / RED / GREEN / ORANGE / GRAY / INK / MUTED` | color constants | Shared palette — one change updates all charts |
| `SHOT_TYPES` | list | `["forehand", "backhand", "smash", "volley", "bandeja"]` |
| `kpi(label, value, sub, color)` | UI helper | Renders styled KPI cards using `st.markdown` |
| `apply_theme(fig)` | chart helper | Applies consistent Plotly font, backgrounds, and gridlines |
| `partner_win_rate(df)` | analytics | Groups by partner, computes sorted win rates, flags best/worst |
| `shot_dna(df)` | analytics | Averages winners and errors per match per shot type |
| `rolling_win_rate(df, window=5)` | analytics | Returns rolling win percentage Series |
| `pro_player_form(df, name, n=10)` | analytics | Last `n` match results for a named pro player |
| `sidebar_player_name()` | UI helper | Persistent player name input (session_state, default "Marco") |

`@st.cache_data` decorators on loaders mean CSVs are read from disk once per session.

---

## Tech Stack

| Library | Version | Role |
|---|---|---|
| Python | 3.9+ | Core language |
| Streamlit | ≥ 1.32 | Multi-page app framework, sidebar, forms, cache |
| Pandas | ≥ 2.0 | Data wrangling, filtering, groupby, rolling windows |
| Plotly | ≥ 5.18 | Interactive line, bar, box, radar charts |
| Requests | ≥ 2.31 | Live Padel API integration — men's & women's rankings |

Total application code: approximately **600 lines across 5 Python files**.

---

## Design Decisions

**CSV over a database**: single-user local app. A database would be overhead with no benefit for a demo context.

**Streamlit over Flask/React**: this is a data visualization project. Streamlit delivers charts and interactivity in pure Python, keeping the codebase focused on data logic rather than frontend plumbing.

**Plotly over matplotlib**: interactive charts (hover tooltips, zoom) are more engaging during a live demo and allow the user to explore data independently.

**Every chart has an editorial caption**: a chart without a takeaway is decoration. Every visualization is annotated with the insight it is designed to surface.

**Rolling window = 5**: wide enough to smooth noise, narrow enough to be sensitive to recent form changes. A 10-match window would mask emerging trends.

**Cache clear on form submit**: `st.cache_data.clear()` is called immediately after a new match is appended. Without it, charts would not reflect the new entry until the session restarted.

**Shot tallies are optional**: requiring shot data on every entry would kill adoption. The form works as a pure W/L log; shot analytics become richer over time as users add tallies selectively.

---

## Known Limitations

- **No per-player shot statistics**: the API tier used does not expose shot-by-shot data. The Compare page uses documented aggregate averages as the reference, with a side-tilt heuristic for Drive vs Reves comparison.
- **No court surface in the API**: `court_type`/`venue` come back null, so the Match dynamics tab groups results by tournament tier rather than indoor/outdoor.
- **Free API tier**: 10 requests/minute and roughly 6 months of match history. The app caches for an hour and snapshots every successful fetch, so a rate-limited cold start falls back to the last snapshot instead of failing.
- **No court heatmaps**: positional tracking data is out of scope (see `../01_Brief/` §1.5).
- **Single-user, local storage**: match logs live in `data/my_matches.csv` on the local machine. No multi-user or cloud sync.
- **No authentication**: intended for personal local use only.

---

## Demo Path

1. **Home**: review KPI block and weekly recommendation
2. **Pro Tour → Rankings tab**: toggle Men/Women, read live points and the weekly Δ
3. **Pro Tour → Matches / Match dynamics**: live results up to today; straight-set rate and duration by tier
4. **My Stats**: switch time filter to "Last 30 days", observe trend shift
5. **Log Match**: fill in a new match (under 90 seconds), submit
6. **Home**: confirm KPI and recent matches table have updated
7. **Compare**: read gap analysis cards and drill recommendations

---

## Exam Deliverable Map

| Folder | Content |
|---|---|
| `../01_Brief/` | Project brief, editorial angle, research questions |
| `../02_Data/` | Data acquisition notes, API client, raw CSV exports |
| `../03_UX/` | Wireframes, Nielsen heuristic evaluation |
| `../04_Visual_Encoding/` | Chart choice justifications (Kirk framework) |
| `../05_App/` | This folder — working Streamlit application |
