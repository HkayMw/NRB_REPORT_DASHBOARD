import pandas as pd

from nrb.domain.cleaning import clean_responses


def test_clean_responses_keeps_latest_duplicate_and_reports_quality_findings():
    responses = pd.DataFrame(
        {
            "Timestamp": [
                "2026-09-01 09:00:00",
                "2026-09-01 10:00:00",
                "2026-09-02 09:00:00",
                "2026-09-01 11:00:00",
            ],
            "Name": ["J.Doe", "J.Doe", "Unknown", "M.Smith"],
            "Date": ["2026-09-01", "2026-09-01", "2026-09-02", "2026-09-10"],
            "Assigned Section": ["ID CAPTURING"] * 4,
            "New applicants captured": [1, 3, 5, 2],
        }
    )

    result = clean_responses(responses, ["J.Doe", "M.Smith"], today="2026-09-05")

    assert len(result.clean) == 2
    assert (
        result.clean.loc[
            result.clean["date"] == pd.Timestamp("2026-09-01"),
            "New applicants captured",
        ].item()
        == 3
    )
    assert len(result.dropped_duplicates) == 1
    assert result.unknown_names["Name"].tolist() == ["Unknown"]
    assert "Future date" in result.issues["issue"].tolist()
