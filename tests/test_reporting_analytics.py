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


def test_scheduled_reporting_comparison_marks_unreported_and_extra_people():
    clean = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-10-06", "2026-10-06"]),
            "names_list": [["Alice"], ["Bob"]],
        }
    )
    schedule = {
        "schedule": {"week_start": "2026-10-05"},
        "assignments": [
            {"team_name": "Capturing", "staff_name": "Alice"},
            {"team_name": "Distribution", "staff_name": "Cara"},
        ],
    }

    rows, extras = reporting_analytics.scheduled_reporting_comparison(clean, schedule)

    assert rows == [
        {"Team": "Capturing", "Staff": "Alice", "Reported this week": "✅"},
        {"Team": "Distribution", "Staff": "Cara", "Reported this week": "❌"},
    ]
    assert extras == ["Bob"]
