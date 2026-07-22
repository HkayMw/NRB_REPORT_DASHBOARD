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
  roles) in SQLite. Dashboards can be public or login-only (Admin toggle);
  export, scheduling and admin always require login.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

First run: the app asks you to create the admin account, then log in from the
sidebar. Data source defaults to the office responses sheet; change it in
**Admin → Data source** (the sheet must be shared "Anyone with link → Viewer").

## Deploy on Streamlit Community Cloud

1. Push this folder to a GitHub repo.
2. share.streamlit.io → New app → pick the repo, main file `app.py`.
3. Open the deployed app, create the admin account, configure.

**Important:** Community Cloud storage is ephemeral — the SQLite database
(users, teams, schedules, settings) is wiped on reboot/redeploy. Use
**Admin → Backup** to download the `.db` after changes and restore it after a
redeploy. (Form data is never at risk — it lives in Google Sheets.)

## Data rules (agreed)

- `Name` is multi-select: one submission can cover several staff.
- Rows whose names don't all match the roster are excluded (old free-text era).
- Duplicate = same **(date, section, same people)** → latest submission wins.
- Different people reporting the same section on the same day are **summed**
  (e.g. CRVS office team + hospital teams).
- Sections missing `Assigned Section` (old rows) are inferred from which
  fields were filled.
