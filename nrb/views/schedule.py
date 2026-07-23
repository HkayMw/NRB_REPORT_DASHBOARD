"""Scheduling: manage teams/sections, generate fair weekly allocations,
export the WhatsApp message."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from nrb import auth, config, db, scheduling, ui, weeks


def render():
    ui.header("🗓️", "Team Scheduling", "Fair weekly allocations and the WhatsApp message")
    if not auth.is_admin():
        st.warning("Scheduling is restricted to administrators — log in from the sidebar.")
        return

    tab_build, tab_teams, tab_history = st.tabs(
        ["Build schedule", "Manage teams", "History"])
    with tab_build:
        _build_tab()
    with tab_teams:
        _teams_tab()
    with tab_history:
        _history_tab()


# ---------------- build ----------------

def _build_tab():
    teams = db.list_teams(active_only=True)
    staff = db.list_staff(active_only=True)
    if not teams or not staff:
        st.info("Add active teams and staff first (Manage teams / Admin → Roster).")
        return

    next_monday = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 or 7)
    week_start = st.date_input("Week starting (Monday)", next_monday)
    if week_start.weekday() != 0:
        st.error("Pick a Monday.")
        return
    monday, friday = week_start, week_start + timedelta(days=4)

    names = [s["form_name"] for s in staff]
    absent = st.multiselect("Away this week (leave, travel, …)", names)
    available = [n for n in names if n not in absent]
    st.caption(f"{len(available)} staff available · team capacity "
               f"{sum(t['min_size'] for t in teams)}–{sum(t['max_size'] for t in teams)}")

    if st.button("⚖️ Generate fair allocation", type="primary"):
        result = scheduling.generate_schedule(available, teams, db.assignment_history())
        st.session_state["draft_schedule"] = {
            str(t["id"]): result["assignment"][t["id"]] for t in teams}
        if result["unplaced"]:
            st.warning("Everyone placed except (teams full): " + ", ".join(result["unplaced"]))

    draft = st.session_state.get("draft_schedule")
    if not draft:
        return

    st.subheader(f"Draft — Week of {weeks.pretty_range(monday, friday)}")
    st.caption("Adjust any team manually, then save.")
    edited = {}
    cols = st.columns(2)
    for i, t in enumerate(teams):
        with cols[i % 2]:
            edited[t["id"]] = st.multiselect(
                f"{t['name']}  (target {t['min_size']}–{t['max_size']})",
                names, default=[n for n in draft.get(str(t["id"]), []) if n in names],
                key=f"team_edit_{t['id']}",
            )
    counts = {}
    for members in edited.values():
        for m in members:
            counts[m] = counts.get(m, 0) + 1
    doubled = [m for m, c in counts.items() if c > 1]
    if doubled:
        st.warning("On more than one team: " + ", ".join(doubled))

    if st.button("💾 Save schedule for this week"):
        assignments = [
            (t["id"], name, pos)
            for t in teams for pos, name in enumerate(edited[t["id"]])
        ]
        db.save_schedule(monday.isoformat(), friday.isoformat(), assignments,
                         created_by=auth.current_user()["username"])
        st.session_state["draft_schedule"] = {
            str(tid): members for tid, members in edited.items()}
        st.success("Schedule saved — it now feeds the Compliance page.")

    full_names = {s["form_name"]: (s["full_name"] or s["form_name"]) for s in db.list_staff()}
    msg = scheduling.whatsapp_text(
        monday, [(t["name"], edited[t["id"]]) for t in teams], full_names)
    st.subheader("WhatsApp message")
    st.code(msg, language=None)


# ---------------- teams ----------------

def _teams_tab():
    st.caption("Teams are what people are allocated to; each team can be mapped "
               "to the form section its numbers land in.")
    teams = db.list_teams()
    staff_names = [s["form_name"] for s in db.list_staff(active_only=True)]
    sections = [""] + list(config.SECTION_FIELDS)

    options = ["➕ New team"] + [t["name"] for t in teams]
    pick = st.selectbox("Team", options)
    team = next((t for t in teams if t["name"] == pick), None)

    with st.form("team_form"):
        name = st.text_input("Team name", team["name"] if team else "")
        section = st.selectbox(
            "Reports as section", sections,
            index=sections.index(team["reports_as_section"])
            if team and team["reports_as_section"] in sections else 0)
        c1, c2, c3 = st.columns(3)
        min_size = c1.number_input("Min size", 0, 20, team["min_size"] if team else 1)
        max_size = c2.number_input("Max size", 1, 20, team["max_size"] if team else 3)
        sort_order = c3.number_input("Display order", 0, 99,
                                     team["sort_order"] if team else len(teams))
        pinned = st.multiselect(
            "Pinned members (always on this team)", staff_names,
            default=[p for p in (team["pinned_members"] if team else []) if p in staff_names])
        active = st.checkbox("Active", value=bool(team["active"]) if team else True)
        if st.form_submit_button("Save team"):
            if not name.strip():
                st.error("Team name is required.")
            elif max_size < min_size:
                st.error("Max size must be ≥ min size.")
            else:
                db.upsert_team(name, section, min_size, max_size, pinned,
                               active, sort_order, team_id=team["id"] if team else None)
                st.success("Saved.")
                st.rerun()

    if team and st.button(f"🗑️ Delete '{team['name']}'"):
        db.delete_team(team["id"])
        st.success("Deleted (including its past schedule entries).")
        st.rerun()

    if teams:
        view = pd.DataFrame([{
            "Team": t["name"], "Section": t["reports_as_section"],
            "Size": f"{t['min_size']}–{t['max_size']}",
            "Pinned": ", ".join(t["pinned_members"]),
            "Active": "✅" if t["active"] else "—",
        } for t in teams])
        st.dataframe(view, width="stretch", hide_index=True)


# ---------------- history ----------------

def _history_tab():
    scheds = db.list_schedules()
    if not scheds:
        st.info("No schedules saved yet.")
        return
    pick = st.selectbox("Saved week", [s["week_start"] for s in scheds],
                        format_func=lambda w: f"Week of {w}")
    sched = db.get_schedule(pick)
    rows = pd.DataFrame([{"Team": a["team_name"], "Staff": a["staff_name"]}
                         for a in sched["assignments"]])
    st.dataframe(rows, width="stretch", hide_index=True)

    full_names = {s["form_name"]: (s["full_name"] or s["form_name"]) for s in db.list_staff()}
    by_team = {}
    for a in sched["assignments"]:
        by_team.setdefault(a["team_name"], []).append(a["staff_name"])
    msg = scheduling.whatsapp_text(date.fromisoformat(pick), list(by_team.items()), full_names)
    st.code(msg, language=None)

    if st.button("🗑️ Delete this schedule"):
        db.delete_schedule(pick)
        st.rerun()

    # Fairness overview: how often has each person served on each team?
    hist = db.assignment_history()
    if hist:
        st.subheader("Fairness overview (all saved weeks)")
        teams_by_id = {t["id"]: t["name"] for t in db.list_teams()}
        hdf = pd.DataFrame(hist)
        hdf["team"] = hdf["team_id"].map(teams_by_id)
        pivot = hdf.pivot_table(index="staff_name", columns="team",
                                values="week_start", aggfunc="count", fill_value=0)
        st.dataframe(pivot, width="stretch")
