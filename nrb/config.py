"""Static configuration: form field registry, roster defaults, constants.

Field names must match the Google Form response headers EXACTLY,
including double spaces (e.g. "Expired  IDs processed").
"""

APP_TITLE = "Mzuzu NRB Report Dashboard"
OFFICE_NAME = "MZUZU NRB OFFICE"
REPORT_TITLE = "DAILY REPORT FOR MZUZU NRB"
ORG_LONG_NAME = "The National Registration Bureau (NRB)"

DEFAULT_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1CWohxZr2rjlOqBpCGP693CtPJ5pctXmProLfqY5W-aM/edit#gid=165711781"
)

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

ALL_NUMERIC_FIELDS = [f for fields in SECTION_FIELDS.values() for f in fields]

# Current form dropdown roster (initials format).
DEFAULT_ROSTER = [
    ("S.Chirwa", "Stella Chirwa"),
    ("W.Mwamsango", "Wigly Mwamsango"),
    ("N.Nyalugwe", "Nathan Nyalugwe"),
    ("D.Kayira", "Daniel Kayira"),
    ("E.Chimbalanga", "Emmanuel Chimbalanga"),
    ("L.Chirwa", "Lawrence Chirwa"),
    ("H.Kanyumbu", "Harry Kanyumbu"),
    ("D.Chimera", "Dalitso Chimera"),
    ("T.Ng'ambi", "Temwanani Ng'ambi"),
    ("B.Jeke", "Bennita Jeke"),
    ("K.Zirenga", "Kenneth Zirenga"),
    ("M.Chirwa", "Macson Chirwa"),
    ("M.Mbewe", "M. Mbewe"),
    ("T.Mwenelupembe", "Towera Mwenelupembe"),
    ("A.Nkata", "Ancent Nkata"),
    ("D.Lobe", "Deborah Lobe"),
    ("S.Gondwe", "Shuppie Gondwe"),
    ("L.Chilinda", "Linda Chilinda"),
    ("O.Chibalazi", "O. Chibalazi"),
    ("S.Chipeta", "Stanley Chipeta"),
    ("L.Khunga", "Laston Khunga"),
    ("E.Thera", "Eliam Thera"),
    ("C.Mzumara", "C. Mzumara"),
]

DEFAULT_TEAMS = [
    # (name, reports_as_section, min_size, max_size)
    ("Capturing Team", "ID CAPTURING", 2, 3),
    ("Distribution Team", "ID DISTRIBUTION", 2, 3),
    ("CRVS Team (Office)", "BIRTHS SECTION", 2, 3),
    ("Mzuzu Central Hospital Team", "BIRTHS SECTION", 2, 2),
    ("Mapale Health Centre Team", "BIRTHS SECTION", 2, 2),
    ("Tracking", "ID DISTRIBUTION", 2, 3),
]

SCHEDULE_FOOTER = '"THE SCHEDULE IS SUBJECT TO CHANGE"'

DEFAULT_PLANNED_ACTIVITIES = (
    "1.Continue with ID registration and distribution\n"
    "2.Issue out birth and death certificates\n"
    "3.Print out birth and death certificates\n"
    "4.Monitor and collect NR8 and NR10 forms"
)
DEFAULT_COMPILED_BY = "COMPILED BY  MZUZU ARO\nFOR MZUZU PRO."
