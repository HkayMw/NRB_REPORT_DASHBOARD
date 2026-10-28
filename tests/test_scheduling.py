import pytest

from nrb.domain.scheduling import (
    carry_packages,
    generate_schedule,
    validate_schedule,
)


def _validate(
    assignments,
    *,
    teams=None,
    staff=None,
    available=None,
    week_start="2026-10-05",
    week_end="2026-10-09",
):
    validate_schedule(
        week_start,
        week_end,
        assignments,
        teams
        or [
            {
                "id": "team-1",
                "name": "Team One",
                "min_size": 1,
                "max_size": 2,
                "pinned_members": [],
            }
        ],
        staff or [{"form_name": name} for name in ("Alice", "Bob", "Cara")],
        available or ["Alice", "Bob", "Cara"],
    )


def test_generate_schedule_prefers_person_with_longest_team_absence():
    teams = [
        {
            "id": "team-1",
            "pinned_members": [],
            "min_size": 1,
            "max_size": 1,
            "sort_order": 0,
        },
        {
            "id": "team-2",
            "pinned_members": [],
            "min_size": 1,
            "max_size": 1,
            "sort_order": 1,
        },
    ]
    history = [
        {"week_start": "2026-09-28", "team_id": "team-1", "staff_name": "Alice"},
        {"week_start": "2026-09-21", "team_id": "team-1", "staff_name": "Bob"},
    ]

    result = generate_schedule(["Alice", "Bob"], teams, history)

    assert result == {
        "assignment": {"team-1": ["Bob"], "team-2": ["Alice"]},
        "unplaced": [],
    }


def test_validate_schedule_accepts_valid_schedule_and_absent_pin():
    team = {
        "id": "team-1",
        "name": "Team One",
        "min_size": 1,
        "max_size": 2,
        "pinned_members": ["Alice"],
    }

    _validate([("team-1", "Bob", 0)], teams=[team], available=["Bob"])


@pytest.mark.parametrize(
    "week_start,week_end,message",
    [
        ("2026-10-06", "2026-10-09", "Monday"),
        ("2026-10-05", "2026-10-10", "Friday"),
        ("not-a-date", "2026-10-09", "ISO dates"),
    ],
)
def test_validate_schedule_rejects_invalid_week_dates(week_start, week_end, message):
    with pytest.raises(ValueError, match=message):
        _validate([("team-1", "Alice", 0)], week_start=week_start, week_end=week_end)


def test_validate_schedule_rejects_inactive_unavailable_and_unknown_members():
    with pytest.raises(ValueError, match="not active"):
        _validate([("team-1", "Unknown", 0)])
    with pytest.raises(ValueError, match="not available"):
        _validate([("team-1", "Alice", 0)], available=["Bob"])
    with pytest.raises(ValueError, match="active roster members"):
        _validate([("team-1", "Alice", 0)], available=["Visitor"])


def test_validate_schedule_rejects_unknown_team_and_duplicate_membership():
    with pytest.raises(ValueError, match="active teams"):
        _validate([("missing", "Alice", 0)])
    with pytest.raises(ValueError, match="only be assigned once"):
        _validate([("team-1", "Alice", 0), ("team-1", "Alice", 1)])


def test_validate_schedule_enforces_capacity_and_pinned_assignment():
    team = {
        "id": "team-1",
        "name": "Team One",
        "min_size": 2,
        "max_size": 2,
        "pinned_members": ["Alice"],
    }

    with pytest.raises(ValueError, match="between 2 and 2"):
        _validate([("team-1", "Alice", 0)], teams=[team])
    with pytest.raises(ValueError, match="between 2 and 2"):
        _validate(
            [
                ("team-1", "Alice", 0),
                ("team-1", "Bob", 1),
                ("team-1", "Cara", 2),
            ],
            teams=[team],
        )
    with pytest.raises(ValueError, match="pinned member 'Alice'"):
        _validate([("team-1", "Bob", 0), ("team-1", "Cara", 1)], teams=[team])


def package_teams():
    return [
        {
            "id": "cap",
            "name": "Capturing",
            "min_size": 2,
            "max_size": 3,
            "pinned_members": ["Pia"],
        },
        {
            "id": "dist",
            "name": "Distribution",
            "min_size": 2,
            "max_size": 2,
            "pinned_members": [],
        },
    ]


def test_carry_packages_swaps_teams_keeping_people_together():
    source = [
        {"team_id": "cap", "staff_name": "Pia", "position": 0},
        {"team_id": "cap", "staff_name": "Ann", "position": 1},
        {"team_id": "cap", "staff_name": "Ben", "position": 2},
        {"team_id": "dist", "staff_name": "Cy", "position": 0},
        {"team_id": "dist", "staff_name": "Di", "position": 1},
    ]

    result = carry_packages(
        source,
        {"cap": "dist", "dist": "cap"},
        ["Pia", "Ann", "Ben", "Cy", "Di"],
        package_teams(),
    )

    assert result["assignment"] == {"cap": ["Pia", "Cy", "Di"], "dist": ["Ann", "Ben"]}
    assert result["unplaced"] == []
    assert result["notes"] == ["Pia stayed on Capturing (pinned)."]


def test_carry_packages_leaves_gaps_and_unplaced_overflow():
    source = [
        {"team_id": "cap", "staff_name": "Ann", "position": 0},
        {"team_id": "cap", "staff_name": "Ben", "position": 1},
        {"team_id": "cap", "staff_name": "Eve", "position": 2},
        {"team_id": "dist", "staff_name": "Cy", "position": 0},
        {"team_id": "dist", "staff_name": "Di", "position": 1},
    ]

    result = carry_packages(
        source,
        {"cap": "dist", "dist": "cap"},
        ["Ann", "Ben", "Eve", "Cy", "Fay"],  # Di away, Fay not carried
        package_teams(),
    )

    assert result["assignment"] == {"cap": ["Cy"], "dist": ["Ann", "Ben"]}
    assert result["unplaced"] == ["Eve", "Fay"]
    assert "Eve not placed — Distribution is full (max 2)." in result["notes"]
    assert "Di is away — gap left on Capturing." in result["notes"]
    assert "Capturing needs 1 more (min 2) — add someone manually." in result["notes"]


def test_carry_packages_skips_uncarried_and_inactive_targets():
    source = [
        {"team_id": "cap", "staff_name": "Ann", "position": 0},
        {"team_id": "old", "staff_name": "Ben", "position": 0},
    ]

    result = carry_packages(
        source, {"old": "gone"}, ["Ann", "Ben", "Pia"], package_teams()
    )

    assert result["assignment"] == {"cap": ["Pia"], "dist": []}
    assert result["unplaced"] == ["Ann", "Ben"]
