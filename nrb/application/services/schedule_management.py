"""Use cases for generating and saving weekly team schedules."""

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from nrb.domain import roles, scheduling, weeks
from nrb.application.errors import call_infrastructure
from nrb.application.services.authorization import AuthorizationService


class ScheduleRepository(Protocol):
    def list_staff(self, active_only: bool = False) -> list[dict]: ...

    def list_teams(self, active_only: bool = False) -> list[dict]: ...

    def assignment_history(self) -> list[dict]: ...

    def upsert_team(
        self,
        name: str,
        reports_as_section: str,
        min_size: int,
        max_size: int,
        pinned_members: list[str],
        active: bool,
        sort_order: int,
        team_id: str | None = None,
    ) -> None: ...

    def delete_team(self, team_id: str) -> None: ...

    def list_schedules(self, limit: int = 30) -> list[dict]: ...

    def get_schedule(self, week_start: str) -> dict | None: ...

    def delete_schedule(self, week_start: str) -> None: ...

    def save_schedule(
        self,
        week_start: str,
        week_end: str,
        assignments: list[tuple[str, str, int]],
        created_by: str = "",
    ) -> None: ...


@dataclass
class ScheduleService:
    repository: ScheduleRepository
    authorization: AuthorizationService

    def list_staff(self, active_only: bool = False) -> list[dict]:
        return call_infrastructure(
            "Load scheduling roster",
            "Could not load staff. Please try again later.",
            self.repository.list_staff,
            active_only,
        )

    def list_teams(self, active_only: bool = False) -> list[dict]:
        return call_infrastructure(
            "Load teams",
            "Could not load teams. Please try again later.",
            self.repository.list_teams,
            active_only,
        )

    def assignment_history(self) -> list[dict]:
        return call_infrastructure(
            "Load schedule assignment history",
            "Could not load schedule history. Please try again later.",
            self.repository.assignment_history,
        )

    def upsert_team(
        self,
        name,
        reports_as_section,
        min_size,
        max_size,
        pinned_members,
        active,
        sort_order,
        team_id,
        actor,
    ) -> None:
        self._require_admin(actor)
        if not name.strip():
            raise ValueError("Team name is required.")
        if max_size < min_size:
            raise ValueError("Max size must be greater than or equal to min size.")
        call_infrastructure(
            "Save team",
            "Could not save the team. Please try again later.",
            self.repository.upsert_team,
            name,
            reports_as_section,
            min_size,
            max_size,
            pinned_members,
            active,
            sort_order,
            team_id,
        )

    def delete_team(self, team_id: str, actor: dict | None) -> None:
        self._require_admin(actor)
        call_infrastructure(
            "Delete team",
            "Could not delete the team. Please try again later.",
            self.repository.delete_team,
            team_id,
        )

    def list_schedules(self, limit: int = 30) -> list[dict]:
        return call_infrastructure(
            "Load schedules",
            "Could not load schedules. Please try again later.",
            self.repository.list_schedules,
            limit,
        )

    def get_schedule(self, week_start: str) -> dict | None:
        return call_infrastructure(
            "Load schedule details",
            "Could not load that schedule. Please try again later.",
            self.repository.get_schedule,
            week_start,
        )

    def schedule_for_week(self, day: date) -> dict | None:
        """The saved schedule for the Mon–Fri week containing `day`, if any."""
        monday, _ = weeks.work_week_of(day)
        return self.get_schedule(monday.isoformat())

    def delete_schedule(self, week_start: str, actor: dict | None) -> None:
        self.authorization.require(actor, roles.EDIT_SCHEDULE)
        call_infrastructure(
            "Delete schedule",
            "Could not delete the schedule. Please try again later.",
            self.repository.delete_schedule,
            week_start,
        )

    def generate_schedule(self, available: list, teams: list) -> dict:
        history = self.assignment_history()
        return scheduling.generate_schedule(available, teams, history)

    def carry_packages(
        self,
        source_week_start: str,
        moves: dict[str, str],
        available: list[str],
        teams: list[dict],
    ) -> dict:
        """Draft (not saved) from moving a saved week's team packages."""
        source = self.get_schedule(source_week_start)
        if source is None:
            raise ValueError("That saved week is no longer available.")
        return scheduling.carry_packages(source["assignments"], moves, available, teams)

    def save_schedule(
        self,
        week_start: str,
        week_end: str,
        assignments: list[tuple[str, str, int]],
        available_staff: list[str],
        actor: dict | None,
    ) -> None:
        """Create the week's schedule, or replace it when allowed to edit."""
        principal = self.authorization.require(actor, roles.CREATE_SCHEDULE)
        if not roles.has_permission(
            principal.get("role"), roles.EDIT_SCHEDULE
        ) and self.get_schedule(week_start):
            raise PermissionError(
                "A schedule already exists for this week. Only administrators "
                "can change it."
            )
        active_teams = self.list_teams(active_only=True)
        active_staff = self.list_staff(active_only=True)
        scheduling.validate_schedule(
            week_start,
            week_end,
            assignments,
            active_teams,
            active_staff,
            available_staff,
        )
        call_infrastructure(
            "Save schedule",
            "Could not save the schedule. Please try again later.",
            self.repository.save_schedule,
            week_start,
            week_end,
            assignments,
            created_by=principal["username"],
        )

    def _require_admin(self, actor: dict | None) -> dict:
        return self.authorization.require_admin(actor)
