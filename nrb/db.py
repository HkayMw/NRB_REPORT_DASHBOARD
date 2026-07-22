"""SQLite persistence layer: users, settings, roster, teams, schedules."""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from nrb import config

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DATA_DIR, "nrb.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    pw_hash TEXT NOT NULL,
    full_name TEXT DEFAULT '',
    role TEXT NOT NULL DEFAULT 'viewer',        -- 'admin' | 'viewer'
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    form_name TEXT UNIQUE NOT NULL,             -- exact dropdown value, e.g. "H.Kanyumbu"
    full_name TEXT DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    reports_as_section TEXT DEFAULT '',         -- which form section this team's work lands in
    min_size INTEGER NOT NULL DEFAULT 1,
    max_size INTEGER NOT NULL DEFAULT 3,
    pinned_members TEXT NOT NULL DEFAULT '[]',  -- JSON list of staff form_names always on this team
    active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start TEXT NOT NULL,                   -- ISO date (Monday)
    week_end TEXT NOT NULL,                     -- ISO date (Friday shown on message)
    created_by TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(week_start)
);
CREATE TABLE IF NOT EXISTS schedule_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER NOT NULL REFERENCES schedules(id) ON DELETE CASCADE,
    team_id INTEGER NOT NULL REFERENCES teams(id),
    staff_name TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0
);
"""


@contextmanager
def conn():
    os.makedirs(DATA_DIR, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db():
    with conn() as c:
        c.executescript(SCHEMA)
        # Seed roster and teams on first run only.
        if c.execute("SELECT COUNT(*) FROM staff").fetchone()[0] == 0:
            c.executemany(
                "INSERT INTO staff (form_name, full_name) VALUES (?, ?)",
                config.DEFAULT_ROSTER,
            )
        if c.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == 0:
            for i, (name, section, mn, mx) in enumerate(config.DEFAULT_TEAMS):
                c.execute(
                    "INSERT INTO teams (name, reports_as_section, min_size, max_size, sort_order)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (name, section, mn, mx, i),
                )


# ---------- settings ----------

def get_setting(key, default=None):
    with conn() as c:
        row = c.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def set_setting(key, value):
    with conn() as c:
        c.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value)),
        )


# ---------- users ----------

def count_users():
    with conn() as c:
        return c.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def get_user(username):
    with conn() as c:
        row = c.execute(
            "SELECT * FROM users WHERE username = ? AND active = 1", (username,)
        ).fetchone()
    return dict(row) if row else None


def list_users():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM users ORDER BY username")]


def create_user(username, pw_hash, role="viewer", full_name=""):
    with conn() as c:
        c.execute(
            "INSERT INTO users (username, pw_hash, full_name, role, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (username.strip(), pw_hash, full_name.strip(), role,
             datetime.utcnow().isoformat(timespec="seconds")),
        )


def update_user(user_id, **fields):
    allowed = {"pw_hash", "full_name", "role", "active"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return
    q = ", ".join(f"{k} = ?" for k in sets)
    with conn() as c:
        c.execute(f"UPDATE users SET {q} WHERE id = ?", (*sets.values(), user_id))


def delete_user(user_id):
    with conn() as c:
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))


# ---------- staff ----------

def list_staff(active_only=False):
    q = "SELECT * FROM staff" + (" WHERE active = 1" if active_only else "") + " ORDER BY form_name"
    with conn() as c:
        return [dict(r) for r in c.execute(q)]


def upsert_staff(form_name, full_name="", active=1, staff_id=None):
    with conn() as c:
        if staff_id:
            c.execute(
                "UPDATE staff SET form_name = ?, full_name = ?, active = ? WHERE id = ?",
                (form_name.strip(), full_name.strip(), int(active), staff_id),
            )
        else:
            c.execute(
                "INSERT INTO staff (form_name, full_name, active) VALUES (?, ?, ?)",
                (form_name.strip(), full_name.strip(), int(active)),
            )


def delete_staff(staff_id):
    with conn() as c:
        c.execute("DELETE FROM staff WHERE id = ?", (staff_id,))


# ---------- teams ----------

def list_teams(active_only=False):
    q = "SELECT * FROM teams" + (" WHERE active = 1" if active_only else "") + " ORDER BY sort_order, name"
    with conn() as c:
        rows = [dict(r) for r in c.execute(q)]
    for r in rows:
        r["pinned_members"] = json.loads(r["pinned_members"] or "[]")
    return rows


def upsert_team(name, reports_as_section, min_size, max_size, pinned_members,
                active=1, sort_order=0, team_id=None):
    pinned = json.dumps(list(pinned_members or []))
    with conn() as c:
        if team_id:
            c.execute(
                "UPDATE teams SET name=?, reports_as_section=?, min_size=?, max_size=?,"
                " pinned_members=?, active=?, sort_order=? WHERE id=?",
                (name.strip(), reports_as_section, int(min_size), int(max_size),
                 pinned, int(active), int(sort_order), team_id),
            )
        else:
            c.execute(
                "INSERT INTO teams (name, reports_as_section, min_size, max_size,"
                " pinned_members, active, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name.strip(), reports_as_section, int(min_size), int(max_size),
                 pinned, int(active), int(sort_order)),
            )


def delete_team(team_id):
    with conn() as c:
        c.execute("DELETE FROM schedule_assignments WHERE team_id = ?", (team_id,))
        c.execute("DELETE FROM teams WHERE id = ?", (team_id,))


# ---------- schedules ----------

def save_schedule(week_start, week_end, assignments, created_by=""):
    """assignments: list of (team_id, staff_name, position). Replaces any
    existing schedule for the same week."""
    with conn() as c:
        row = c.execute("SELECT id FROM schedules WHERE week_start = ?", (week_start,)).fetchone()
        if row:
            sid = row["id"]
            c.execute("DELETE FROM schedule_assignments WHERE schedule_id = ?", (sid,))
            c.execute(
                "UPDATE schedules SET week_end = ?, created_by = ?, created_at = ? WHERE id = ?",
                (week_end, created_by, datetime.utcnow().isoformat(timespec="seconds"), sid),
            )
        else:
            cur = c.execute(
                "INSERT INTO schedules (week_start, week_end, created_by, created_at)"
                " VALUES (?, ?, ?, ?)",
                (week_start, week_end, created_by,
                 datetime.utcnow().isoformat(timespec="seconds")),
            )
            sid = cur.lastrowid
        c.executemany(
            "INSERT INTO schedule_assignments (schedule_id, team_id, staff_name, position)"
            " VALUES (?, ?, ?, ?)",
            [(sid, tid, name, pos) for tid, name, pos in assignments],
        )
    return sid


def list_schedules(limit=30):
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM schedules ORDER BY week_start DESC LIMIT ?", (limit,))]


def get_schedule(week_start):
    with conn() as c:
        s = c.execute("SELECT * FROM schedules WHERE week_start = ?", (week_start,)).fetchone()
        if not s:
            return None
        rows = c.execute(
            "SELECT a.*, t.name AS team_name FROM schedule_assignments a"
            " JOIN teams t ON t.id = a.team_id WHERE a.schedule_id = ?"
            " ORDER BY t.sort_order, a.position", (s["id"],)).fetchall()
    return {"schedule": dict(s), "assignments": [dict(r) for r in rows]}


def delete_schedule(week_start):
    with conn() as c:
        row = c.execute("SELECT id FROM schedules WHERE week_start = ?", (week_start,)).fetchone()
        if row:
            c.execute("DELETE FROM schedule_assignments WHERE schedule_id = ?", (row["id"],))
            c.execute("DELETE FROM schedules WHERE id = ?", (row["id"],))


def assignment_history():
    """All historical assignments: [{week_start, team_id, staff_name}] newest first."""
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT s.week_start, a.team_id, a.staff_name"
            " FROM schedule_assignments a JOIN schedules s ON s.id = a.schedule_id"
            " ORDER BY s.week_start DESC")]
