"""My Stats — personal analytics dashboard."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import (BLUE, RED, INK, MUTED, get_theme, inject_theme_css, kpi,
                   load_my_matches, partner_win_rate, rolling_win_rate,
                   section_caption, shot_dna, sidebar_player_name, themed_fig)

st.set_page_config(page_title="My Stats · PadelLens",
                   page_icon="📊", layout="wide")
inject_theme_css()
t = get_theme()

mm = load_my_matches()

st.title("My Stats")
st.caption("What you can see now that you couldn't feel during the match.")

# ---- Sidebar filter
with st.sidebar:
    player_name = sidebar_player_name()
    st.markdown("---")
    st.markdown("### Filter")
    window = st.radio("Show data from", ["All time", "Last 30 days",
                                          "Last 60 days", "Last 90 days"],
                      index=0)
    if window != "All time":
        days = int(window.split()[1])
        cutoff = mm["date"].max() - pd.Timedelta(days=days)
        mm = mm[mm["date"] >= cutoff]
    st.caption(f"{len(mm)} matches in current view.")

# ---- KPI row
c1, c2, c3, c4 = st.columns(4)
with c1:
    kpi("TOTAL MATCHES", str(len(mm)),
        f"since {mm['date'].min().strftime('%b %Y')}")
with c2:
    wr = mm["won"].mean()
    kpi("WIN RATE", f"{wr*100:.0f}%",
        f"{int(mm['won'].sum())}W · {int((~mm['won']).sum())}L")
with c3:
    two = mm[mm["sets_played"] == 2]
    three = mm[mm["sets_played"] == 3]
    if len(three):
        rate_three = three["won"].mean() * 100
        rate_two = two["won"].mean() * 100
        kpi("3-SET FADE", f"{rate_three:.0f}%",
            f"vs {rate_two:.0f}% in 2-set · {rate_three - rate_two:+.0f}pp",
            color=RED if rate_three < rate_two else t["ink"])
    else:
        kpi("3-SET FADE", "-", "no 3-set matches in view")
with c4:
    last5 = mm.tail(5)
    streak = "".join(["W" if w else "L" for w in last5["won"]])
    streak_str = " ".join(streak) if len(streak) else "-"
    kpi("CURRENT FORM", streak_str, f"last {len(last5)} matches")

st.write("")

# ---- 2x2 chart grid
r1c1, r1c2 = st.columns(2)

with r1c1:
    st.markdown("##### Rolling win rate · 5-match window")
    rw = rolling_win_rate(mm, window=5)
    rw["pct"] = rw["rolling"] * 100
    fig = go.Figure()
    fig.add_hline(y=50, line_dash="dot", line_color=t["zero"],
                  annotation_text="50%", annotation_position="right")
    fig.add_trace(go.Scatter(x=rw["date"], y=rw["pct"], mode="lines",
                              line=dict(color=BLUE, width=2.5),
                              fill="tozeroy",
                              fillcolor="rgba(14,165,233,0.1)",
                              hovertemplate="%{x|%d %b %Y}<br>Win rate: %{y:.0f}%"
                                            "<extra></extra>"))
    fig.update_layout(
        height=260, margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(showgrid=False),
        yaxis=dict(range=[0, 100], showgrid=True, ticksuffix="%"),
        showlegend=False
    )
    st.plotly_chart(themed_fig(fig), use_container_width=True,
                    config={"displayModeBar": False})

with r1c2:
    st.markdown("##### Win rate by partner")
    pw = partner_win_rate(mm)
    pw["pct"] = pw["win_rate"] * 100
    colors = [RED if r.is_worst else BLUE for r in pw.itertuples()]
    fig = go.Figure(go.Bar(
        y=pw["partner"], x=pw["pct"], orientation="h",
        marker=dict(color=colors),
        text=[f"{r['wins']}/{r['matches']} = {r['pct']:.0f}%" for _, r in pw.iterrows()],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Win rate: %{x:.0f}%<extra></extra>",
    ))
    fig.update_layout(
        height=260, margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(range=[0, 110], showgrid=False, visible=False),
        yaxis=dict(autorange="reversed"),
        showlegend=False
    )
    st.plotly_chart(themed_fig(fig), use_container_width=True,
                    config={"displayModeBar": False})
    best, worst = pw.iloc[0], pw.iloc[-1]
    section_caption(
        f"<b>{best['partner']}</b> highlighted as the strongest pairing "
        f"({best['win_rate']*100:.0f}%); <b>{worst['partner']}</b> as the weakest "
        f"({worst['win_rate']*100:.0f}%).")

r2c1, r2c2 = st.columns(2)

with r2c1:
    st.markdown("##### Shot DNA: winners vs errors")
    sd = shot_dna(mm)
    fig = go.Figure()
    fig.add_trace(go.Bar(y=sd["shot"], x=sd["winners"], orientation="h",
                         name="Winners", marker_color=BLUE,
                         text=sd["winners"], textposition="outside",
                         hovertemplate="<b>%{y}</b><br>Winners: %{x}<extra></extra>"))
    fig.add_trace(go.Bar(y=sd["shot"], x=-sd["errors"], orientation="h",
                         name="Errors", marker_color=RED,
                         text=sd["errors"], textposition="outside",
                         customdata=sd["errors"],
                         hovertemplate="<b>%{y}</b><br>Errors: %{customdata}"
                                       "<extra></extra>"))
    fig.update_layout(
        barmode="overlay", height=300,
        margin=dict(l=20, r=20, t=20, b=40),
        xaxis=dict(title="errors  ←  0  →  winners",
                   showgrid=False, zeroline=True),
        yaxis=dict(autorange="reversed"),
        showlegend=False,
    )
    st.plotly_chart(themed_fig(fig), use_container_width=True,
                    config={"displayModeBar": False})
    section_caption(
        f"{sd.iloc[0]['shot']} is your weapon (+{sd.iloc[0]['net']}). "
        f"{sd.iloc[-1]['shot']} bleeds points ({sd.iloc[-1]['net']}).")

with r2c2:
    st.markdown("##### Set-by-set fatigue")
    two = mm[mm["sets_played"] == 2]
    three = mm[mm["sets_played"] == 3]
    cats = ["2-set matches", "3-set matches"]
    rates = [two["won"].mean()*100 if len(two) else 0,
             three["won"].mean()*100 if len(three) else 0]
    counts = [len(two), len(three)]
    colors = [BLUE, RED if rates[1] < rates[0] else BLUE]
    fig = go.Figure(go.Bar(
        x=cats, y=rates, marker_color=colors,
        text=[f"{r:.0f}%<br><span style='font-size:11px;color:#6b7280;'>"
              f"n={c}</span>" for r, c in zip(rates, counts)],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Win rate: %{y:.0f}%<extra></extra>",
    ))
    fig.add_annotation(
        x=0.5, y=max(rates) + 8,
        text=f"<b>{rates[1] - rates[0]:+.0f} pp</b>",
        showarrow=False, font=dict(color=t["ink"], size=14), xref="x", yref="y")
    fig.update_layout(
        height=300, margin=dict(l=20, r=20, t=40, b=20),
        yaxis=dict(range=[0, 110], showgrid=True, ticksuffix="%"),
        xaxis=dict(showgrid=False),
        showlegend=False)
    st.plotly_chart(themed_fig(fig), use_container_width=True,
                    config={"displayModeBar": False})
    section_caption(
        "Annotation guides the user: the drop is the editorial focus, not the raw bars.")

# ---- Match table at the bottom
st.write("")
st.markdown("##### All matches in current view")
table = mm.sort_values("date", ascending=False).copy()
table["Date"] = table["date"].dt.strftime("%d %b %Y")
table["Score"] = table.apply(
    lambda r: f"{r.set1_us}-{r.set1_them} {r.set2_us}-{r.set2_them}" +
              (f" {int(r.set3_us)}-{int(r.set3_them)}"
               if pd.notna(r.set3_us) and str(r.set3_us) != "" else ""),
    axis=1)
display = table[["Date", "partner", "opponents", "Score", "result", "surface", "club"]]
display.columns = ["Date", "Partner", "Opponents", "Score", "Result",
                   "Surface", "Club"]
st.dataframe(display, hide_index=True, use_container_width=True, height=300)

# Export
st.write("")
col_dl, _ = st.columns([1, 3])
with col_dl:
    csv_bytes = mm.drop(columns=["won"] + [c for c in mm.columns if c.startswith("net_")],
                        errors="ignore").to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇ Download match log (CSV)",
        data=csv_bytes,
        file_name="my_matches.csv",
        mime="text/csv",
        use_container_width=True,
    )
