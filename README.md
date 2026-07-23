# Mzuzu NRB Report Dashboard

Live dashboard + one-click monthly reporting + fair team scheduling for the
Mzuzu NRB daily report Google Form.

## What it replaces

The old month-end ritual (edit week dates on 5 sheets, download, paste-values,
delete imported data, rename the file) becomes: open **Monthly Report** →
pick month → **Download**. Weeks are derived automatically (Monday–Sunday,
month days only), the workbook is values-only and already named
`<MONTH> MONTHLY REPORT_MZUZU NRB.xlsx`.

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
- **Real auth** — per-user accounts (PBKDF2-hashed passwords, admin/viewer
  roles) stored in MongoDB Atlas. Dashboards can be public or login-only
  (Admin toggle); export, scheduling and admin always require login.
- **Persistent storage** — users, teams, schedules and settings live in
  MongoDB Atlas, so nothing is lost on app restarts or redeploys. Form
  responses stay in Google Sheets as before.

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

```bash
pip install -r requirements.txt
```

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, paste
your `MONGODB_URI`, then:

```bash
streamlit run app.py
```

First run: the app asks you to create the admin account, then log in from the
sidebar. Data source defaults to the office responses sheet; change it in
**Admin → Data source** (the sheet must be shared "Anyone with link → Viewer").

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
