"""Week derivation: Monday–Sunday weeks, clipped to the month's own days."""

import calendar
from datetime import date, timedelta


def month_weeks(year: int, month: int) -> list:
    """[(week_no, start_date, end_date), ...] — Mon–Sun blocks, weekends
    included, containing only days that belong to the given month."""
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    weeks = []
    start = first
    n = 1
    while start <= last:
        # End of this Mon–Sun block: the upcoming Sunday.
        end = start + timedelta(days=6 - start.weekday())
        end = min(end, last)
        weeks.append((n, start, end))
        start = end + timedelta(days=1)
        n += 1
    return weeks


def ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def pretty_range(start: date, end: date) -> str:
    """e.g. '1st June - 7th June, 2026'."""
    s = f"{ordinal(start.day)} {start.strftime('%B')}"
    e = f"{ordinal(end.day)} {end.strftime('%B')}, {end.year}"
    return f"{s} - {e}"


def work_week_of(d: date) -> tuple:
    """Monday and Friday of the week containing d (for schedules)."""
    monday = d - timedelta(days=d.weekday())
    return monday, monday + timedelta(days=4)
