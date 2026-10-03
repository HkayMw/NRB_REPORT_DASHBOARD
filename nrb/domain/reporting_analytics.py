"""Reporting calculations shared by Streamlit pages."""

from dataclasses import dataclass
from datetime import date

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


def scheduled_reporting_comparison(
    clean: pd.DataFrame, schedule: dict
) -> tuple[list[dict], list[str]]:
    week_start = pd.Timestamp(schedule["schedule"]["week_start"])
    week_end = week_start + pd.Timedelta(days=6)
    week_people = cleaning.explode_people(
        clean[(clean["date"] >= week_start) & (clean["date"] <= week_end)]
    )
    reported = set(week_people["person"]) if not week_people.empty else set()
    assignments = schedule["assignments"]
    rows = [
        {
            "Team": assignment["team_name"],
            "Staff": assignment["staff_name"],
            "Reported this week": "✅"
            if assignment["staff_name"] in reported
            else "❌",
        }
        for assignment in assignments
    ]
    extras = sorted(reported - {assignment["staff_name"] for assignment in assignments})
    return rows, extras
