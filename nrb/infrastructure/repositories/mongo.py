"""MongoDB Atlas persistence layer: users, settings, roster, teams, schedules.

Connection string comes from (in order):
1. the MONGODB_URI environment variable
2. st.secrets["MONGODB_URI"]  (.streamlit/secrets.toml locally, or the
   Secrets box on Streamlit Community Cloud)

Demo mode (APP_MODE = "demo") always uses an in-memory database and ignores
any MONGODB_URI, so the public demo can never read or write real data.

Special URI "mongomock://local" runs an in-memory fake MongoDB — handy for
tests and quick local demos (data lost when the process exits).

Public API (function names/shapes) is unchanged from the old SQLite layer;
documents are returned as plain dicts with a string "id" key.
"""

import json
import logging
import os
from pathlib import Path
from datetime import datetime, timezone

import streamlit as st
from bson import ObjectId

from nrb import config

DB_NAME = "nrb_dashboard"
logger = logging.getLogger("nrb.infrastructure.mongo")


def get_uri():
    # The demo must never touch a real database, even when a MONGODB_URI is
    # present in the environment or secrets (e.g. a developer's local setup).
    if config.DEMO_MODE:
        return "mongomock://local"
    uri = os.environ.get("MONGODB_URI")
    if uri:
        return uri
    try:
        return st.secrets["MONGODB_URI"]
    except Exception:
        return None


def configured() -> bool:
    return bool(get_uri())


@st.cache_resource(show_spinner=False)
def _client(uri: str):
    if uri.startswith("mongomock://"):
        import mongomock

        return mongomock.MongoClient()
    from pymongo import MongoClient

    return MongoClient(uri, serverSelectionTimeoutMS=8000)


def _db():
    return _client(get_uri())[DB_NAME]


def ping() -> tuple:
    """(ok, detail) — used by the Admin page to show connection status."""
    try:
        _client(get_uri()).admin.command("ping")
        host = (
            "in-memory mongomock"
            if get_uri().startswith("mongomock://")
            else get_uri().split("@")[-1].split("/")[0].split("?")[0]
        )
        return True, host
    except Exception:
        logger.exception("MongoDB ping failed")
        return False, "Connection check failed. See application logs."


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _out(doc):
    """Mongo doc -> plain dict with string id."""
    if doc is None:
        return None
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


def _oid(id_):
    return id_ if isinstance(id_, ObjectId) else ObjectId(str(id_))


def init_db():
    db = _db()
    db.users.create_index("username", unique=True)
    db.staff.create_index("form_name", unique=True)
    db.teams.create_index("name", unique=True)
    db.schedules.create_index("week_start", unique=True)
    if db.staff.count_documents({}) == 0 and config.default_roster():
        db.staff.insert_many(
            [
                {"form_name": fn, "full_name": full, "active": 1}
                for fn, full in config.default_roster()
            ]
        )
    if db.teams.count_documents({}) == 0:
        db.teams.insert_many(
            [
                {
                    "name": name,
                    "reports_as_section": section,
                    "min_size": mn,
                    "max_size": mx,
                    "pinned_members": [],
                    "active": 1,
                    "sort_order": i,
                }
                for i, (name, section, mn, mx) in enumerate(config.default_teams())
            ]
        )
    if config.DEMO_MODE and db.schedules.count_documents({}) == 0:
        _seed_demo_schedules(db)


DEMO_SCHEDULES = Path(__file__).resolve().parents[3] / "data" / "demo_schedules.json"


def _seed_demo_schedules(db):
    """Load the synthetic weekly schedules that match the demo responses."""
    if not DEMO_SCHEDULES.exists():
        return
    team_ids = {t["name"]: str(t["_id"]) for t in db.teams.find()}
    docs = []
    for sched in json.loads(DEMO_SCHEDULES.read_text()):
        docs.append(
            {
                "week_start": sched["week_start"],
                "week_end": sched["week_end"],
                "created_by": "demo_clerk",
                "created_at": _now(),
                "assignments": [
                    {
                        "team_id": team_ids[a["team_name"]],
                        "staff_name": a["staff_name"],
                        "position": a["position"],
                    }
                    for a in sched["assignments"]
                    if a["team_name"] in team_ids
                ],
            }
        )
    if docs:
        db.schedules.insert_many(docs)


def ensure_demo_accounts(hash_password):
    """Make sure the published demo logins always exist and are active.

    Cheap on every rerun: a password is only hashed when an account is missing.
    """
    users = _db().users
    for username, full_name, role in config.DEMO_ACCOUNTS:
        doc = users.find_one({"username": username})
        if doc is None:
            create_user(username, hash_password(config.DEMO_PASSWORD), role, full_name)
        elif doc.get("active") != 1 or doc.get("role") != role:
            users.update_one({"_id": doc["_id"]}, {"$set": {"active": 1, "role": role}})


# ---------- settings ----------


def get_setting(key, default=None):
    doc = _db().settings.find_one({"_id": key})
    return doc["value"] if doc else default


def set_setting(key, value):
    _db().settings.update_one({"_id": key}, {"$set": {"value": value}}, upsert=True)


# ---------- users ----------


def count_users():
    return _db().users.count_documents({})


def get_user(username):
    return _out(_db().users.find_one({"username": username.strip(), "active": 1}))


def get_user_by_id(user_id):
    return _out(_db().users.find_one({"_id": _oid(user_id)}))


def list_users():
    return [_out(u) for u in _db().users.find().sort("username", 1)]


def create_user(username, pw_hash, role="viewer", full_name=""):
    _db().users.insert_one(
        {
            "username": username.strip(),
            "pw_hash": pw_hash,
            "full_name": full_name.strip(),
            "role": role,
            "active": 1,
            "created_at": _now(),
        }
    )


def update_user(user_id, **fields):
    allowed = {"pw_hash", "full_name", "role", "active"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if sets:
        _db().users.update_one({"_id": _oid(user_id)}, {"$set": sets})


def delete_user(user_id):
    _db().users.delete_one({"_id": _oid(user_id)})


# ---------- staff ----------


def list_staff(active_only=False):
    q = {"active": 1} if active_only else {}
    return [_out(s) for s in _db().staff.find(q).sort("form_name", 1)]


def upsert_staff(form_name, full_name="", active=1, staff_id=None):
    doc = {
        "form_name": form_name.strip(),
        "full_name": full_name.strip(),
        "active": int(active),
    }
    if staff_id:
        _db().staff.update_one({"_id": _oid(staff_id)}, {"$set": doc})
    else:
        _db().staff.insert_one(doc)


def delete_staff(staff_id):
    _db().staff.delete_one({"_id": _oid(staff_id)})


# ---------- teams ----------


def list_teams(active_only=False):
    q = {"active": 1} if active_only else {}
    return [_out(t) for t in _db().teams.find(q).sort([("sort_order", 1), ("name", 1)])]


def upsert_team(
    name,
    reports_as_section,
    min_size,
    max_size,
    pinned_members,
    active=1,
    sort_order=0,
    team_id=None,
):
    doc = {
        "name": name.strip(),
        "reports_as_section": reports_as_section,
        "min_size": int(min_size),
        "max_size": int(max_size),
        "pinned_members": list(pinned_members or []),
        "active": int(active),
        "sort_order": int(sort_order),
    }
    if team_id:
        _db().teams.update_one({"_id": _oid(team_id)}, {"$set": doc})
    else:
        _db().teams.insert_one(doc)


def delete_team(team_id):
    tid = str(team_id)
    _db().schedules.update_many({}, {"$pull": {"assignments": {"team_id": tid}}})
    _db().teams.delete_one({"_id": _oid(team_id)})


# ---------- schedules (assignments embedded in the schedule document) ----------


def save_schedule(week_start, week_end, assignments, created_by=""):
    """assignments: list of (team_id, staff_name, position). Replaces any
    existing schedule for the same week."""
    _db().schedules.update_one(
        {"week_start": week_start},
        {
            "$set": {
                "week_end": week_end,
                "created_by": created_by,
                "created_at": _now(),
                "assignments": [
                    {"team_id": str(tid), "staff_name": name, "position": pos}
                    for tid, name, pos in assignments
                ],
            }
        },
        upsert=True,
    )


def list_schedules(limit=30):
    return [_out(s) for s in _db().schedules.find().sort("week_start", -1).limit(limit)]


def get_schedule(week_start):
    doc = _db().schedules.find_one({"week_start": week_start})
    if not doc:
        return None
    teams = {t["id"]: t for t in list_teams()}
    assignments = []
    for a in sorted(
        doc.get("assignments", []),
        key=lambda a: (
            teams.get(a["team_id"], {}).get("sort_order", 99),
            a.get("position", 0),
        ),
    ):
        t = teams.get(a["team_id"])
        assignments.append(
            {
                **a,
                "team_name": t["name"] if t else "(deleted team)",
                "reports_as_section": t["reports_as_section"] if t else None,
            }
        )
    return {"schedule": _out(doc), "assignments": assignments}


def delete_schedule(week_start):
    _db().schedules.delete_one({"week_start": week_start})


def assignment_history():
    """[{week_start, team_id, staff_name}] newest first."""
    out = []
    for s in _db().schedules.find().sort("week_start", -1):
        for a in s.get("assignments", []):
            out.append(
                {
                    "week_start": s["week_start"],
                    "team_id": a["team_id"],
                    "staff_name": a["staff_name"],
                }
            )
    return out


# ---------- backup (JSON export/import via Admin page) ----------

_COLLECTIONS = ["users", "settings", "staff", "teams", "schedules"]


def export_all() -> dict:
    db = _db()
    dump = {}
    for coll in _COLLECTIONS:
        docs = []
        for d in db[coll].find():
            d = dict(d)
            d["_id"] = str(d["_id"])
            docs.append(d)
        dump[coll] = docs
    return dump


def import_all(dump: dict):
    db = _db()
    for coll in _COLLECTIONS:
        if coll not in dump:
            continue
        db[coll].delete_many({})
        docs = []
        for d in dump[coll]:
            d = dict(d)
            raw = d.pop("_id", None)
            if coll == "settings":
                d["_id"] = raw  # settings keep their string key ids
            else:
                try:
                    d["_id"] = ObjectId(raw)
                except Exception:
                    pass  # let Mongo assign a fresh id
            docs.append(d)
        if docs:
            db[coll].insert_many(docs)
