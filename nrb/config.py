"""Static configuration: form field registry, roster defaults, constants.

Field names must match the Google Form response headers EXACTLY,
including double spaces (e.g. "Expired  IDs processed").
"""

import os
from datetime import date


def _setting(name: str, default: str = "") -> str:
    """Read a deployment setting from the environment or Streamlit secrets."""
    value = os.environ.get(name)
    if value:
        return value
    try:
        import streamlit as st

        return str(st.secrets.get(name, default))
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Deployment mode
#   live  the office deployment (default). Reads the Google Sheet set in the
#         SHEET_URL secret or in Admin -> Data source.
#   demo  the public demo. Uses bundled synthetic data, an in-memory database
#         and published demo logins. Set APP_MODE = "demo" in the app secrets.
# ---------------------------------------------------------------------------
APP_MODE = _setting("APP_MODE", "live").strip().lower()
DEMO_MODE = APP_MODE == "demo"

DEMO_AS_OF = date(2028, 7, 28)  # the demo treats this Friday as "today"
DEMO_DATA_START = date(2026, 6, 1)
DEMO_PASSWORD = "demo1234"
DEMO_ACCOUNTS = [
    # (username, full name, role)
    ("demo_admin", "Demo Administrator", "admin"),
    ("demo_clerk", "Demo Clerk", "clerk"),
    ("demo_viewer", "Demo Viewer", "viewer"),
]
DEMO_USERNAMES = {username for username, _, _ in DEMO_ACCOUNTS}


def today() -> date:
    """The date the app treats as today (fixed in the demo)."""
    return DEMO_AS_OF if DEMO_MODE else date.today()


if DEMO_MODE:
    APP_TITLE = "Registration Office Report Dashboard (Demo)"
    OFFICE_NAME = "DEMO DISTRICT REGISTRATION OFFICE"
    OFFICE_SHORT = "DEMO OFFICE"
    REPORT_TITLE = "DAILY REPORT FOR DEMO DISTRICT REGISTRATION OFFICE"
    ORG_LONG_NAME = "Demo District Registration Office"
    DEFAULT_SHEET_URL = "demo://synthetic-form-responses"
else:
    APP_TITLE = "Mzuzu NRB Report Dashboard"
    OFFICE_NAME = "MZUZU NRB OFFICE"
    OFFICE_SHORT = "MZUZU NRB"
    REPORT_TITLE = "DAILY REPORT FOR MZUZU NRB"
    ORG_LONG_NAME = "The National Registration Bureau (NRB)"
    # Never hard-code the office sheet: set SHEET_URL in the app secrets or
    # save it in Admin -> Data source (stored in the database).
    DEFAULT_SHEET_URL = _setting("SHEET_URL", "")

TIMESTAMP_COL = "Timestamp"
NAME_COL = "Name"
DATE_COL = "Date"
SECTION_COL = "Assigned Section"

# Form sections and their numeric fields, in form order.
SECTION_FIELDS = {
    "ID CAPTURING": [
        "New applicants captured",
        "Expired  IDs processed",
        "Damaged  IDs processed",
        "Defaced  IDs processed",
        "Lost  IDs processed",
        "Edits processed",
        "Duplicate IDs resolved",
        "ID numbers retrieved",
    ],
    "ID DISTRIBUTION": [
        "IDs tracked",
        "New applicants  IDs distributed",
        "Renewed  IDs distributed",
        "Replaced Damaged  IDs distributed",
        "Replaced Defaced  IDs distributed",
        "Replaced Lost  IDs distributed",
        "Edited IDs distributed",
    ],
    "BIRTHS SECTION": [
        "NR8 forms collected",
        "NR8 forms entered",
        "NR8 forms approved",
        "Birth certificates printed",
        "Birth certificates issued",
        "Duplicate Birth records resolved",
    ],
    "DEATHS SECTION": [
        "NR10 forms collected",
        "NR10 forms entered",
        "NR10 forms approved",
        "Death certificates printed",
        "Death certificates issued",
        "Duplicate death records resolved",
        "Deceased IDs retrieved",
    ],
}

# The demo replaces office-specific form codes with generic names.
DEMO_FIELD_RENAMES = {
    "NR8 forms collected": "Birth registration forms collected",
    "NR8 forms entered": "Birth registration forms entered",
    "NR8 forms approved": "Birth registration forms approved",
    "NR10 forms collected": "Death registration forms collected",
    "NR10 forms entered": "Death registration forms entered",
    "NR10 forms approved": "Death registration forms approved",
}
DEMO_LABEL_RENAMES = {
    "NR8 FORMS ENTERED": "BIRTH FORMS ENTERED",
    "NR8 FORMS COLLECTED": "BIRTH FORMS COLLECTED",
    "NR10 FORMS ENTERED": "DEATH FORMS ENTERED",
    "NR10 APPROVED": "DEATH FORMS APPROVED",
    "NR10 FORMS COLLECTED": "DEATH FORMS COLLECTED",
}
if DEMO_MODE:
    SECTION_FIELDS = {
        section: [DEMO_FIELD_RENAMES.get(f, f) for f in fields]
        for section, fields in SECTION_FIELDS.items()
    }

ALL_NUMERIC_FIELDS = [f for fields in SECTION_FIELDS.values() for f in fields]

# The live roster is kept only in the database (Admin -> Roster), never in
# code, so staff names are not published with the source. A new live
# database starts with an empty roster for an admin to fill in.
DEFAULT_ROSTER: list[tuple[str, str]] = []

DEFAULT_TEAMS = [
    # (name, reports_as_section, min_size, max_size)
    ("Capturing Team", "ID CAPTURING", 2, 3),
    ("Distribution Team", "ID DISTRIBUTION", 2, 3),
    ("CRVS Team (Office)", "BIRTHS SECTION", 2, 3),
    ("Mzuzu Central Hospital Team", "BIRTHS SECTION", 2, 2),
    ("Mapale Health Centre Team", "BIRTHS SECTION", 2, 2),
    ("Tracking", "ID DISTRIBUTION", 2, 3),
]

# Fictional roster and teams used only by the demo.
DEMO_ROSTER = [
    ("A.Banda", "Alinafe Banda"),
    ("C.Phiri", "Chikondi Phiri"),
    ("T.Mwale", "Thokozani Mwale"),
    ("L.Tembo", "Limbani Tembo"),
    ("M.Nyirenda", "Madalitso Nyirenda"),
    ("K.Msiska", "Kondwani Msiska"),
    ("P.Lungu", "Pemphero Lungu"),
    ("F.Kaunda", "Fatsani Kaunda"),
    ("Y.Mhango", "Yamikani Mhango"),
    ("G.Mkandawire", "Grace Mkandawire"),
    ("J.Zulu", "Joseph Zulu"),
    ("R.Kumwenda", "Rhoda Kumwenda"),
    ("S.Munthali", "Sangwani Munthali"),
    ("W.Ngwira", "Wezi Ngwira"),
    ("E.Sichinga", "Esther Sichinga"),
    ("B.Moyo", "Blessings Moyo"),
    ("H.Luhanga", "Hope Luhanga"),
    ("D.Mtambo", "Dumisani Mtambo"),
    ("V.Kalua", "Victor Kalua"),
    ("N.Soko", "Natasha Soko"),
    ("I.Chavula", "Isaac Chavula"),
    ("Q.Mzembe", "Queen Mzembe"),
    ("U.Nkhoma", "Upile Nkhoma"),
]

DEMO_TEAMS = [
    ("Capturing Team", "ID CAPTURING", 2, 3),
    ("Distribution Team", "ID DISTRIBUTION", 2, 3),
    ("CRVS Team (Office)", "BIRTHS SECTION", 2, 3),
    ("District Hospital Team", "BIRTHS SECTION", 2, 2),
    ("Health Centre Team", "BIRTHS SECTION", 2, 2),
    ("Tracking", "ID DISTRIBUTION", 2, 3),
    ("Deaths Desk", "DEATHS SECTION", 1, 2),
]


def default_roster() -> list[tuple[str, str]]:
    return DEMO_ROSTER if DEMO_MODE else DEFAULT_ROSTER


def default_teams() -> list[tuple[str, str, int, int]]:
    return DEMO_TEAMS if DEMO_MODE else DEFAULT_TEAMS


SCHEDULE_FOOTER = '"THE SCHEDULE IS SUBJECT TO CHANGE"'

DEFAULT_PLANNED_ACTIVITIES = (
    "1.Continue with ID registration and distribution\n"
    "2.Issue out birth and death certificates\n"
    "3.Print out birth and death certificates\n"
    + (
        "4.Monitor and collect birth and death registration forms"
        if DEMO_MODE
        else "4.Monitor and collect NR8 and NR10 forms"
    )
)
DEFAULT_COMPILED_BY = (
    "COMPILED BY  OFFICE SUPERVISOR\nFOR DISTRICT REGISTRAR."
    if DEMO_MODE
    else "COMPILED BY  MZUZU ARO\nFOR MZUZU PRO."
)
