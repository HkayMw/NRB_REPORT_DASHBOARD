"""Fetch the Google Form responses sheet as a DataFrame (public CSV export)."""

import re
from io import StringIO

import pandas as pd
import requests
import streamlit as st


def _csv_export_url(sheet_url: str) -> str:
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", sheet_url)
    if not m:
        raise ValueError("That does not look like a Google Sheets URL.")
    doc_id = m.group(1)
    gid_m = re.search(r"[#&?]gid=(\d+)", sheet_url)
    gid = gid_m.group(1) if gid_m else "0"
    return f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid}"


@st.cache_data(ttl=300, show_spinner="Fetching latest form responses…")
def fetch_responses(sheet_url: str) -> pd.DataFrame:
    resp = requests.get(_csv_export_url(sheet_url), timeout=30)
    resp.raise_for_status()
    if resp.headers.get("content-type", "").startswith("text/html"):
        raise RuntimeError(
            "Google returned a web page instead of CSV — the sheet is probably not "
            "shared as 'Anyone with the link → Viewer'."
        )
    df = pd.read_csv(StringIO(resp.content.decode("utf-8")))
    df = df.dropna(how="all").dropna(axis=1, how="all")
    return df


def clear_cache():
    fetch_responses.clear()
