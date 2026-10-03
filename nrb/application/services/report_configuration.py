"""Use case for reading and validating monthly report configuration."""

from dataclasses import dataclass
from typing import Protocol

from nrb.application.errors import call_infrastructure
from nrb.application.services.authorization import AuthorizationService
from nrb.domain import report_config


class ReportConfigRepository(Protocol):
    def get_report_config(self) -> dict: ...

    def save_report_config(self, cfg: dict) -> None: ...


@dataclass
class ReportConfigService:
    repository: ReportConfigRepository
    authorization: AuthorizationService

    def get_report_config(self) -> dict:
        return call_infrastructure(
            "Load report layout",
            "Could not load the report layout. Please try again later.",
            self.repository.get_report_config,
        )

    def save_report_config(self, cfg: dict, actor: dict | None) -> None:
        self.authorization.require_admin(actor)
        errors = report_config.validate(cfg)
        if errors:
            raise ValueError("; ".join(errors))
        call_infrastructure(
            "Save report layout",
            "Could not save the report layout. Please try again later.",
            self.repository.save_report_config,
            cfg,
        )
