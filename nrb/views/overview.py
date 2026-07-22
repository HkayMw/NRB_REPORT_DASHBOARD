"""Live dashboard: KPIs, trends and section breakdowns."""

import pandas as pd
import plotly.express as px
import streamlit as st

from nrb import config, data, reportcfg


def render():
    st.title("📊 Live Dashboard")
    _, res = data.load_or_stop()
    data.refresh_button()
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

    cfg = reportcfg.get_report_config()

    # KPI row: one metric per report block (config-driven).
    blocks = [(g, b) for g in cfg["groups"] for b in g["blocks"]]
    cols = st.columns(len(blocks)) if blocks else []
    for col, (g, b) in zip(cols, blocks):
        val = reportcfg.compute_block(df, b)["total"]
        col.metric(b["title"].title(), f"{val:,}")

    tab_trend, tab_sections, tab_detail = st.tabs(
        ["Trends", "Section activity", "Field breakdown"])

    with tab_trend:
        titles = [b["title"] for _, b in blocks]
        chosen = st.multiselect("Show", titles, default=titles[:2])
        rows = []
        for g, b in blocks:
            if b["title"] not in chosen:
                continue
            fields = [f for r in b["rows"] for f in r["fields"]]
            daily = df.groupby("date")[fields].sum().sum(axis=1)
            for d, v in daily.items():
                rows.append({"date": d, "metric": b["title"], "value": v})
        if rows:
            tdf = pd.DataFrame(rows)
            fig = px.line(tdf, x="date", y="value", color="metric", markers=True)
            fig.update_layout(legend_title="", margin=dict(t=10))
            st.plotly_chart(fig, width="stretch")

    with tab_sections:
        counts = df.groupby(["date", "section"]).size().reset_index(name="submissions")
        fig = px.bar(counts, x="date", y="submissions", color="section")
        fig.update_layout(legend_title="", margin=dict(t=10))
        st.plotly_chart(fig, width="stretch")
        st.dataframe(
            df.groupby("section").agg(
                submissions=("date", "count"),
                first=("date", "min"), last=("date", "max"),
            ).reset_index(),
            width="stretch", hide_index=True,
        )

    with tab_detail:
        section = st.selectbox("Section", list(config.SECTION_FIELDS))
        fields = config.SECTION_FIELDS[section]
        sdf = df[df["section"] == section]
        if sdf.empty:
            st.info("No submissions for this section in the selected range.")
        else:
            totals = sdf[fields].sum().astype(int).sort_values()
            fig = px.bar(x=totals.values, y=totals.index, orientation="h",
                         labels={"x": "Total", "y": ""})
            fig.update_layout(margin=dict(t=10))
            st.plotly_chart(fig, width="stretch")
