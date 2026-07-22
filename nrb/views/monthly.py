"""Monthly report: on-screen preview + one-click Excel export."""

from datetime import date

import pandas as pd
import streamlit as st

from nrb import auth, config, data, db, export, reportcfg, weeks


def render():
    st.title("📑 Monthly Report")
    _, res = data.load_or_stop()
    data.refresh_button()
    clean = res.clean
    if clean.empty:
        st.info("No clean submissions found yet.")
        return

    months = sorted(clean["date"].dt.to_period("M").unique(), reverse=True)
    pick = st.selectbox("Report month", months,
                        format_func=lambda p: p.strftime("%B %Y"))
    year, month = pick.year, pick.month
    cfg = reportcfg.get_report_config()
    wk_list = weeks.month_weeks(year, month)

    mdf = clean[clean["date"].dt.to_period("M") == pick]
    st.caption(f"{len(mdf)} submissions found for {pick.strftime('%B %Y')} · "
               f"{len(wk_list)} weeks (Mon–Sun, month days only)")

    # ---- Summary preview (mirrors the exported Report Summary sheet) ----
    cols = reportcfg.summary_columns(cfg)
    table = []
    for wno, start, end in wk_list:
        wdf = mdf[(mdf["date"] >= pd.Timestamp(start)) & (mdf["date"] <= pd.Timestamp(end))]
        row = {"Week": f"Week {wno} ({start.day}–{end.day})"}
        for gtitle, label, (gi, bi, ri) in cols:
            blk = reportcfg.compute_block(wdf, cfg["groups"][gi]["blocks"][bi])
            row[f"{gtitle} · {label}"] = blk["total"] if ri == "total" else blk["rows"][ri][1]
        table.append(row)
    prev = pd.DataFrame(table).set_index("Week")
    prev.loc["TOTALS"] = prev.sum()
    st.dataframe(prev, width="stretch")

    with st.expander("Week-by-week detail"):
        for wno, start, end in wk_list:
            wdf = mdf[(mdf["date"] >= pd.Timestamp(start)) & (mdf["date"] <= pd.Timestamp(end))]
            st.markdown(f"**Week {wno}** — {weeks.pretty_range(start, end)} "
                        f"({len(wdf)} submissions)")
            block_cols = st.columns(2)
            i = 0
            for g in cfg["groups"]:
                for b in g["blocks"]:
                    vals = reportcfg.compute_block(wdf, b)
                    rows = pd.DataFrame(vals["rows"], columns=[b["title"], "Total"])
                    if b.get("total_label"):
                        rows.loc[len(rows)] = [b["total_label"], vals["total"]]
                    with block_cols[i % 2]:
                        st.dataframe(rows, width="stretch", hide_index=True)
                    i += 1

    # ---- Export ----
    st.divider()
    if not auth.is_logged_in():
        st.info("Log in (sidebar) to download the Excel report.")
        return

    planned = db.get_setting("planned_activities", config.DEFAULT_PLANNED_ACTIVITIES)
    compiled = db.get_setting("compiled_by", config.DEFAULT_COMPILED_BY)
    with st.expander("Report footer text (saved for future months)"):
        planned_new = st.text_area("Planned activities", planned, height=120)
        compiled_new = st.text_area("Compiled by", compiled, height=70)
        if st.button("Save footer text"):
            db.set_setting("planned_activities", planned_new)
            db.set_setting("compiled_by", compiled_new)
            st.success("Saved.")
            planned, compiled = planned_new, compiled_new

    buf = export.build_monthly_workbook(mdf, year, month, cfg, planned, compiled)
    st.download_button(
        "⬇️ Download Excel report",
        data=buf,
        file_name=export.suggested_filename(year, month),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )
    st.caption("Values only — no imported-data sheet to detach, no week dates to edit, "
               "already named correctly.")
