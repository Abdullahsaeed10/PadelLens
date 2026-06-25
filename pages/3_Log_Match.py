"""Log a Match — data entry form."""
import csv
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from utils import (DATA_DIR, inject_theme_css, load_my_matches,
                   sidebar_player_name)

st.set_page_config(page_title="Log a Match · PadelLens",
                   page_icon="➕", layout="wide")
inject_theme_css()

mm = load_my_matches()

st.title("Log a Match")
st.caption("Takes about 90 seconds. The shot tallies are optional.")

# Saved-confirmation banner. The save handler stores its message in session_state
# and reruns, so this renders at the TOP of the page — visible immediately even
# though the form and its Save button sit further down and reset on submit.
if "match_saved_msg" in st.session_state:
    st.success(st.session_state.pop("match_saved_msg"))
    st.toast("Your match has been saved!", icon="✅")
    st.balloons()

# Default values from history so the form feels familiar
known_partners = mm["partner"].unique().tolist()
known_opponents = mm["opponents"].unique().tolist()
known_clubs = mm["club"].unique().tolist()

with st.sidebar:
    sidebar_player_name()
    st.markdown("---")
    st.markdown("### Help")
    st.markdown(
        "**Why this matters.** The shot tallies are optional. Just filling "
        "date + score + partner is enough for the basic charts.")
    st.markdown(
        "**Tip.** Estimate roughly: 5-10 winners and 5-10 errors per set "
        "is normal at the amateur level.")
    st.markdown("**Privacy.** Logs stay on your machine. Nothing is sent.")


# The "3-set match" toggle lives OUTSIDE the form on purpose: widgets inside a
# form don't rerun until you press Save, so an in-form auto-detect can't unlock
# Set 3 while you type. This toggle reruns immediately and enables Set 3 below.
three_sets = st.toggle(
    "🎾 This was a 3-set match",
    key="three_sets",
    help="Turn on to enter the third (deciding) set. Leave off for a "
         "straight-sets win, e.g. 6-4, 6-2.",
)


with st.form("log_match", clear_on_submit=True):
    # Score goes first so the deciding set sits right under the 3-set toggle that
    # unlocks it (the toggle has to live just above the form to work).
    st.markdown("**Score**")
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        a1, b1 = st.columns(2)
        with a1: set1_us = st.number_input("Set 1 · us", 0, 7, value=0)
        with b1: set1_them = st.number_input("Set 1 · them", 0, 7, value=0)
    with sc2:
        a2, b2 = st.columns(2)
        with a2: set2_us = st.number_input("Set 2 · us", 0, 7, value=0)
        with b2: set2_them = st.number_input("Set 2 · them", 0, 7, value=0)
    with sc3:
        # Set 3 is unlocked by the "🎾 3-set match" toggle just above the form.
        a3, b3 = st.columns(2)
        with a3:
            set3_us = st.number_input("Set 3 · us", 0, 7, value=0,
                                      disabled=not three_sets,
                                      help="Turn on '3-set match' above to fill this")
        with b3:
            set3_them = st.number_input("Set 3 · them", 0, 7, value=0,
                                        disabled=not three_sets)

    # Set 3 only counts once it actually has a winner, so leaving the toggle on
    # but the third set at 0-0 still records a clean straight-sets win.
    played_set3 = three_sets and (set3_us != set3_them)

    # Auto-result preview — visibility of system status (Nielsen #1)
    us_sets = sum([set1_us > set1_them, set2_us > set2_them,
                   (played_set3 and set3_us > set3_them)])
    them_sets = sum([set1_us < set1_them, set2_us < set2_them,
                     (played_set3 and set3_us < set3_them)])
    if us_sets > them_sets:
        st.success(f"Auto result: **W** ({us_sets}-{them_sets} in sets)")
    elif them_sets > us_sets:
        st.error(f"Auto result: **L** ({us_sets}-{them_sets} in sets)")
    else:
        st.info("Auto result will update when the score is decisive.")

    st.markdown("**When & where**")
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        match_date = st.date_input("Date", value=date.today())
    with c2:
        club = st.text_input(
            "Club",
            value="",
            placeholder="e.g. Padel Bicocca",
            help="Type any club name. Past clubs: " + ", ".join(known_clubs[:4]),
        )
    with c3:
        surface = st.radio("Surface", ["indoor", "outdoor"], horizontal=True)

    st.markdown("**Players**")
    c1, c2 = st.columns(2)
    with c1:
        partner = st.text_input(
            "My partner",
            value="",
            placeholder="e.g. Luca",
            help="Past partners: " + ", ".join(known_partners[:5]),
        )
    with c2:
        opponents = st.text_input("Opponents", placeholder="e.g. Paolo & Matteo")

    with st.expander("Shot tallies (optional): for deeper analytics"):
        st.caption("Estimates are fine. Skip if you're in a hurry.")
        cols = st.columns(5)
        w_fh = cols[0].number_input("FH winners", 0, 30, value=0)
        w_bh = cols[1].number_input("BH winners", 0, 30, value=0)
        w_sm = cols[2].number_input("Smash winners", 0, 30, value=0)
        w_vo = cols[3].number_input("Volley winners", 0, 30, value=0)
        w_ba = cols[4].number_input("Bandeja winners", 0, 30, value=0)
        cols2 = st.columns(5)
        e_fh = cols2[0].number_input("FH errors", 0, 30, value=0)
        e_bh = cols2[1].number_input("BH errors", 0, 30, value=0)
        e_sm = cols2[2].number_input("Smash errors", 0, 30, value=0)
        e_vo = cols2[3].number_input("Volley errors", 0, 30, value=0)
        e_ba = cols2[4].number_input("Bandeja errors", 0, 30, value=0)

    duration = st.slider("Duration (minutes)", 30, 180, value=80, step=5)
    notes = st.text_input("Notes (optional)",
                          placeholder="e.g. 'Cold court, slow play'")

    submitted = st.form_submit_button("Save match", type="primary")


def append_to_csv(row: dict):
    """Append a row to my_matches.csv. Creates the file if missing."""
    p = DATA_DIR / "my_matches.csv"
    cols = ["match_id", "date", "partner", "opponents", "club", "surface",
            "sets_played", "set1_us", "set1_them", "set2_us", "set2_them",
            "set3_us", "set3_them", "result",
            "winners_forehand", "winners_backhand", "winners_smash",
            "winners_volley", "winners_bandeja",
            "errors_forehand", "errors_backhand", "errors_smash",
            "errors_volley", "errors_bandeja",
            "duration_min", "notes"]
    write_header = not p.exists()
    with open(p, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        if write_header:
            w.writeheader()
        w.writerow(row)


if submitted:
    if us_sets == them_sets:
        st.error("Score isn't decisive — one side must win 2 sets. For a split, "
                 "turn on '🎾 This was a 3-set match' and enter the deciding set.")
    elif not opponents.strip():
        st.error("Please enter the opponents' names.")
    elif not partner.strip():
        st.error("Please enter your partner's name.")
    elif not club.strip():
        st.error("Please enter the club name.")
    else:  # noqa: E501
        new_id = int(mm["match_id"].max()) + 1 if len(mm) else 1
        result = "W" if us_sets > them_sets else "L"
        sets_played = 3 if played_set3 else 2
        row = {
            "match_id": new_id, "date": match_date.isoformat(),
            "partner": partner, "opponents": opponents, "club": club,
            "surface": surface, "sets_played": sets_played,
            "set1_us": set1_us, "set1_them": set1_them,
            "set2_us": set2_us, "set2_them": set2_them,
            "set3_us": set3_us if played_set3 else "",
            "set3_them": set3_them if played_set3 else "",
            "result": result,
            "winners_forehand": w_fh, "winners_backhand": w_bh,
            "winners_smash": w_sm, "winners_volley": w_vo,
            "winners_bandeja": w_ba,
            "errors_forehand": e_fh, "errors_backhand": e_bh,
            "errors_smash": e_sm, "errors_volley": e_vo,
            "errors_bandeja": e_ba,
            "duration_min": duration, "notes": notes,
        }
        try:
            append_to_csv(row)
        except PermissionError:
            st.error(
                "Couldn't save — `my_matches.csv` looks like it's open in "
                "another program (e.g. Excel). Close it and press Save again.")
            st.stop()
        except Exception as exc:  # noqa: BLE001 — surface any write error, never fail silently
            st.error(f"Couldn't save the match: {exc}")
            st.stop()
        st.cache_data.clear()
        # Stash the confirmation and rerun so the banner shows at the top of the
        # page — the success then can't be missed below the long form, which
        # clears on submit.
        st.session_state["match_saved_msg"] = (
            f"✅ Your match has been saved! Match #{new_id} recorded as "
            f"**{result}** ({us_sets}-{them_sets} in sets). "
            f"Open **My Stats** to see your updated dashboard.")
        st.rerun()
