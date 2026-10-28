# NRB Report Dashboard

Live dashboard + one-click monthly reporting + fair team scheduling for a
registration office's daily report Google Form. The office is named in the
deployment settings, not in the code.

## What it replaces

The old month-end ritual (edit week dates on 5 sheets, download, paste-values,
delete imported data, rename the file) becomes: open **Monthly Report** →
pick month → **Download**. Weeks are derived automatically (Monday–Sunday,
month days only), the workbook is values-only and already named
`<MONTH> MONTHLY REPORT_<OFFICE>.xlsx`.

## Features

- **Dashboard** — live KPIs, trends and per-section breakdowns for any date
  range, straight from the form responses sheet (cached 5 min, manual refresh).
- **Compliance** — section-coverage grid (who reported which day), per-person
  activity, and scheduled-vs-reported comparison.
- **Data Quality** — duplicates removed (same date + section + same people →
  latest wins), rows excluded for unknown names, future dates, suspicious values.
- **Monthly Report** — preview + Excel export reproducing the office format;
  the layout (which rows appear, which form fields combine into each row, what
  goes on the summary) is fully configurable in **Admin → Report layout**.
- **Scheduling** — manage teams (CRUD, min/max size, pinned members, which form
  section each team reports as), generate a fair rotation (longest-away-first,
  balanced totals), tweak manually, save, and copy the WhatsApp message.
- **Real auth** — per-user accounts (PBKDF2-hashed passwords) stored in
  MongoDB Atlas. Dashboards can be public or login-only (Admin toggle);
  export, scheduling and admin always require login. Roles
  (`nrb/domain/roles.py`):
  - **viewer** — dashboards and report download.
  - **clerk** — plus creating new weekly schedules and editing the roster.
  - **admin** — everything, including editing/deleting saved schedules,
    teams, users, data source, report layout and the database.
- **Persistent storage** — users, teams, schedules and settings live in
  MongoDB Atlas, so nothing is lost on app restarts or redeploys. Form
  responses stay in Google Sheets as before.

## Deployment modes

One codebase runs both the office app and a public demo. The mode comes from
the `APP_MODE` setting (environment variable or Streamlit secret).

|                | Live (default)                         | Demo (`APP_MODE = "demo"`)                                                 |
| -------------- | -------------------------------------- | -------------------------------------------------------------------------- |
| Form responses | Google Sheet from `SHEET_URL` or Admin | `data/demo_responses.csv` (synthetic)                                      |
| Database       | MongoDB Atlas (`MONGODB_URI`)          | In-memory mongomock, no secrets needed                                     |
| Accounts       | Created by the office admin            | `demo_admin`, `demo_clerk`, `demo_viewer` (password `demo1234`), read-only |
| Today          | Real date                              | Fixed at 28 July 2028                                                      |
| Branding       | From the office settings below         | Neutral "Registration Office (Demo)"                                       |

Live app secrets:

```toml
MONGODB_URI = "mongodb+srv://..."
SHEET_URL = "https://docs.google.com/spreadsheets/d/<sheet id>/edit#gid=<gid>"

# Office branding (all optional; neutral defaults otherwise)
OFFICE_NAME = "Lakeside Registration Office"      # report header
OFFICE_SHORT_NAME = "Lakeside"                    # report titles and file names
APP_TITLE = "Lakeside Report Dashboard"           # page title
ORG_LONG_NAME = "Lakeside Registration Office"    # weekly sheet header
REPORT_COMPILED_BY = "COMPILED BY  OFFICE SUPERVISOR\nFOR DISTRICT REGISTRAR."
```

The report footer can also be edited in the app, and a saved footer takes
priority over `REPORT_COMPILED_BY`.

Demo app secrets:

```toml
APP_MODE = "demo"
```

To regenerate the synthetic demo data (June 2026 to July 2028, fictional
names): `python -m scripts.generate_demo_data`.

## Database setup (one-time, free)

1. Create a free cluster at [mongodb.com/atlas](https://www.mongodb.com/atlas)
   (Shared / M0 tier).
2. **Database Access** → create a database user with a password.
3. **Network Access** → allow `0.0.0.0/0` (needed for Streamlit Cloud).
4. **Database → Connect → Drivers** → copy the `mongodb+srv://…` string.
5. Give it to the app as the `MONGODB_URI` secret (see below).

For a throwaway local demo without Atlas, set
`MONGODB_URI = "mongomock://local"` — in-memory, data lost on restart.

## Run locally

Supported Python version: **3.11**.

```bash
pip install -r requirements.txt
```

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, paste
your `MONGODB_URI`, then:

```bash
streamlit run app.py
```

## Development checks

Install development tools and runtime dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

Run the same checks used by CI:

```bash
python -m pytest tests -q
python -m ruff check .
python -m ruff format --check app.py nrb tests scripts
python -m mypy
```

First run: the app asks you to create the admin account, then log in from the
sidebar. The office sheet is never stored in the code. Set it as the
`SHEET_URL` secret, or save it in **Admin → Data source** (the sheet must be
shared "Anyone with link → Viewer").

## Deploy on Streamlit Community Cloud

1. Push this folder to a GitHub repo.
2. share.streamlit.io → New app → pick the repo, main file `app.py`.
3. App → Settings → **Secrets** → add `MONGODB_URI = "mongodb+srv://…"`.
4. Open the deployed app, create the admin account, configure.

**Admin → Database** shows connection status and offers an optional JSON
backup/restore of app data (accounts, teams, schedules, settings).

## Data rules (agreed)

- `Name` is multi-select: one submission can cover several staff.
- Rows whose names don't all match the roster are excluded (old free-text era).
- Duplicate = same **(date, section, same people)** → latest submission wins.
- Different people reporting the same section on the same day are **summed**
  (e.g. CRVS office team + hospital teams).
- Sections missing `Assigned Section` (old rows) are inferred from which
  fields were filled.

## Copyright

© 2026 Harry Kanyumbu. All rights reserved.
