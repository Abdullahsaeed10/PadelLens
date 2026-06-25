"""PadelLens — Dashboard (home) page.

Run: streamlit run Dashboard.py
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import (BLUE, RED, GRAY, get_theme, inject_theme_css, kpi,
                   load_my_matches, load_pro_matches, load_rankings,
                   partner_win_rate, render_table, section_caption, shot_dna,
                   sidebar_player_name, themed_fig)

st.set_page_config(
    page_title="PadelLens - Dashboard",
    page_icon="🎾",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "PadelLens - Politecnico Milano."},
)

# Apply the active theme (light/dark) — replaces the old fixed light styles.
inject_theme_css()
t = get_theme()

mm = load_my_matches()
pm = load_pro_matches()
rk, rk_meta = load_rankings("men")   # live men's ranking for the World #1 card

# ---- Sidebar
with st.sidebar:
    st.markdown("### PadelLens")
    st.caption("Pro Tour Insights + My Match Log")
    player_name = sidebar_player_name()
    st.markdown(f"**Viewing as:** {player_name}")
    st.caption("Politecnico Milano AY 2025/2026")

# ---- Header
st.title("🎾 PadelLens")
st.caption(f"Welcome back, **{player_name}**. Your padel game, at a glance.")

# ---- Hero row: last-10 KPI + today's pro card
hero_col, pro_col = st.columns([2, 1])

with hero_col:
    last10 = mm.tail(10)
    w = int(last10["won"].sum())
    l = len(last10) - w
    rate = w / max(1, len(last10))
    prev = mm.iloc[-20:-10] if len(mm) >= 20 else mm.iloc[:0]
    prev_rate = prev["won"].mean() if len(prev) else rate
    delta_pp = (rate - prev_rate) * 100

    st.markdown(
        f"""
        <div style="padding:24px 28px; background:{t['card']};
                    border:1px solid {t['border']}; border-radius:10px;">
          <div style="font-size:11px; color:{t['muted']}; letter-spacing:0.5px;">
              YOUR LAST 10 MATCHES</div>
          <div style="font-size:48px; font-weight:700; color:{t['ink']};
                      margin-top:8px; line-height:1;">{w}-{l}</div>
          <div style="font-size:13px; color:{t['muted']}; margin-top:6px;">
              {rate*100:.0f}% win rate ·
              <span style="color:{t['good_fg'] if delta_pp>=0 else t['bad_fg']};">
              {'↑' if delta_pp>=0 else '↓'} {abs(delta_pp):.0f}pp vs previous 10
              </span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Form sparkline under the hero — a 5-match rolling win rate so the
    # *trajectory* of recent form is readable, not just the headline number.
    spark = mm.tail(15).reset_index(drop=True).assign(idx=lambda d: range(len(d)))
    spark["roll"] = spark["won"].rolling(5, min_periods=1).mean()
    spark["date_str"] = spark["date"].dt.strftime("%d %b")
    spark["result"] = spark["won"].map({True: "Won", False: "Lost"})

    # Title so the reader knows what the line measures.
    st.markdown(
        f"<div style='font-size:11px; color:{t['muted']}; letter-spacing:0.5px; "
        f"margin:14px 0 2px;'>FORM TREND · 5-MATCH ROLLING WIN RATE · LAST 15</div>",
        unsafe_allow_html=True,
    )

    fig = go.Figure(go.Scatter(
        x=spark["idx"], y=spark["roll"],
        mode="lines+markers", line=dict(color=BLUE, width=2.5),
        marker=dict(size=5, color=BLUE),
        fill="tozeroy", fillcolor="rgba(14,165,233,0.1)",
        customdata=spark[["date_str", "result"]],
        hovertemplate="%{customdata[0]} · %{customdata[1]}<br>"
                      "Rolling win rate: %{y:.0%}<extra></extra>",
    ))
    # 50% break-even baseline: above = winning the majority of the recent
    # window, below = losing it. Gives the line a reference to read against.
    fig.add_hline(y=0.5, line=dict(color=t["zero"], width=1, dash="dot"),
                  annotation_text="50% break-even",
                  annotation_position="bottom left",
                  annotation_font=dict(size=10, color=t["muted"]))
    # Label the most recent value at the right end.
    last = spark.iloc[-1]
    fig.add_annotation(x=last["idx"], y=last["roll"], text=f"{last['roll']:.0%}",
                       showarrow=False, yshift=13, xshift=-6,
                       font=dict(size=11, color=BLUE))
    fig.update_layout(
        height=150, margin=dict(l=8, r=24, t=16, b=22),
        xaxis=dict(title=dict(text="older  →  most recent",
                              font=dict(size=10, color=t["muted"])),
                   showticklabels=False, showgrid=False, zeroline=False),
        yaxis=dict(range=[0, 1.08], tickvals=[0, 0.5, 1],
                   ticktext=["0%", "50%", "100%"],
                   tickfont=dict(size=10, color=t["muted"]), showgrid=False),
        showlegend=False,
    )
    st.plotly_chart(themed_fig(fig), use_container_width=True,
                    config={"displayModeBar": False})
    section_caption("How to read it: each point is your win rate over the trailing "
                    "5 matches. Hover any point for the date and result; above the "
                    "dotted 50% line means you're winning most of your recent games.")

with pro_col:
    # rk is already ordered by ranking; the top two share rank #1 (a pair).
    top, top2 = rk.iloc[0], rk.iloc[1]
    as_of = f"week of {rk_meta['as_of']}" if rk_meta["live"] else rk_meta["as_of"]
    st.markdown(
        f"""
        <div style="padding:24px 28px; background:{t['card']};
                    border:1px solid {t['border']}; border-radius:10px; height:230px;">
          <div style="font-size:11px; color:{t['muted']}; letter-spacing:0.5px;">
              PRO TOUR · WORLD #1 · {as_of}</div>
          <div style="font-size:22px; font-weight:700; color:{t['ink']};
                      margin-top:16px;">{top['name']} / {top2['name']}</div>
          <div style="font-size:13px; color:{t['muted']}; margin-top:6px;">
              {int(top['points']):,} pts · {top['nationality']} / {top2['nationality']}</div>
          <div style="font-size:12px; color:{t['muted']}; margin-top:12px;
                      font-style:italic;">→ Open Pro Tour to drill into matches</div>
        </div>
        """, unsafe_allow_html=True
    )

st.write("")

# ---- Row 2: three cards — partner effect, shot DNA, recommendation
c1, c2, c3 = st.columns(3)

with c1:
    st.markdown("##### Partner effect")
    pw = partner_win_rate(mm)
    fig = go.Figure()
    colors = [RED if r.is_worst else BLUE for r in pw.itertuples()]
    fig.add_trace(go.Bar(y=pw["partner"], x=pw["win_rate"]*100, orientation="h",
                         marker=dict(color=colors),
                         text=[f"{r*100:.0f}%" for r in pw['win_rate']],
                         textposition="outside",
                         hovertemplate="<b>%{y}</b><br>Win rate: %{x:.0f}%"
                                       "<extra></extra>"))
    fig.update_layout(height=240, margin=dict(l=0, r=20, t=10, b=0),
                      xaxis=dict(visible=False, range=[0, 100]),
                      yaxis=dict(autorange="reversed"),
                      showlegend=False)
    st.plotly_chart(themed_fig(fig), use_container_width=True,
                    config={"displayModeBar": False})
    best, worst = pw.iloc[0], pw.iloc[-1]
    st.caption(f"**{best['partner']}** is your strongest pairing "
               f"({best['win_rate']*100:.0f}%). **{worst['partner']}** is your weakest "
               f"({worst['win_rate']*100:.0f}%).")

with c2:
    st.markdown("##### Shot DNA")
    sd = shot_dna(mm)
    fig = go.Figure()
    # diverging bars: errors to the left, winners to the right
    fig.add_trace(go.Bar(y=sd["shot"], x=sd["winners"], orientation="h",
                        name="Winners", marker_color=BLUE,
                        hovertemplate="Winners: %{x}<extra></extra>"))
    fig.add_trace(go.Bar(y=sd["shot"], x=-sd["errors"], orientation="h",
                        name="Errors", marker_color=RED,
                        hovertemplate="Errors: %{customdata}<extra></extra>",
                        customdata=sd["errors"]))
    fig.update_layout(barmode="overlay", height=240,
                      margin=dict(l=0, r=20, t=10, b=20),
                      xaxis=dict(title="errors  ←  0  →  winners",
                                 showgrid=False, zeroline=True),
                      yaxis=dict(autorange="reversed"),
                      showlegend=False)
    st.plotly_chart(themed_fig(fig), use_container_width=True,
                    config={"displayModeBar": False})
    st.caption(f"**{sd.iloc[0]['shot']}** is your weapon (+{sd.iloc[0]['net']}). "
               f"**{sd.iloc[-1]['shot']}** bleeds points ({sd.iloc[-1]['net']}).")

with c3:
    st.markdown("##### Recommended this week")
    worst_shot = sd.iloc[-1]
    st.markdown(
        f"""
        <div style="padding:8px 0;">
          <div style="font-size:14px; color:{t['ink']}; font-weight:600;">
            Drill: {worst_shot['shot'].lower()} stability
          </div>
          <p style="font-size:13px; color:{t['muted']}; margin-top:8px;">
            You lose roughly <b>{abs(worst_shot['net']) // len(mm) + 1}</b> points/match
            on {worst_shot['shot'].lower()}s, vs your strongest shot (bandeja: +{sd.iloc[0]['net']} net).
            Three focused drill sets per week.
          </p>
          <p style="font-size:13px; color:{t['muted']};">
            <b>Why:</b> the gap to your strongest shot is the largest opportunity in your game.
          </p>
        </div>
        """, unsafe_allow_html=True
    )

st.write("")

# ---- Bottom row: recent matches + log button
b1, b2 = st.columns([2, 1])

with b1:
    st.markdown("##### Recent matches")
    recent = mm.sort_values("date", ascending=False).head(6).copy()
    recent["date_str"] = recent["date"].dt.strftime("%d %b %Y")
    recent["score"] = recent.apply(
        lambda r: f"{r.set1_us}-{r.set1_them} {r.set2_us}-{r.set2_them}" +
                  (f" {int(r.set3_us)}-{int(r.set3_them)}" if pd.notna(r.set3_us) and r.set3_us != "" else ""),
        axis=1
    )
    table = recent[["date_str", "partner", "opponents", "score", "result", "surface"]]
    table.columns = ["Date", "Partner", "Opponents", "Score", "Result", "Surface"]
    render_table(table)

with b2:
    st.markdown("##### Just played?")
    st.markdown(
        f"<p style='color:{t['muted']}; font-size:13px;'>Log it in 90 seconds: "
        "the data pipeline starts here.</p>",
        unsafe_allow_html=True
    )
    st.page_link("pages/3_Log_Match.py", label="➕ Log a new match",
                 icon=None, use_container_width=True)
    st.caption("Friction killer: one button, always visible above the fold.")
