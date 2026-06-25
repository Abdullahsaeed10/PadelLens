"""Compare — your shot mix overlaid on a pro reference."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import (BLUE, GRAY, INK, LBLUE, LRED, MUTED, RED, SHOT_TYPES,
                   get_theme, inject_theme_css, load_my_matches,
                   section_caption, sidebar_player_name, themed_fig)

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

# Illustrative pro ERROR rates per match. There is no per-shot error feed in the
# API, so these share PRO_AVG's provenance: a documented efficiency benchmark for
# the demo, not measured data. They encode the one thing that defines a pro —
# a high winner-to-error ratio (few errors, smash a touch riskier than control
# shots) — so the head-to-head reference reads as a target to aim at.
PRO_ERR = {"forehand": 2.4, "backhand": 2.6, "smash": 2.8,
           "volley": 1.8, "bandeja": 1.6}


def per_match_rates(df):
    """Per-match mean winners and errors for each shot type, as two dicts."""
    win = {s: float(df[f"winners_{s}"].mean()) for s in SHOT_TYPES}
    err = {s: float(df[f"errors_{s}"].mean()) for s in SHOT_TYPES}
    return win, err


def head_to_head_fig(shots, a_win, a_err, b_win, b_err, a_label, b_label):
    """Grouped diverging 'tornado' comparing two players across the shot types.

    Same encoding as the My Stats Shot DNA chart — errors run left of zero,
    winners run right — but each shot holds TWO separate bars: series A (vivid
    blue/red) on top, series B (lighter blue/red) below. They sit side by side
    and never overlap, so both players' winners and errors stay readable.
    `offsetgroup` ties each player's winner bar and error bar onto one row;
    `barmode="group"` then gives the two players their own row within each shot.
    """
    fig = go.Figure()
    # Series A (you) — vivid, top row of each shot pair.
    fig.add_trace(go.Bar(y=shots, x=a_win, orientation="h", marker_color=BLUE,
                         name=a_label, legendgroup="a", offsetgroup="a",
                         text=[f"{v:.1f}" for v in a_win], textposition="outside",
                         textfont=dict(size=10),
                         hovertemplate=f"<b>%{{y}}</b><br>{a_label} winners: "
                                       f"%{{x:.1f}}<extra></extra>"))
    fig.add_trace(go.Bar(y=shots, x=[-e for e in a_err], orientation="h",
                         marker_color=RED, name=a_label, legendgroup="a",
                         offsetgroup="a", showlegend=False, customdata=a_err,
                         text=[f"{v:.1f}" for v in a_err], textposition="outside",
                         textfont=dict(size=10),
                         hovertemplate=f"<b>%{{y}}</b><br>{a_label} errors: "
                                       f"%{{customdata:.1f}}<extra></extra>"))
    # Series B (reference) — lighter, bottom row of each shot pair.
    fig.add_trace(go.Bar(y=shots, x=b_win, orientation="h", marker_color=LBLUE,
                         name=b_label, legendgroup="b", offsetgroup="b",
                         text=[f"{v:.1f}" for v in b_win], textposition="outside",
                         textfont=dict(size=10),
                         hovertemplate=f"<b>%{{y}}</b><br>{b_label} winners: "
                                       f"%{{x:.1f}}<extra></extra>"))
    fig.add_trace(go.Bar(y=shots, x=[-e for e in b_err], orientation="h",
                         marker_color=LRED, name=b_label, legendgroup="b",
                         offsetgroup="b", showlegend=False, customdata=b_err,
                         text=[f"{v:.1f}" for v in b_err], textposition="outside",
                         textfont=dict(size=10),
                         hovertemplate=f"<b>%{{y}}</b><br>{b_label} errors: "
                                       f"%{{customdata:.1f}}<extra></extra>"))
    # Pad the range so the outside value labels fit on both ends.
    max_w = max(max(a_win), max(b_win))
    max_e = max(max(a_err), max(b_err))
    pad = 0.22 * (max_w + max_e)
    fig.update_layout(
        barmode="group", bargap=0.28, bargroupgap=0.08, height=380,
        margin=dict(l=20, r=20, t=30, b=40),
        xaxis=dict(title="errors  ←  0  →  winners", showgrid=False,
                   zeroline=True, range=[-max_e - pad, max_w + pad]),
        yaxis=dict(autorange="reversed"),
        legend=dict(orientation="h", yanchor="bottom", y=1.0,
                    xanchor="right", x=1.0))
    return fig


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
        # No per-player error signal exists, so hold errors at the pro baseline.
        REF_ERR = PRO_ERR
        ref_label = f"vs {name}"
    else:
        REF = PRO_AVG
        REF_ERR = PRO_ERR
        ref_label = "vs Pro average"

# Per-match means for the user — winners feed the radar, both feed the
# head-to-head charts below.
me_win, me_err = per_match_rates(mm)
me_per_match = me_win

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

# ---------------------------------------------------------------------------
# Head-to-head charts — read the exact winner/error gap that the radar can only
# hint at. Two comparisons: you vs the chosen reference, and you vs yourself.
# ---------------------------------------------------------------------------
st.write("")
st.markdown("---")

ref_short = ref_label.replace("vs ", "")

# ---- You vs the reference (winners are real for you, illustrative for the pro;
#      pro errors are an illustrative efficiency benchmark — see the caption).
st.markdown(f"##### Head-to-head: winners & errors per match · {ref_short}")
a_win = [me_win[s.lower()] for s in shots_order]
a_err = [me_err[s.lower()] for s in shots_order]
b_win = [REF[s.lower()] for s in shots_order]
b_err = [REF_ERR[s.lower()] for s in shots_order]
fig = head_to_head_fig(shots_order, a_win, a_err, b_win, b_err,
                       player_name, ref_short)
st.plotly_chart(themed_fig(fig), use_container_width=True,
                config={"displayModeBar": False})
section_caption(
    f"The <b>top</b> bar of each shot is <b>{player_name}</b>; the <b>lighter</b> bar "
    f"below is the <b>{ref_short}</b> reference. Winners run right, errors left. Pro "
    "winner levels are illustrative values from match-level studies; the pro "
    "<b>error</b> rates are an illustrative efficiency benchmark (not in the API "
    "yet) — read them as a target, not measured data.")

# ---- You vs you: split the real log two ways (100% measured data, so this is
#      the comparison with no illustrative caveats).
st.write("")
st.markdown("##### Your own splits: where winners and errors come from")
split = st.radio(
    "Split my matches by",
    ["Result (won / lost)", "Surface (indoor / outdoor)", "Recent vs older"],
    horizontal=True)

if split.startswith("Result"):
    slice_a, slice_b = mm[mm["won"]], mm[~mm["won"]]
    label_a, label_b = "Won", "Lost"
elif split.startswith("Surface"):
    slice_a = mm[mm["surface"] == "indoor"]
    slice_b = mm[mm["surface"] == "outdoor"]
    label_a, label_b = "Indoor", "Outdoor"
else:
    mid = mm["date"].median()
    slice_a, slice_b = mm[mm["date"] >= mid], mm[mm["date"] < mid]
    label_a, label_b = "Recent", "Older"

if len(slice_a) == 0 or len(slice_b) == 0:
    st.info("Not enough matches on both sides of this split to compare.")
else:
    aw, ae = per_match_rates(slice_a)
    bw, be = per_match_rates(slice_b)
    a_win = [aw[s.lower()] for s in shots_order]
    a_err = [ae[s.lower()] for s in shots_order]
    b_win = [bw[s.lower()] for s in shots_order]
    b_err = [be[s.lower()] for s in shots_order]
    fig = head_to_head_fig(shots_order, a_win, a_err, b_win, b_err,
                           f"{label_a} (n={len(slice_a)})",
                           f"{label_b} (n={len(slice_b)})")
    st.plotly_chart(themed_fig(fig), use_container_width=True,
                    config={"displayModeBar": False})
    # Editorial: which shot's net balance (winners − errors) swings most between
    # the two slices — that is the shot the split is really about.
    swings = [(a_win[i] - a_err[i]) - (b_win[i] - b_err[i])
              for i in range(len(shots_order))]
    idx = max(range(len(shots_order)), key=lambda i: abs(swings[i]))
    better = label_a if swings[idx] >= 0 else label_b
    section_caption(
        f"Both sides are your measured matches. <b>{shots_order[idx]}</b> swings "
        f"most — net {abs(swings[idx]):.1f} winners/match better in your "
        f"<b>{better}</b> matches.")
