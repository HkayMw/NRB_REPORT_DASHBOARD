"""Shared data access for all pages: fetch sheet -> clean -> filter helpers."""

import pandas as pd
import streamlit as st

from nrb import cleaning, config, db, sheets


def get_sheet_url():
    return db.get_setting("sheet_url", config.DEFAULT_SHEET_URL)


def load():
    """Returns (raw_df, CleanResult) or raises with a user-friendly error."""
    raw = sheets.fetch_responses(get_sheet_url())
    roster = [s["form_name"] for s in db.list_staff()]
    return raw, cleaning.clean_responses(raw, roster)


def load_or_stop():
    try:
        return load()
    except Exception as e:
        st.error(f"Could not load form responses: {e}")
        st.stop()


def date_range_filter(clean: pd.DataFrame, key="range"):
    """Sidebar date-range picker; returns the filtered frame + (start, end)."""
    if clean.empty:
        return clean, (None, None)
    min_d, max_d = clean["date"].min().date(), clean["date"].max().date()
    with st.sidebar:
        st.markdown("**Filter**")
        picked = st.date_input(
            "Date range", value=(max(min_d, max_d.replace(day=1)), max_d),
            min_value=min_d, max_value=max_d, key=key,
        )
    if isinstance(picked, tuple) and len(picked) == 2:
        start, end = picked
    else:
        start = end = picked if not isinstance(picked, tuple) else picked[0]
    mask = (clean["date"] >= pd.Timestamp(start)) & (clean["date"] <= pd.Timestamp(end))
    return clean[mask], (start, end)


def refresh_button():
    with st.sidebar:
        if st.button("🔄 Refresh data now", width="stretch"):
            sheets.clear_cache()
            st.rerun()
