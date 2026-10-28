"""Generate the synthetic data used by the public demo.

Creates:
- data/demo_responses.csv   Google Form style daily report responses
- data/demo_schedules.json  weekly team schedules that match the responses

Everything is fictional. Run again with the same seed to get the same files:

    python scripts/generate_demo_data.py
"""

import json
import math
import os
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

os.environ["APP_MODE"] = "demo"  # generate with the demo's generic field names

from nrb import config  # noqa: E402

SEED = 2026
START = config.DEMO_DATA_START
END = config.DEMO_AS_OF
OUT_DIR = Path(__file__).resolve().parent.parent / "data"

# Daily averages per team. Fields not listed are left blank on the form.
PROFILES = {
    "Capturing Team": {
        "New applicants captured": 38,
        "Expired  IDs processed": 7,
        "Damaged  IDs processed": 3,
        "Defaced  IDs processed": 1,
        "Lost  IDs processed": 9,
        "Edits processed": 4,
        "Duplicate IDs resolved": 1,
        "ID numbers retrieved": 11,
    },
    "Distribution Team": {
        "New applicants  IDs distributed": 46,
        "Renewed  IDs distributed": 7,
        "Replaced Damaged  IDs distributed": 3,
        "Replaced Defaced  IDs distributed": 1,
        "Replaced Lost  IDs distributed": 8,
        "Edited IDs distributed": 3,
    },
    "Tracking": {"IDs tracked": 64},
    "CRVS Team (Office)": {
        "Birth registration forms collected": 14,
        "Birth registration forms entered": 19,
        "Birth registration forms approved": 15,
        "Birth certificates printed": 13,
        "Birth certificates issued": 11,
        "Duplicate Birth records resolved": 1,
    },
    "District Hospital Team": {
        "Birth registration forms collected": 21,
        "Birth registration forms entered": 16,
    },
    "Health Centre Team": {
        "Birth registration forms collected": 11,
        "Birth registration forms entered": 8,
    },
    "Deaths Desk": {
        "Death registration forms collected": 4,
        "Death registration forms entered": 4,
        "Death registration forms approved": 3,
        "Death certificates printed": 2,
        "Death certificates issued": 2,
        "Duplicate death records resolved": 0.3,
        "Deceased IDs retrieved": 1,
    },
}
TEAM_SIZES = {
    "Capturing Team": (3, 3),
    "Distribution Team": (3, 3),
    "CRVS Team (Office)": (2, 3),
    "District Hospital Team": (2, 2),
    "Health Centre Team": (2, 2),
    "Tracking": (2, 3),
    "Deaths Desk": (1, 2),
}


def holidays(year: int) -> set:
    """Fixed-date public holidays (fictional calendar based on common dates)."""
    days = [
        (1, 1),
        (1, 15),
        (3, 3),
        (5, 1),
        (5, 14),
        (7, 6),
        (10, 15),
        (12, 25),
        (12, 26),
    ]
    return {date(year, m, d) for m, d in days}


def seasonal_factor(day: date) -> float:
    """Busier early in the year and mid-year, with slow growth over time."""
    doy = day.timetuple().tm_yday
    season = 1 + 0.18 * math.sin(2 * math.pi * (doy - 20) / 365)
    growth = 1 + 0.12 * (day - START).days / (END - START).days
    week_dip = 0.85 if day.weekday() == 4 else 1.0  # quieter Fridays
    return season * growth * week_dip


def make_schedules(rng: random.Random) -> list[dict]:
    names = [form for form, _ in config.DEMO_ROSTER]
    served = {n: 0 for n in names}
    schedules = []
    monday = START - timedelta(days=START.weekday())
    while monday <= END:
        on_leave = set(rng.sample(names, rng.randint(1, 3)))
        pool = sorted(
            (n for n in names if n not in on_leave),
            key=lambda n: (served[n], rng.random()),
        )
        assignments = []
        for team, _section, _mn, _mx in config.DEMO_TEAMS:
            lo, hi = TEAM_SIZES[team]
            size = rng.randint(lo, hi)
            for pos in range(size):
                if not pool:
                    break
                person = pool.pop(0)
                served[person] += 1
                assignments.append(
                    {"team_name": team, "staff_name": person, "position": pos}
                )
        schedules.append(
            {
                "week_start": monday.isoformat(),
                "week_end": (monday + timedelta(days=4)).isoformat(),
                "assignments": assignments,
            }
        )
        monday += timedelta(days=7)
    return schedules


def fmt_ts(moment: datetime) -> str:
    return f"{moment.month}/{moment.day}/{moment.year} {moment:%H:%M:%S}"


def fmt_date(day: date) -> str:
    return f"{day.month}/{day.day}/{day.year}"


def make_responses(schedules: list[dict], rng: random.Random, np_rng) -> list[dict]:
    sections = {team: section for team, section, _, _ in config.DEMO_TEAMS}
    off_days = set().union(*(holidays(y) for y in range(START.year, END.year + 1)))
    rows = []
    for sched in schedules:
        monday = date.fromisoformat(sched["week_start"])
        teams: dict[str, list[str]] = {}
        for a in sched["assignments"]:
            teams.setdefault(a["team_name"], []).append(a["staff_name"])
        for offset in range(5):
            day = monday + timedelta(days=offset)
            if day < START or day > END or day in off_days:
                continue
            factor = seasonal_factor(day)
            for team, members in teams.items():
                if rng.random() < 0.03:  # team forgot to report
                    continue
                present = list(members)
                if len(present) > 1 and rng.random() < 0.04:  # one member absent
                    present.remove(rng.choice(present))
                row = {
                    "Timestamp": None,
                    "Name": ", ".join(present),
                    "Date": fmt_date(day),
                    "Assigned Section": sections[team],
                }
                for field in config.ALL_NUMERIC_FIELDS:
                    row[field] = ""
                for field, mean in PROFILES[team].items():
                    value = int(np_rng.poisson(mean * factor))
                    row[field] = "" if value == 0 and rng.random() < 0.5 else value
                submitted = datetime.combine(day, time(15, 0)) + timedelta(
                    minutes=rng.randint(0, 180), seconds=rng.randint(0, 59)
                )
                if rng.random() < 0.08:  # submitted the next morning
                    submitted += timedelta(hours=rng.randint(15, 18))
                row["Timestamp"] = fmt_ts(submitted)

                # Realistic data-entry problems for the Data Quality page.
                roll = rng.random()
                if roll < 0.010:
                    row["Assigned Section"] = ""  # old form version, inferred
                elif roll < 0.014:
                    row["Name"] = present[0].split(".")[-1].lower()  # free text
                elif roll < 0.017:
                    field = rng.choice(list(PROFILES[team]))
                    row[field] = rng.choice([-3, 2.5, 4.5])  # suspicious value
                rows.append(row)

                if rng.random() < 0.02:  # corrected resubmission (duplicate)
                    fixed = dict(row)
                    field = rng.choice(list(PROFILES[team]))
                    current = fixed[field] if isinstance(fixed[field], int) else 0
                    fixed[field] = max(0, current + rng.choice([-2, -1, 1, 2, 5]))
                    later = submitted + timedelta(minutes=rng.randint(5, 90))
                    fixed["Timestamp"] = fmt_ts(later)
                    rows.append(fixed)
    rows.sort(key=lambda r: datetime.strptime(r["Timestamp"], "%m/%d/%Y %H:%M:%S"))
    return rows


def main() -> None:
    rng = random.Random(SEED)
    np_rng = np.random.default_rng(SEED)
    schedules = make_schedules(rng)
    rows = make_responses(schedules, rng, np_rng)
    OUT_DIR.mkdir(exist_ok=True)
    columns = [
        "Timestamp",
        "Name",
        "Date",
        "Assigned Section",
        *config.ALL_NUMERIC_FIELDS,
    ]
    pd.DataFrame(rows, columns=columns).to_csv(
        OUT_DIR / "demo_responses.csv", index=False
    )
    (OUT_DIR / "demo_schedules.json").write_text(json.dumps(schedules, indent=1))
    print(f"{len(rows)} responses, {len(schedules)} weekly schedules")


if __name__ == "__main__":
    main()
