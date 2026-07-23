"""Data quality: dropped duplicates, unknown names, flagged issues."""

import streamlit as st

from nrb import config, data, ui


def render():
    ui.header("🧹", "Data Quality", "What the cleaning rules caught in the raw responses")
    _, res = data.load_or_stop()
    data.refresh_button()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Clean submissions", len(res.clean))
    c2.metric("Duplicates removed", len(res.dropped_duplicates))
    c3.metric("Rows with unknown names", len(res.unknown_names))
    c4.metric("Flagged issues", len(res.issues))

    st.subheader("Flagged issues")
    if res.issues.empty:
        st.success("No issues flagged. 🎉")
    else:
        st.dataframe(res.issues, width="stretch", hide_index=True)

    st.subheader("Duplicates removed (latest submission kept)")
    st.caption("Same date + section + same people, submitted more than once — "
               "the earlier copies below were dropped as corrections.")
    if res.dropped_duplicates.empty:
        st.success("No duplicate submissions.")
    else:
        cols = [config.TIMESTAMP_COL, config.NAME_COL, config.DATE_COL, "section"]
        st.dataframe(res.dropped_duplicates[cols], width="stretch", hide_index=True)

    st.subheader("Excluded rows (names not on the roster)")
    st.caption("Mostly the old free-text era. Fix the roster in Admin → Roster "
               "if a legitimate current name is being excluded.")
    if res.unknown_names.empty:
        st.success("Every row matches the roster.")
    else:
        cols = [config.TIMESTAMP_COL, config.NAME_COL, config.DATE_COL]
        st.dataframe(res.unknown_names[cols], width="stretch", hide_index=True)
