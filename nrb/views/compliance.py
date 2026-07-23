"""Who reported what: section coverage grid, per-person activity,
and scheduled-vs-reported comparison."""

import pandas as pd
import streamlit as st

from nrb import cleaning, config, data, db, scheduling, ui, weeks


def render():
    ui.header("✅", "Reporting Compliance", "Who reported, what was covered, what's missing")
    _, res = data.load_or_stop()
    data.refresh_button()
    clean = res.clean
    if clean.empty:
        st.info("No clean submissions found yet.")
        return
    df, (start, end) = data.date_range_filter(clean, key="comp_range")

    tab_grid, tab_people, tab_sched = st.tabs(
        ["Section coverage", "People", "Scheduled vs reported"])

    with tab_grid:
        st.caption("Submissions per section per day. Blank weekday = nobody reported.")
        if df.empty:
            st.info("No data in range.")
        else:
            all_days = pd.date_range(start, end, freq="D")
            grid = (
                df.groupby(["date", "section"]).size().unstack(fill_value=0)
                .reindex(all_days, fill_value=0)
            )
            for s in config.SECTION_FIELDS:
                if s not in grid.columns:
                    grid[s] = 0
            grid = grid[[s for s in config.SECTION_FIELDS]]
            grid.index = grid.index.strftime("%a %d %b %Y")

            def _color(v):
                return "background-color:#fee2e2;color:#991b1b" if v == 0 else \
                       "background-color:#dcfce7;color:#166534"
            st.dataframe(grid.style.map(_color), width="stretch",
                         height=min(38 * len(grid) + 40, 640))
            missing = int((grid == 0).sum().sum())
            st.caption(f"⚠️ {missing} section-days with no submission in this range.")

    with tab_people:
        people = cleaning.explode_people(df)
        if people.empty:
            st.info("No data in range.")
        else:
            per = (people.groupby("person").agg(
                submissions=("date", "count"),
                days=("date", "nunique"),
                sections=("section", lambda s: ", ".join(sorted(s.unique()))),
                last_report=("date", "max"),
            ).sort_values("submissions", ascending=False).reset_index())
            per["last_report"] = per["last_report"].dt.date
            st.dataframe(per, width="stretch", hide_index=True)

            active = {s["form_name"] for s in db.list_staff(active_only=True)}
            silent = sorted(active - set(per["person"]))
            if silent:
                st.warning("No submissions in this range from: " + ", ".join(silent))

            who = st.selectbox("Inspect a person", per["person"])
            pdf = people[people["person"] == who]
            show = pdf[["date", "section", config.NAME_COL]].copy()
            show["date"] = show["date"].dt.date
            st.dataframe(show.sort_values("date", ascending=False),
                         width="stretch", hide_index=True)

    with tab_sched:
        scheds = db.list_schedules()
        if not scheds:
            st.info("No saved schedules yet — create one on the Scheduling page.")
            return
        pick = st.selectbox(
            "Week", [s["week_start"] for s in scheds],
            format_func=lambda ws: f"Week of {ws}",
        )
        sched = db.get_schedule(pick)
        wk_start = pd.Timestamp(pick)
        wk_end = wk_start + pd.Timedelta(days=6)
        week_people = cleaning.explode_people(
            clean[(clean["date"] >= wk_start) & (clean["date"] <= wk_end)])
        reported = set(week_people["person"]) if not week_people.empty else set()
        rows = []
        for a in sched["assignments"]:
            rows.append({
                "Team": a["team_name"],
                "Staff": a["staff_name"],
                "Reported this week": "✅" if a["staff_name"] in reported else "❌",
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        extras = reported - {a["staff_name"] for a in sched["assignments"]}
        if extras:
            st.caption("Also reported but not on the schedule: " + ", ".join(sorted(extras)))
