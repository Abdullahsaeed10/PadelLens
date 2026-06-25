"""Compare — your shot mix overlaid on a pro reference."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import (BLUE, GRAY, INK, MUTED, RED, SHOT_TYPES, get_theme,
                   inject_theme_css, load_my_matches, section_caption,
                   sidebar_player_name, themed_fig)

st.set_page_config(page_title="Compare · PadelLens",
                   page_icon="⚖️", layout="wide")
inject_theme_css()
t = get_theme()

mm = load_my_matches()

st.title("Compare your game to the pros")
st.caption("We're not saying you should play like them. We're showing where the "
           "biggest gaps are.")

# Hard-coded pro reference values (winners per match, from documented pro
# match-level studies of Premier Padel matches — see brief §2.1).
# These are conservative, illustrative values for the demo.
PRO_AVG = {"forehand": 5.2, "backhand": 5.8, "smash": 4.1,
           "volley": 6.5, "bandeja": 4.2}

with st.sidebar:
    player_name = sidebar_player_name()
    st.markdown("---")
    st.markdown("### Reference")
    mode = st.radio("Compare against", ["Pro average", "A specific player"])
    if mode == "A specific player":
        from utils import load_pro_players
        pp = load_pro_players()
        name = st.selectbox("Player", pp["name"].tolist())
        st.info("In v1 the per-player shot averages aren't in the API yet, so "
                "the chart falls back to the pro average + a tilt for that "
                "player's playing style (drive/reves).")
        # tiny tilt to make the per-player option feel distinct
        sel = pp[pp["name"] == name].iloc[0]
        tilt = 1.1 if sel["side"] == "D" else 0.95
        REF = {k: v * tilt for k, v in PRO_AVG.items()}
        ref_label = f"vs {name}"
    else:
        REF = PRO_AVG
        ref_label = "vs Pro average"

# Per-match means for the user
me_per_match = {s: float(mm[f"winners_{s}"].mean()) for s in SHOT_TYPES}

# ---- Radar
shots_order = ["Forehand", "Backhand", "Smash", "Volley", "Bandeja"]
me_vals = [me_per_match[s.lower()] for s in shots_order]
ref_vals = [REF[s.lower()] for s in shots_order]
gaps = [m - r for m, r in zip(me_vals, ref_vals)]
biggest_gap_idx = gaps.index(min(gaps))

left, right = st.columns([2, 1])

with left:
    st.markdown("##### Shot-mix radar: winners per match")
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=ref_vals + [ref_vals[0]],
                                  theta=shots_order + [shots_order[0]],
                                  fill="toself", name="Pro reference",
                                  line=dict(color=GRAY, width=1.5),
                                  fillcolor="rgba(148,163,184,0.3)"))
    fig.add_trace(go.Scatterpolar(r=me_vals + [me_vals[0]],
                                  theta=shots_order + [shots_order[0]],
                                  fill="toself", name=player_name,
                                  line=dict(color=BLUE, width=2),
                                  fillcolor="rgba(14,165,233,0.35)"))
    max_val = max(max(me_vals), max(ref_vals)) + 1
    fig.update_layout(
        polar=dict(bgcolor=t["card"],
                   radialaxis=dict(range=[0, max_val],
                                   showgrid=True, gridcolor=t["grid"],
                                   showline=False),
                   angularaxis=dict(showgrid=True, gridcolor=t["grid"])),
        height=500, margin=dict(l=40, r=40, t=40, b=40),
        showlegend=True, legend=dict(orientation="h", yanchor="bottom",
                                     y=-0.1, xanchor="center", x=0.5))
    st.plotly_chart(themed_fig(fig), use_container_width=True,
                    config={"displayModeBar": False})
    section_caption(
        f"<b>Biggest gap:</b> {shots_order[biggest_gap_idx]} "
        f"({gaps[biggest_gap_idx]:+.1f} winners/match). This is your focus.")

with right:
    st.markdown(f"##### Biggest gaps · {ref_label}")
    # Sort shots by gap (worst gap first)
    rows = sorted(zip(shots_order, me_vals, ref_vals, gaps),
                  key=lambda x: x[3])
    for i, (shot, me, ref, gap) in enumerate(rows):
        if gap < -1.0:
            bg, border, color = t["bad_bg"], t["bad_br"], t["bad_fg"]
            verdict = "needs work"
        elif gap < 0:
            bg, border, color = t["warn_bg"], t["warn_br"], t["warn_fg"]
            verdict = "slight gap"
        else:
            bg, border, color = t["good_bg"], t["good_br"], t["good_fg"]
            verdict = "above reference"

        if gap >= 0:
            tip = f"You're above the reference: {shot.lower()} is a strength, keep using it."
        elif shot == "Forehand":
            tip = "Drill: cross-court forehand rallies, 20 balls per set. Focus on flat contact."
        elif shot == "Backhand":
            tip = "Drill: wall repetitions with a partner. Prioritise stability before power."
        elif shot == "Smash":
            tip = "Drill: defensive smash from the back glass, 3 sets per session. Aim for depth."
        elif shot == "Volley":
            tip = "Drill: touch volleys at the net. Soft hands beat power at the amateur level."
        elif shot == "Bandeja":
            tip = "Drill: bandeja from mid-court targeting the corners, 15 reps each side."
        else:
            tip = "Focus on consistency in training before adding power."

        st.markdown(
            f"""<div style='padding:14px 16px; background:{bg};
                       border:1px solid {border}; border-radius:8px;
                       margin-bottom:10px;'>
              <div style='font-size:14px; font-weight:600; color:{color};'>{shot}</div>
              <div style='font-size:12px; color:{t['muted']}; margin-top:4px;'>
                  You: {me:.1f} winners/match · {ref_label.replace('vs ', '')}: {ref:.1f}</div>
              <div style='font-size:12px; color:{t['muted']}; margin-top:2px;'>
                  Gap: <b>{gap:+.1f}</b> · {verdict}</div>
              <div style='font-size:12px; color:{t['muted']}; margin-top:6px;
                          font-style:italic;'>{tip}</div>
            </div>""",
            unsafe_allow_html=True)
