"""Who reported what: daily scheduled-vs-reported check, section coverage
grid, and per-person activity."""

from datetime import timedelta

import streamlit as st

from nrb import config, data, ui
from nrb.application.services.load_reporting_data import ReportingDataService
from nrb.application.services.schedule_management import ScheduleService
from nrb.domain import reporting_analytics, weeks

_STATUS_STYLES = {
    reporting_analytics.REPORTED: "background-color:#dcfce7;color:#166534",
    reporting_analytics.OTHER_SECTION: "background-color:#fef3c7;color:#92400e",
    reporting_analytics.MISSING: "background-color:#fee2e2;color:#991b1b",
}


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
        st.info(
            "No clean submissions found yet. If Data quality lists rows under "
            "unknown names, add those names in Admin -> Roster."
        )
        return
    df, (start, end) = data.date_range_filter(clean, key="comp_range")

    tab_daily, tab_grid, tab_people = st.tabs(
        ["Daily (by week)", "Section coverage", "People"]
    )

    with tab_daily:
        _render_daily(schedule_service, clean)

    with tab_grid:
        st.caption("Submissions per section per day. Red = nobody reported.")
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


def _render_daily(schedule_service: ScheduleService, clean):
    today = config.today()
    picked = st.date_input("Week containing", value=today, key="comp_week")
    monday, _ = weeks.work_week_of(picked)
    st.caption(weeks.pretty_range(monday, monday + timedelta(days=6)))

    sched = schedule_service.schedule_for_week(monday)
    if sched is not None:
        assignments = sched["assignments"]
    else:
        st.info(
            "No saved schedule for this week — checking every active staff "
            "member for a submission on each day."
        )
        assignments = [
            {"team_name": "—", "staff_name": s["form_name"]}
            for s in schedule_service.list_staff(active_only=True)
        ]
    if not assignments:
        st.info("Nobody to check for this week.")
        return

    week = reporting_analytics.daily_reporting_compliance(
        clean, monday, assignments, today
    )

    cols = st.columns(7)
    for col, day in zip(cols, week.days):
        if day.enforced:
            value = f"{day.reported}/{day.expected}"
        elif day.day > today:
            value = "—"
        else:
            value = f"{day.reported} worked"
        col.metric(day.day.strftime("%a %d"), value)

    day_columns = [reporting_analytics.day_column(day.day) for day in week.days]
    st.dataframe(
        week.grid.style.map(lambda v: _STATUS_STYLES.get(v, ""), subset=day_columns),
        width="stretch",
        hide_index=True,
    )
    st.caption(
        "✅ reported for their team's section · ⚠️ reported, but for another "
        "section · ❌ no report on a weekday · · day not reached yet · "
        "blank weekend = not required"
    )

    shown = st.selectbox(
        "Inspect a day",
        week.days,
        index=(today - monday).days if 0 <= (today - monday).days < 7 else 0,
        format_func=lambda d: d.day.strftime("%A %d %B"),
        key="comp_day",
    )
    reports = reporting_analytics.day_reports(clean, shown.day)
    if reports.empty:
        st.info("No submissions on this day.")
    else:
        st.dataframe(reports, width="stretch", hide_index=True)
    if shown.unscheduled and sched is not None:
        st.caption(
            "Reported but not on this week's schedule: " + ", ".join(shown.unscheduled)
        )
