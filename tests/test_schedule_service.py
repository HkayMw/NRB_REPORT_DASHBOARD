import pytest

from nrb.application.services.authorization import AuthorizationService
from nrb.application.services.schedule_management import ScheduleService


class FakeScheduleRepository:
    def __init__(self, history=None):
        self.history = history or []
        self.saved = []
        self.teams = [
            {
                "id": "team-1",
                "name": "Team",
                "min_size": 1,
                "max_size": 2,
                "pinned_members": [],
                "active": 1,
            }
        ]
        self.staff = [
            {
                "form_name": "Alice",
                "full_name": "Alice Example",
                "active": 1,
            }
        ]
        self.schedules = []
        self.team_writes = []
        self.deleted_teams = []
        self.deleted_schedules = []
        self.principals = {
            "admin": {"id": "admin", "username": "admin", "role": "admin", "active": 1},
            "admin-id": {
                "id": "admin-id",
                "username": "admin",
                "role": "admin",
                "active": 1,
            },
            "viewer": {
                "id": "viewer",
                "username": "viewer",
                "role": "viewer",
                "active": 1,
            },
        }

    def get_user_by_id(self, user_id):
        return self.principals.get(user_id)

    def list_staff(self, active_only=False):
        return [
            staff for staff in self.staff if not active_only or staff.get("active", 1)
        ]

    def list_teams(self, active_only=False):
        return [team for team in self.teams if not active_only or team.get("active", 1)]

    def assignment_history(self):
        return self.history

    def save_schedule(self, week_start, week_end, assignments, created_by=""):
        self.saved.append((week_start, week_end, assignments, created_by))

    def upsert_team(
        self,
        name,
        reports_as_section,
        min_size,
        max_size,
        pinned_members,
        active,
        sort_order,
        team_id=None,
    ):
        self.team_writes.append(
            (
                name,
                reports_as_section,
                min_size,
                max_size,
                pinned_members,
                active,
                sort_order,
                team_id,
            )
        )

    def delete_team(self, team_id):
        self.deleted_teams.append(team_id)

    def list_schedules(self, limit=30):
        return self.schedules

    def get_schedule(self, week_start):
        return next(
            (
                schedule
                for schedule in self.schedules
                if schedule["schedule"]["week_start"] == week_start
            ),
            None,
        )

    def delete_schedule(self, week_start):
        self.deleted_schedules.append(week_start)


def test_generate_schedule_uses_repository_history():
    repository = FakeScheduleRepository(
        [
            {
                "week_start": "2026-09-28",
                "team_id": "team-1",
                "staff_name": "Alice",
            }
        ]
    )
    service = ScheduleService(repository, AuthorizationService(repository))
    teams = [
        {
            "id": "team-1",
            "pinned_members": [],
            "min_size": 1,
            "max_size": 1,
            "sort_order": 0,
        }
    ]

    result = service.generate_schedule(["Alice", "Bob"], teams)

    assert result == {"assignment": {"team-1": ["Bob"]}, "unplaced": ["Alice"]}


def test_save_schedule_rejects_non_admin_without_writing():
    repository = FakeScheduleRepository()
    service = ScheduleService(repository, AuthorizationService(repository))

    with pytest.raises(PermissionError):
        service.save_schedule(
            "2026-10-05",
            "2026-10-09",
            [],
            [],
            {
                "id": "viewer",
                "username": "viewer",
                "role": "admin",
            },
        )

    assert repository.saved == []


def test_admin_save_schedule_passes_actor_to_repository():
    repository = FakeScheduleRepository()
    service = ScheduleService(repository, AuthorizationService(repository))
    assignments = [("team-1", "Alice", 0)]

    service.save_schedule(
        "2026-10-05",
        "2026-10-09",
        assignments,
        ["Alice"],
        {
            "id": "admin",
            "username": "admin",
            "role": "viewer",
        },
    )

    assert repository.saved == [
        (
            "2026-10-05",
            "2026-10-09",
            assignments,
            "admin",
        )
    ]


def test_save_schedule_rejects_non_roster_assignment_before_repository_write():
    repository = FakeScheduleRepository()
    service = ScheduleService(repository, AuthorizationService(repository))

    with pytest.raises(ValueError, match="active roster members"):
        service.save_schedule(
            "2026-10-05",
            "2026-10-09",
            [("team-1", "Visitor", 0)],
            ["Visitor"],
            {"id": "admin", "username": "admin", "role": "admin"},
        )

    assert repository.saved == []


def test_team_mutations_require_admin_and_validate_size():
    repository = FakeScheduleRepository()
    service = ScheduleService(repository, AuthorizationService(repository))

    with pytest.raises(PermissionError):
        service.delete_team("team-1", {"id": "viewer", "role": "admin"})
    with pytest.raises(ValueError, match="Max size"):
        service.upsert_team(
            "Team", "", 3, 2, [], True, 0, None, {"id": "admin", "role": "admin"}
        )

    assert repository.deleted_teams == []
    assert repository.team_writes == []


def test_admin_can_upsert_team_and_delete_schedule():
    repository = FakeScheduleRepository()
    service = ScheduleService(repository, AuthorizationService(repository))
    admin = {"id": "admin", "username": "admin", "role": "viewer"}

    service.upsert_team("New team", "ID CAPTURING", 1, 2, [], True, 0, None, admin)
    service.delete_schedule("2026-10-05", admin)

    assert repository.team_writes == [
        (
            "New team",
            "ID CAPTURING",
            1,
            2,
            [],
            True,
            0,
            None,
        )
    ]
    assert repository.deleted_schedules == ["2026-10-05"]
