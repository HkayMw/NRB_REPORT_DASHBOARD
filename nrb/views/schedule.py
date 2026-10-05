"""Scheduling: manage teams/sections, generate fair weekly allocations,
export the WhatsApp message."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from nrb import auth, config, ui
from nrb.application.services.schedule_management import ScheduleService
from nrb.domain import roles, scheduling, weeks


def render(schedule_service: ScheduleService):
    ui.header(
        "🗓️", "Team Scheduling", "Fair weekly allocations and the WhatsApp message"
    )
    if not auth.can(roles.CREATE_SCHEDULE):
        st.warning(
            "Scheduling is restricted to administrators and clerks — log in "
            "from the sidebar."
        )
        return

    tab_build, tab_teams, tab_history = st.tabs(
        ["Build schedule", "Manage teams", "History"]
    )
    with tab_build:
        _build_tab(schedule_service, auth.current_user())
    with tab_teams:
        _teams_tab(schedule_service, auth.current_user())
    with tab_history:
        _history_tab(schedule_service, auth.current_user())


# ---------------- build ----------------


def _build_tab(schedule_service: ScheduleService, actor: dict | None):
    teams = schedule_service.list_teams(active_only=True)
    staff = schedule_service.list_staff(active_only=True)
    if not teams or not staff:
        st.info("Add active teams and staff first (Manage teams / Admin → Roster).")
        return

    next_monday = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 or 7)
    week_start = st.date_input("Week starting (Monday)", next_monday)
    if week_start.weekday() != 0:
        st.error("Pick a Monday.")
        return
    monday, friday = week_start, week_start + timedelta(days=4)
    if schedule_service.get_schedule(monday.isoformat()):
        if not auth.can(roles.EDIT_SCHEDULE):
            st.info(
                "This week already has a saved schedule (see History). "
                "Only administrators can change it."
            )
            return
        st.info(
            "This week already has a saved schedule — saving here replaces it. "
            "To adjust it instead, use History → Edit this schedule."
        )

    names = [s["form_name"] for s in staff]
    absent = st.multiselect("Away this week (leave, travel, …)", names)
    available = [n for n in names if n not in absent]
    st.caption(
        f"{len(available)} staff available · team capacity "
        f"{sum(t['min_size'] for t in teams)}–{sum(t['max_size'] for t in teams)}"
    )

    start_from = st.radio(
        "Start from",
        ["Fair allocation", "Move team packages from a saved week"],
        horizontal=True,
    )
    if start_from == "Fair allocation":
        if st.button("⚖️ Generate fair allocation", type="primary"):
            result = schedule_service.generate_schedule(available, teams)
            notes = []
            if result["unplaced"]:
                notes.append(
                    "Everyone placed except (teams full): "
                    + ", ".join(result["unplaced"])
                )
            _set_draft(result["assignment"], notes, teams)
    else:
        _packages_form(schedule_service, available, teams)

    draft = st.session_state.get("draft_schedule")
    if not draft:
        return
    for note in st.session_state.get("draft_notes", []):
        st.warning(note)

    st.subheader(f"Draft — Week of {weeks.pretty_range(monday, friday)}")
    st.caption("Adjust any team manually, then save.")
    edited = {}
    cols = st.columns(2)
    for i, t in enumerate(teams):
        with cols[i % 2]:
            edited[t["id"]] = st.multiselect(
                f"{t['name']}  (target {t['min_size']}–{t['max_size']})",
                available,
                default=[n for n in draft.get(str(t["id"]), []) if n in available],
                key=f"team_edit_{t['id']}",
            )
    counts: dict[str, int] = {}
    for members in edited.values():
        for m in members:
            counts[m] = counts.get(m, 0) + 1
    doubled = [m for m, c in counts.items() if c > 1]
    if doubled:
        st.warning("On more than one team: " + ", ".join(doubled))
    unassigned = [n for n in available if n not in counts]
    if unassigned:
        st.caption("Available but not on any team yet: " + ", ".join(unassigned))

    if st.button("💾 Save schedule for this week"):
        assignments = [
            (t["id"], name, pos)
            for t in teams
            for pos, name in enumerate(edited[t["id"]])
        ]
        try:
            schedule_service.save_schedule(
                monday.isoformat(),
                friday.isoformat(),
                assignments,
                available_staff=available,
                actor=actor,
            )
            st.session_state["draft_schedule"] = {
                str(tid): members for tid, members in edited.items()
            }
            st.success("Schedule saved — it now feeds the Compliance page.")
        except (ValueError, PermissionError) as error:
            st.error(f"Schedule was not saved: {error}")

    full_names = {
        s["form_name"]: (s["full_name"] or s["form_name"])
        for s in schedule_service.list_staff()
    }
    msg = scheduling.whatsapp_text(
        monday, [(t["name"], edited[t["id"]]) for t in teams], full_names
    )
    st.subheader("WhatsApp message")
    st.code(msg, language=None)


def _set_draft(assignment: dict, notes: list[str], teams: list[dict]):
    st.session_state["draft_schedule"] = {
        str(t["id"]): list(assignment.get(str(t["id"]), [])) for t in teams
    }
    st.session_state["draft_notes"] = notes
    # Drop the editors' previous picks so they show the new draft.
    for t in teams:
        st.session_state.pop(f"team_edit_{t['id']}", None)


def _packages_form(
    schedule_service: ScheduleService, available: list[str], teams: list[dict]
):
    scheds = schedule_service.list_schedules()
    if not scheds:
        st.info("No saved schedules yet — use a fair allocation first.")
        return
    source_week = st.selectbox(
        "Take packages from",
        [s["week_start"] for s in scheds],
        format_func=lambda w: f"Week of {w}",
        key="pkg_source",
    )
    source = schedule_service.get_schedule(source_week)
    if source is None:
        st.warning("That schedule is no longer available. Refresh the page.")
        return

    packages: dict[str, dict] = {}
    for a in source["assignments"]:
        package = packages.setdefault(
            str(a["team_id"]), {"name": a["team_name"], "members": []}
        )
        package["members"].append(a["staff_name"])

    st.caption(
        "Choose where each package goes this week. Pinned members stay on "
        "their own team, away members leave a gap, and anyone beyond a "
        "team's maximum is left unplaced — adjust those in the draft below."
    )
    team_names = {str(t["id"]): t["name"] for t in teams}
    choices = ["— don't carry"] + list(team_names)
    moves = {}
    for team_id, package in packages.items():
        target = st.selectbox(
            f"{package['name']}: {', '.join(package['members'])}",
            choices,
            index=choices.index(team_id) if team_id in team_names else 0,
            format_func=lambda c: team_names.get(c, c),
            key=f"pkg_move_{source_week}_{team_id}",
        )
        if target in team_names:
            moves[team_id] = target

    if st.button("📦 Build draft from packages", type="primary"):
        try:
            result = schedule_service.carry_packages(
                source_week, moves, available, teams
            )
        except ValueError as error:
            st.error(str(error))
            return
        _set_draft(result["assignment"], result["notes"], teams)


# ---------------- teams ----------------


def _teams_tab(schedule_service: ScheduleService, actor: dict | None):
    st.caption(
        "Teams are what people are allocated to; each team can be mapped "
        "to the form section its numbers land in."
    )
    teams = schedule_service.list_teams()
    staff_names = [
        s["form_name"] for s in schedule_service.list_staff(active_only=True)
    ]
    sections = [""] + list(config.SECTION_FIELDS)

    if auth.is_admin():
        _team_editor(schedule_service, actor, teams, staff_names, sections)
    else:
        st.caption("Only administrators can change teams.")

    if teams:
        view = pd.DataFrame(
            [
                {
                    "Team": t["name"],
                    "Section": t["reports_as_section"],
                    "Size": f"{t['min_size']}–{t['max_size']}",
                    "Pinned": ", ".join(t["pinned_members"]),
                    "Active": "✅" if t["active"] else "—",
                }
                for t in teams
            ]
        )
        st.dataframe(view, width="stretch", hide_index=True)


def _team_editor(
    schedule_service: ScheduleService,
    actor: dict | None,
    teams: list[dict],
    staff_names: list[str],
    sections: list[str],
):
    options = ["➕ New team"] + [t["name"] for t in teams]
    pick = st.selectbox("Team", options)
    team = next((t for t in teams if t["name"] == pick), None)

    with st.form("team_form"):
        name = st.text_input("Team name", team["name"] if team else "")
        section = st.selectbox(
            "Reports as section",
            sections,
            index=sections.index(team["reports_as_section"])
            if team and team["reports_as_section"] in sections
            else 0,
        )
        c1, c2, c3 = st.columns(3)
        min_size = c1.number_input("Min size", 0, 20, team["min_size"] if team else 1)
        max_size = c2.number_input("Max size", 1, 20, team["max_size"] if team else 3)
        sort_order = c3.number_input(
            "Display order", 0, 99, team["sort_order"] if team else len(teams)
        )
        pinned = st.multiselect(
            "Pinned members (always on this team)",
            staff_names,
            default=[
                p for p in (team["pinned_members"] if team else []) if p in staff_names
            ],
        )
        active = st.checkbox("Active", value=bool(team["active"]) if team else True)
        if st.form_submit_button("Save team"):
            if not name.strip():
                st.error("Team name is required.")
            elif max_size < min_size:
                st.error("Max size must be ≥ min size.")
            else:
                schedule_service.upsert_team(
                    name,
                    section,
                    min_size,
                    max_size,
                    pinned,
                    active,
                    sort_order,
                    team["id"] if team else None,
                    actor,
                )
                st.success("Saved.")
                st.rerun()

    if team and st.button(f"🗑️ Delete '{team['name']}'"):
        schedule_service.delete_team(team["id"], actor)
        st.success("Deleted (including its past schedule entries).")
        st.rerun()


# ---------------- history ----------------


def _history_tab(schedule_service: ScheduleService, actor: dict | None):
    scheds = schedule_service.list_schedules()
    if not scheds:
        st.info("No schedules saved yet.")
        return
    pick = st.selectbox(
        "Saved week",
        [s["week_start"] for s in scheds],
        format_func=lambda w: f"Week of {w}",
    )
    sched = schedule_service.get_schedule(pick)
    if sched is None:
        st.warning("That schedule is no longer available. Refresh the page.")
        return
    rows = pd.DataFrame(
        [
            {"Team": a["team_name"], "Staff": a["staff_name"]}
            for a in sched["assignments"]
        ]
    )
    st.dataframe(rows, width="stretch", hide_index=True)

    full_names = {
        s["form_name"]: (s["full_name"] or s["form_name"])
        for s in schedule_service.list_staff()
    }
    by_team: dict[str, list[str]] = {}
    for a in sched["assignments"]:
        by_team.setdefault(a["team_name"], []).append(a["staff_name"])
    msg = scheduling.whatsapp_text(
        date.fromisoformat(pick), list(by_team.items()), full_names
    )
    st.code(msg, language=None)

    if auth.can(roles.EDIT_SCHEDULE):
        _edit_schedule(schedule_service, actor, pick, sched["assignments"])

    # Fairness overview: how often has each person served on each team?
    hist = schedule_service.assignment_history()
    if hist:
        st.subheader("Fairness overview (all saved weeks)")
        teams_by_id = {t["id"]: t["name"] for t in schedule_service.list_teams()}
        hdf = pd.DataFrame(hist)
        hdf["team"] = hdf["team_id"].map(teams_by_id)
        pivot = hdf.pivot_table(
            index="staff_name",
            columns="team",
            values="week_start",
            aggfunc="count",
            fill_value=0,
        )
        st.dataframe(pivot, width="stretch")


def _edit_schedule(
    schedule_service: ScheduleService,
    actor: dict | None,
    week_start: str,
    assignments: list[dict],
):
    teams = schedule_service.list_teams(active_only=True)
    names = [s["form_name"] for s in schedule_service.list_staff(active_only=True)]
    with st.expander("✏️ Edit this schedule"):
        team_ids = {str(t["id"]) for t in teams}
        dropped = [a["staff_name"] for a in assignments if a["team_id"] not in team_ids]
        if dropped:
            st.caption(
                "On teams that are no longer active (removed when you save): "
                + ", ".join(dropped)
            )
        edited = {}
        cols = st.columns(2)
        for i, t in enumerate(teams):
            current = [
                a["staff_name"]
                for a in assignments
                if a["team_id"] == str(t["id"]) and a["staff_name"] in names
            ]
            with cols[i % 2]:
                edited[t["id"]] = st.multiselect(
                    f"{t['name']}  (target {t['min_size']}–{t['max_size']})",
                    names,
                    default=current,
                    key=f"sched_edit_{week_start}_{t['id']}",
                )
        if st.button("💾 Save changes", key=f"sched_save_{week_start}"):
            new_assignments = [
                (t["id"], name, pos)
                for t in teams
                for pos, name in enumerate(edited[t["id"]])
            ]
            # Everyone placed counts as available; validation rejects doubles.
            available = [name for _, name, _ in new_assignments]
            monday = date.fromisoformat(week_start)
            try:
                schedule_service.save_schedule(
                    week_start,
                    (monday + timedelta(days=4)).isoformat(),
                    new_assignments,
                    available_staff=list(dict.fromkeys(available)),
                    actor=actor,
                )
            except (ValueError, PermissionError) as error:
                st.error(f"Schedule was not saved: {error}")
            else:
                st.success("Schedule updated.")
                st.rerun()

    if st.button("🗑️ Delete this schedule"):
        try:
            schedule_service.delete_schedule(week_start, actor)
        except PermissionError as error:
            st.error(str(error))
        else:
            st.rerun()
