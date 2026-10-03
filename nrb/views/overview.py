"""Live dashboard: KPIs, trends and section breakdowns."""

import plotly.express as px
import streamlit as st

from nrb import config, data, ui
from nrb.application.services.load_reporting_data import ReportingDataService
from nrb.application.services.report_configuration import ReportConfigService
from nrb.domain import reporting_analytics


def render(
    report_config_service: ReportConfigService,
    reporting_data_service: ReportingDataService,
):
    ui.header("📊", "Live Dashboard", "Live totals straight from the daily form")
    _, res = data.load_or_stop(reporting_data_service)
    data.refresh_button(reporting_data_service.clear_cache)
    clean = res.clean
    if clean.empty:
        st.info("No clean submissions found yet.")
        return

    df, (start, end) = data.date_range_filter(clean)
    st.caption(
        f"Showing **{len(df)}** submissions from **{start}** to **{end}** · "
        f"latest submission: {clean['date'].max().date()}"
    )
    if df.empty:
        st.warning("No submissions in the selected range.")
        return

    cfg = report_config_service.get_report_config()

    blocks = [(g, b) for g in cfg["groups"] for b in g["blocks"]]
    metrics = reporting_analytics.overview_metrics(clean, df, start, end, cfg)
    cols = st.columns(len(blocks)) if blocks else []
    for col, metric in zip(cols, metrics):
        delta = (
            f"{metric.value - metric.previous_value:+,} vs prev. {metric.period_days}d"
            if metric.previous_value or metric.value
            else None
        )
        col.metric(metric.title.title(), f"{metric.value:,}", delta=delta)

    tab_trend, tab_sections, tab_detail = st.tabs(
        ["Trends", "Section activity", "Field breakdown"]
    )

    with tab_trend:
        titles = [b["title"] for _, b in blocks]
        chosen = st.multiselect("Show", titles, default=titles[:2])
        tdf = reporting_analytics.overview_trends(df, cfg, chosen)
        if not tdf.empty:
            fig = px.line(tdf, x="date", y="value", color="metric", markers=True)
            fig.update_layout(legend_title="", margin=dict(t=10))
            st.plotly_chart(fig, width="stretch")

    with tab_sections:
        counts, section_summary = reporting_analytics.section_activity(df)
        fig = px.bar(counts, x="date", y="submissions", color="section")
        fig.update_layout(legend_title="", margin=dict(t=10))
        st.plotly_chart(fig, width="stretch")
        st.dataframe(section_summary, width="stretch", hide_index=True)

    with tab_detail:
        section = st.selectbox("Section", list(config.SECTION_FIELDS))
        sdf = df[df["section"] == section]
        if sdf.empty:
            st.info("No submissions for this section in the selected range.")
        else:
            totals = reporting_analytics.section_field_totals(df, section)
            fig = px.bar(
                x=totals.values,
                y=totals.index,
                orientation="h",
                labels={"x": "Total", "y": ""},
            )
            fig.update_layout(margin=dict(t=10))
            st.plotly_chart(fig, width="stretch")
