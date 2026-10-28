from datetime import date

import pandas as pd

from nrb.domain import reporting_analytics


def report_layout():
    return {
        "groups": [
            {
                "title": "Identity",
                "summary_title": "Identity",
                "blocks": [
                    {
                        "title": "Captured",
                        "rows": [
                            {
                                "label": "Applications",
                                "fields": ["Captured"],
                                "summary_label": "Applications",
                            }
                        ],
                        "total_label": "Total captured",
                        "total_summary_label": "Total captured",
                    }
                ],
            }
        ]
    }


def test_monthly_preview_computes_week_and_period_totals():
    clean = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-10-01", "2026-10-06"]),
            "Captured": [2, 3],
        }
    )

    preview = reporting_analytics.build_monthly_preview(
        clean, 2026, 10, report_layout()
    )

    assert len(preview.month_data) == 2
    assert preview.weeks[0].submission_count == 1
    assert preview.weeks[0].blocks[0].rows == [("Applications", 2)]
    assert preview.summary.loc["TOTALS", "Identity · Applications"] == 5
    assert preview.summary.loc["TOTALS", "Identity · Total captured"] == 5


def test_overview_metrics_and_trends_compare_periods():
    clean = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-10-04", "2026-10-05", "2026-10-06"]),
            "Captured": [2, 5, 3],
        }
    )
    selected = clean[clean["date"] >= pd.Timestamp("2026-10-05")]

    metrics = reporting_analytics.overview_metrics(
        clean,
        selected,
        pd.Timestamp("2026-10-05").date(),
        pd.Timestamp("2026-10-06").date(),
        report_layout(),
    )
    trends = reporting_analytics.overview_trends(
        selected, report_layout(), ["Captured"]
    )

    assert [
        (metric.value, metric.previous_value, metric.period_days) for metric in metrics
    ] == [(8, 2, 2)]
    assert trends.to_dict(orient="records") == [
        {"date": pd.Timestamp("2026-10-05"), "metric": "Captured", "value": 5},
        {"date": pd.Timestamp("2026-10-06"), "metric": "Captured", "value": 3},
    ]


def test_section_and_compliance_analytics_preserve_reporting_rules():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-10-01", "2026-10-01"]),
            "section": ["ID CAPTURING", "ID CAPTURING"],
            "Name": ["Alice, Bob", "Alice"],
            "names_list": [["Alice", "Bob"], ["Alice"]],
        }
    )

    daily, section_summary = reporting_analytics.section_activity(frame)
    grid, missing = reporting_analytics.compliance_section_coverage(
        frame, pd.Timestamp("2026-10-01").date(), pd.Timestamp("2026-10-02").date()
    )
    people, per_person = reporting_analytics.compliance_people_activity(frame)
    detail = reporting_analytics.compliance_person_detail(people, "Alice")

    assert daily.iloc[0]["submissions"] == 2
    assert section_summary.iloc[0]["submissions"] == 2
    assert grid.loc["Thu 01 Oct 2026", "ID CAPTURING"] == 2
    assert missing == 7
    assert per_person.set_index("person").loc["Alice", "submissions"] == 2
    assert per_person.set_index("person").loc["Bob", "submissions"] == 1
    assert len(detail) == 2


def test_daily_reporting_compliance_enforces_each_weekday():
    clean = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2026-10-05", "2026-10-06", "2026-10-06", "2026-10-10"]
            ),
            "section": ["ID CAPTURING", "ID DISTRIBUTION", "ID CAPTURING", "OTHER"],
            "names_list": [["Alice", "Cara"], ["Alice"], ["Bob"], ["Cara"]],
        }
    )
    assignments = [
        {
            "team_name": "Capturing",
            "staff_name": "Alice",
            "reports_as_section": "ID CAPTURING",
        },
        {
            "team_name": "Distribution",
            "staff_name": "Cara",
            "reports_as_section": "ID DISTRIBUTION",
        },
    ]

    week = reporting_analytics.daily_reporting_compliance(
        clean, date(2026, 10, 5), assignments, today=date(2026, 10, 7)
    )

    grid = week.grid.set_index("Staff")
    assert grid.loc["Alice", "Mon 05 Oct"] == "✅"
    assert grid.loc["Alice", "Tue 06 Oct"] == "⚠️"
    assert grid.loc["Alice", "Wed 07 Oct"] == "❌"
    assert grid.loc["Alice", "Thu 08 Oct"] == "·"
    assert grid.loc["Cara", "Mon 05 Oct"] == "⚠️"
    assert grid.loc["Cara", "Tue 06 Oct"] == "❌"
    assert grid.loc["Cara", "Sat 10 Oct"] == "⚠️"
    assert grid.loc["Alice", "Missed days"] == 1
    assert grid.loc["Cara", "Missed days"] == 2

    monday, tuesday, wednesday, thursday, _, saturday, _ = week.days
    assert (monday.expected, monday.reported) == (2, 2)
    assert (tuesday.expected, tuesday.reported, tuesday.unscheduled) == (
        2,
        1,
        ["Bob"],
    )
    assert (wednesday.enforced, wednesday.reported) == (True, 0)
    assert (thursday.enforced, thursday.expected) == (False, 0)
    assert (saturday.enforced, saturday.reported) == (False, 1)


def test_daily_reporting_compliance_accepts_any_section_without_team():
    clean = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-10-05"]),
            "section": ["ID CAPTURING"],
            "names_list": [["Alice"]],
        }
    )

    week = reporting_analytics.daily_reporting_compliance(
        clean,
        date(2026, 10, 5),
        [{"team_name": "—", "staff_name": "Alice"}],
        today=date(2026, 10, 11),
    )

    row = week.grid.iloc[0]
    assert row["Mon 05 Oct"] == "✅"
    assert row["Sun 11 Oct"] == ""
    assert row["Missed days"] == 4


def test_day_reports_lists_each_person_and_section():
    clean = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-10-05", "2026-10-06"]),
            "section": ["ID CAPTURING", "ID CAPTURING"],
            "Name": ["Bob, Alice", "Cara"],
            "names_list": [["Bob", "Alice"], ["Cara"]],
        }
    )

    reports = reporting_analytics.day_reports(clean, date(2026, 10, 5))

    assert reports["Person"].tolist() == ["Alice", "Bob"]
    assert set(reports["Submitted as"]) == {"Bob, Alice"}
    assert reporting_analytics.day_reports(clean, date(2026, 10, 7)).empty
