"""Monthly report: on-screen preview + one-click Excel export."""

import pandas as pd
import streamlit as st

from nrb import auth, data, ui
from nrb.application.services.generate_monthly_report import MonthlyReportService
from nrb.application.services.load_reporting_data import ReportingDataService
from nrb.application.services.report_footer import ReportFooterService
from nrb.application.services.report_configuration import ReportConfigService
from nrb.domain import reporting_analytics
from nrb.domain import weeks


def render(
    report_config_service: ReportConfigService,
    report_footer_service: ReportFooterService,
    reporting_data_service: ReportingDataService,
    monthly_report_service: MonthlyReportService,
):
    ui.header(
        "📑", "Monthly Report", "Preview any month and download the office workbook"
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

    months = sorted(clean["date"].dt.to_period("M").unique(), reverse=True)
    pick = st.selectbox(
        "Report month", months, format_func=lambda p: p.strftime("%B %Y")
    )
    year, month = pick.year, pick.month
    cfg = report_config_service.get_report_config()
    preview = reporting_analytics.build_monthly_preview(clean, year, month, cfg)
    mdf = preview.month_data
    st.caption(
        f"{len(mdf)} submissions found for {pick.strftime('%B %Y')} · "
        f"{len(preview.weeks)} weeks (Mon–Sun, month days only)"
    )

    # ---- Summary preview (mirrors the exported Report Summary sheet) ----
    st.dataframe(preview.summary, width="stretch")

    with st.expander("Week-by-week detail"):
        for week in preview.weeks:
            st.markdown(
                f"**Week {week.number}** — {weeks.pretty_range(week.start, week.end)} "
                f"({week.submission_count} submissions)"
            )
            block_cols = st.columns(2)
            for index, block in enumerate(week.blocks):
                rows = pd.DataFrame(block.rows, columns=[block.title, "Total"])
                if block.total_label:
                    rows.loc[len(rows)] = [block.total_label, block.total]
                with block_cols[index % 2]:
                    st.dataframe(rows, width="stretch", hide_index=True)

    # ---- Export ----
    st.divider()
    if not auth.is_logged_in():
        st.info("Log in (sidebar) to download the Excel report.")
        return

    footer = report_footer_service.get_footer()
    if auth.is_admin():
        with st.expander("Report footer text (saved for future months)"):
            planned_new = st.text_area(
                "Planned activities", footer.planned_activities, height=120
            )
            compiled_new = st.text_area("Compiled by", footer.compiled_by, height=70)
            if st.button("Save footer text"):
                footer = report_footer_service.save_footer(
                    planned_new, compiled_new, auth.current_user()
                )
                st.success("Saved.")

    report = monthly_report_service.generate(
        mdf,
        year,
        month,
        cfg,
        footer.planned_activities,
        footer.compiled_by,
    )
    st.download_button(
        "⬇️ Download Excel report",
        data=report.workbook,
        file_name=report.filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )
    st.caption(
        "Values only — no imported-data sheet to detach, no week dates to edit, "
        "already named correctly."
    )
