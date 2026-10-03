import pytest

from nrb.domain.scheduling import generate_schedule, validate_schedule


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
