"""Reporting calculations shared by Streamlit pages."""

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from nrb import config
from nrb.domain import cleaning, report_config, weeks


@dataclass(frozen=True)
class MonthlyBlockPreview:
    title: str
    rows: list[tuple[str, int]]
    total_label: str | None
    total: int


@dataclass(frozen=True)
class MonthlyWeekPreview:
    number: int
    start: date
    end: date
    submission_count: int
    blocks: list[MonthlyBlockPreview]


@dataclass(frozen=True)
class MonthlyReportPreview:
    month_data: pd.DataFrame
    weeks: list[MonthlyWeekPreview]
    summary: pd.DataFrame


@dataclass(frozen=True)
class OverviewMetric:
    title: str
    value: int
    previous_value: int
    period_days: int


def build_monthly_preview(
    clean: pd.DataFrame, year: int, month: int, cfg: dict
) -> MonthlyReportPreview:
    period = pd.Period(year=year, month=month, freq="M")
    month_data = clean[clean["date"].dt.to_period("M") == period]
    week_ranges = weeks.month_weeks(year, month)
    week_previews = []
    summary_rows = []
    summary_columns = report_config.summary_columns(cfg)

    for week_number, start, end in week_ranges:
        week_frame = month_data[
            (month_data["date"] >= pd.Timestamp(start))
            & (month_data["date"] <= pd.Timestamp(end))
        ]
        computed = {}
        block_previews = []
        for group_index, group in enumerate(cfg["groups"]):
            for block_index, block in enumerate(group["blocks"]):
                values = report_config.compute_block(week_frame, block)
                computed[(group_index, block_index)] = values
                block_previews.append(
                    MonthlyBlockPreview(
                        title=block["title"],
                        rows=values["rows"],
                        total_label=block.get("total_label"),
                        total=values["total"],
                    )
                )

        summary_row = {"Week": f"Week {week_number} ({start.day}–{end.day})"}
        for group_title, label, (
            group_index,
            block_index,
            row_index,
        ) in summary_columns:
            block_values = computed[(group_index, block_index)]
            value = (
                block_values["total"]
                if row_index == "total"
                else block_values["rows"][row_index][1]
            )
            summary_row[f"{group_title} · {label}"] = value
        summary_rows.append(summary_row)
        week_previews.append(
            MonthlyWeekPreview(
                number=week_number,
                start=start,
                end=end,
                submission_count=len(week_frame),
                blocks=block_previews,
            )
        )

    summary = pd.DataFrame(summary_rows).set_index("Week")
    summary.loc["TOTALS"] = summary.sum()
    return MonthlyReportPreview(month_data, week_previews, summary)


def overview_metrics(
    clean: pd.DataFrame,
    selected: pd.DataFrame,
    start: date,
    end: date,
    cfg: dict,
) -> list[OverviewMetric]:
    period_days = (pd.Timestamp(end) - pd.Timestamp(start)).days + 1
    previous = clean[
        (clean["date"] >= pd.Timestamp(start) - pd.Timedelta(days=period_days))
        & (clean["date"] < pd.Timestamp(start))
    ]
    return [
        OverviewMetric(
            title=block["title"],
            value=report_config.compute_block(selected, block)["total"],
            previous_value=report_config.compute_block(previous, block)["total"],
            period_days=period_days,
        )
        for group in cfg["groups"]
        for block in group["blocks"]
    ]


def overview_trends(
    frame: pd.DataFrame, cfg: dict, selected_titles: list[str]
) -> pd.DataFrame:
    rows: list[dict] = []
    for group in cfg["groups"]:
        for block in group["blocks"]:
            if block["title"] not in selected_titles:
                continue
            fields = [field for row in block["rows"] for field in row["fields"]]
            daily = frame.groupby("date")[fields].sum().sum(axis=1)
            rows.extend(
                {"date": day, "metric": block["title"], "value": value}
                for day, value in daily.items()
            )
    return pd.DataFrame(rows, columns=["date", "metric", "value"])


def section_activity(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily = frame.groupby(["date", "section"]).size().reset_index(name="submissions")
    summary = (
        frame.groupby("section")
        .agg(
            submissions=("date", "count"),
            first=("date", "min"),
            last=("date", "max"),
        )
        .reset_index()
    )
    return daily, summary


def section_field_totals(frame: pd.DataFrame, section: str) -> pd.Series:
    fields = config.SECTION_FIELDS[section]
    return (
        frame.loc[frame["section"] == section, fields].sum().astype(int).sort_values()
    )


def compliance_section_coverage(
    frame: pd.DataFrame, start: date, end: date
) -> tuple[pd.DataFrame, int]:
    all_days = pd.date_range(start, end, freq="D")
    grid = (
        frame.groupby(["date", "section"])
        .size()
        .unstack(fill_value=0)
        .reindex(all_days, fill_value=0)
    )
    for section in config.SECTION_FIELDS:
        if section not in grid.columns:
            grid[section] = 0
    grid = grid[list(config.SECTION_FIELDS)]
    missing = int((grid == 0).sum().sum())
    grid.index = grid.index.strftime("%a %d %b %Y")
    return grid, missing


def compliance_people_activity(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    people = cleaning.explode_people(frame)
    per_person = (
        people.groupby("person")
        .agg(
            submissions=("date", "count"),
            days=("date", "nunique"),
            sections=("section", lambda values: ", ".join(sorted(values.unique()))),
            last_report=("date", "max"),
        )
        .sort_values("submissions", ascending=False)
        .reset_index()
    )
    if not per_person.empty:
        per_person["last_report"] = per_person["last_report"].dt.date
    return people, per_person


def compliance_person_detail(people: pd.DataFrame, person: str) -> pd.DataFrame:
    detail = people.loc[
        people["person"] == person, ["date", "section", config.NAME_COL]
    ].copy()
    detail["date"] = detail["date"].dt.date
    return detail.sort_values("date", ascending=False)


REPORTED = "✅"
OTHER_SECTION = "⚠️"
MISSING = "❌"
PENDING = "·"
NOT_REQUIRED = ""


@dataclass(frozen=True)
class DailyComplianceDay:
    day: date
    enforced: bool  # weekday that has already started
    expected: int  # scheduled people who had to report (0 when not enforced)
    reported: int  # scheduled people named on any submission that day
    unscheduled: list[str]  # reported but not on the schedule


@dataclass(frozen=True)
class DailyComplianceWeek:
    week_start: date
    days: list[DailyComplianceDay]
    grid: pd.DataFrame


def day_column(day: date) -> str:
    return day.strftime("%a %d %b")


def daily_reporting_compliance(
    clean: pd.DataFrame, week_start: date, assignments: list[dict], today: date
) -> DailyComplianceWeek:
    """Per-person, per-day reporting status for one Mon–Sun week.

    A person has reported on a day when their name is on a submission for that
    date. Reporting for a section other than their team's `reports_as_section`
    is a soft warning; a missing `reports_as_section` accepts any section.
    Weekdays up to `today` are enforced; weekends are shown but never missing.
    """
    days = [week_start + timedelta(days=offset) for offset in range(7)]
    week_people = cleaning.explode_people(
        clean[
            (clean["date"] >= pd.Timestamp(days[0]))
            & (clean["date"] <= pd.Timestamp(days[-1]))
        ]
    )
    sections_by_person_day: dict[tuple[str, date], set[str]] = {}
    for row in week_people.itertuples(index=False):
        key = (row.person, row.date.date())
        sections_by_person_day.setdefault(key, set()).add(row.section)

    scheduled = {assignment["staff_name"] for assignment in assignments}
    rows = []
    for assignment in assignments:
        expected_section = assignment.get("reports_as_section")
        row = {"Team": assignment["team_name"], "Staff": assignment["staff_name"]}
        missed = 0
        for day in days:
            sections = sections_by_person_day.get((assignment["staff_name"], day))
            if sections:
                ok = expected_section is None or expected_section in sections
                status = REPORTED if ok else OTHER_SECTION
            elif day > today:
                status = PENDING
            elif day.weekday() >= 5:
                status = NOT_REQUIRED
            else:
                status = MISSING
                missed += 1
            row[day_column(day)] = status
        row["Missed days"] = missed
        rows.append(row)
    grid = pd.DataFrame(
        rows, columns=["Team", "Staff", *map(day_column, days), "Missed days"]
    )

    summary = []
    for day in days:
        reporters = {person for person, d in sections_by_person_day if d == day}
        enforced = day.weekday() < 5 and day <= today
        summary.append(
            DailyComplianceDay(
                day=day,
                enforced=enforced,
                expected=len(scheduled) if enforced else 0,
                reported=len(reporters & scheduled),
                unscheduled=sorted(reporters - scheduled),
            )
        )
    return DailyComplianceWeek(week_start=week_start, days=summary, grid=grid)


def day_reports(clean: pd.DataFrame, day: date) -> pd.DataFrame:
    """Who reported which section on one day, one row per person."""
    people = cleaning.explode_people(clean[clean["date"] == pd.Timestamp(day)])
    if people.empty:
        return pd.DataFrame(columns=["Person", "Section", "Submitted as"])
    return (
        people[["person", "section", config.NAME_COL]]
        .rename(
            columns={
                "person": "Person",
                "section": "Section",
                config.NAME_COL: "Submitted as",
            }
        )
        .sort_values(["Person", "Section"])
        .reset_index(drop=True)
    )
