"""Demo data source: bundled synthetic form responses instead of Google Sheets.

Has the same interface as ``google_sheets`` so the rest of the app is unchanged.
The URL argument is accepted but ignored, so the demo never reaches out to a
real sheet.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

DEMO_CSV = Path(__file__).resolve().parents[3] / "data" / "demo_responses.csv"


@st.cache_data(show_spinner="Loading demo form responses…")
def fetch_responses(sheet_url: str) -> pd.DataFrame:
    df = pd.read_csv(DEMO_CSV)
    df = df.dropna(how="all").dropna(axis=1, how="all")
    return df


def clear_cache():
    fetch_responses.clear()
