"""Streamlit presentation helpers for loaded reporting data."""

from collections.abc import Callable

import pandas as pd
import streamlit as st

from nrb.application.services.load_reporting_data import ReportingDataService
from nrb.application.errors import ApplicationError, log_unexpected


def load(service: ReportingDataService):
    """Returns (raw_df, CleanResult) or raises with a user-friendly error."""
    result = service.load()
    return result.raw, result.cleaned


def load_or_stop(service: ReportingDataService):
    try:
        return load(service)
    except ApplicationError as error:
        st.error(str(error))
        st.stop()
    except Exception as error:
        log_unexpected("Render reporting data load error", error)
        st.error("Could not load form responses. Please try again later.")
        st.stop()


def date_range_filter(clean: pd.DataFrame, key="range"):
    """Sidebar date-range picker; returns the filtered frame + (start, end)."""
    if clean.empty:
        return clean, (None, None)
    min_d, max_d = clean["date"].min().date(), clean["date"].max().date()
    with st.sidebar:
        st.markdown("**Filter**")
        picked = st.date_input(
            "Date range",
            value=(max(min_d, max_d.replace(day=1)), max_d),
            min_value=min_d,
            max_value=max_d,
            key=key,
        )
    if isinstance(picked, tuple):
        picked_values = iter(picked)
        start = next(picked_values, min_d)
        end = next(picked_values, start)
    else:
        start = end = picked
    mask = (clean["date"] >= pd.Timestamp(start)) & (clean["date"] <= pd.Timestamp(end))
    return clean[mask], (start, end)


def refresh_button(clear_cache: Callable[[], None]):
    with st.sidebar:
        if st.button("🔄 Refresh data now", width="stretch"):
            clear_cache()
            st.rerun()
