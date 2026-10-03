"""Who reported what: section coverage grid, per-person activity,
and scheduled-vs-reported comparison."""

import pandas as pd
import streamlit as st

from nrb import data, ui
from nrb.application.services.load_reporting_data import ReportingDataService
from nrb.application.services.schedule_management import ScheduleService
from nrb.domain import reporting_analytics


def render(
    schedule_service: ScheduleService,
    reporting_data_service: ReportingDataService,
):
    ui.header(
        "✅", "Reporting Compliance", "Who reported, what was covered, what's missing"
    )
    _, res = data.load_or_stop(reporting_data_service)
    data.refresh_button(reporting_data_service.clear_cache)
    clean = res.clean
    if clean.empty:
        st.info("No clean submissions found yet.")
        return
    df, (start, end) = data.date_range_filter(clean, key="comp_range")

    tab_grid, tab_people, tab_sched = st.tabs(
        ["Section coverage", "People", "Scheduled vs reported"]
    )

    with tab_grid:
        st.caption("Submissions per section per day. Blank weekday = nobody reported.")
        if df.empty:
            st.info("No data in range.")
        else:
            grid, missing = reporting_analytics.compliance_section_coverage(
                df, start, end
            )

            def _color(v):
                return (
                    "background-color:#fee2e2;color:#991b1b"
                    if v == 0
                    else "background-color:#dcfce7;color:#166534"
                )

            st.dataframe(
                grid.style.map(_color),
                width="stretch",
                height=min(38 * len(grid) + 40, 640),
            )
            st.caption(f"⚠️ {missing} section-days with no submission in this range.")

    with tab_people:
        people, per = reporting_analytics.compliance_people_activity(df)
        if people.empty:
            st.info("No data in range.")
        else:
            st.dataframe(per, width="stretch", hide_index=True)

            active = {
                s["form_name"] for s in schedule_service.list_staff(active_only=True)
            }
            silent = sorted(active - set(per["person"]))
            if silent:
                st.warning("No submissions in this range from: " + ", ".join(silent))

            who = st.selectbox("Inspect a person", per["person"])
            detail = reporting_analytics.compliance_person_detail(people, who)
            st.dataframe(detail, width="stretch", hide_index=True)

    with tab_sched:
        scheds = schedule_service.list_schedules()
        if not scheds:
            st.info("No saved schedules yet — create one on the Scheduling page.")
            return
        pick = st.selectbox(
            "Week",
            [s["week_start"] for s in scheds],
            format_func=lambda ws: f"Week of {ws}",
        )
        sched = schedule_service.get_schedule(pick)
        if sched is None:
            st.warning("That schedule is no longer available. Refresh the page.")
            return
        rows, extras = reporting_analytics.scheduled_reporting_comparison(clean, sched)
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        if extras:
            st.caption("Also reported but not on the schedule: " + ", ".join(extras))
