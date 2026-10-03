"""Use case for monthly report footer settings."""

from dataclasses import dataclass
from typing import Protocol

from nrb import config
from nrb.application.errors import call_infrastructure
from nrb.application.services.authorization import AuthorizationService


class ReportFooterRepository(Protocol):
    def get_setting(self, key: str, default=None): ...

    def set_setting(self, key: str, value) -> None: ...


@dataclass(frozen=True)
class ReportFooter:
    planned_activities: str
    compiled_by: str


@dataclass
class ReportFooterService:
    repository: ReportFooterRepository
    authorization: AuthorizationService

    def get_footer(self) -> ReportFooter:
        return ReportFooter(
            planned_activities=call_infrastructure(
                "Load report footer settings",
                "Could not load report footer settings. Please try again later.",
                self.repository.get_setting,
                "planned_activities",
                config.DEFAULT_PLANNED_ACTIVITIES,
            ),
            compiled_by=call_infrastructure(
                "Load report footer settings",
                "Could not load report footer settings. Please try again later.",
                self.repository.get_setting,
                "compiled_by",
                config.DEFAULT_COMPILED_BY,
            ),
        )

    def save_footer(
        self, planned_activities: str, compiled_by: str, actor: dict | None
    ) -> ReportFooter:
        self.authorization.require_admin(actor)
        call_infrastructure(
            "Save planned report activities",
            "Could not save report footer text. Please try again later.",
            self.repository.set_setting,
            "planned_activities",
            planned_activities,
        )
        call_infrastructure(
            "Save report compiler text",
            "Could not save report footer text. Please try again later.",
            self.repository.set_setting,
            "compiled_by",
            compiled_by,
        )
        return ReportFooter(planned_activities, compiled_by)
