"""Use cases for data-source settings and staff-roster administration."""

from dataclasses import dataclass
from typing import Callable, Protocol

import pandas as pd

from nrb import config
from nrb.application.errors import application_error, call_infrastructure
from nrb.application.services.authorization import AuthorizationService
from nrb.domain import roles


class AdminSettingsRepository(Protocol):
    def get_setting(self, key: str, default=None): ...

    def set_setting(self, key: str, value) -> None: ...

    def list_staff(self) -> list[dict]: ...

    def upsert_staff(
        self,
        form_name: str,
        full_name: str,
        active: bool,
        staff_id: str | None = None,
    ) -> None: ...

    def delete_staff(self, staff_id: str) -> None: ...


@dataclass
class AdminSettingsService:
    repository: AdminSettingsRepository
    fetch_responses: Callable[[str], pd.DataFrame]
    clear_sheet_cache: Callable[[], None]
    authorization: AuthorizationService

    def get_sheet_url(self) -> str:
        return call_infrastructure(
            "Load reporting sheet URL",
            "Could not load the reporting sheet setting. Please try again later.",
            self.repository.get_setting,
            "sheet_url",
            config.DEFAULT_SHEET_URL,
        )

    def test_and_save_sheet_url(
        self, sheet_url: str, actor: dict | None
    ) -> pd.DataFrame:
        self._require_admin(actor)
        try:
            responses = self.fetch_responses(sheet_url)
            self.repository.set_setting("sheet_url", sheet_url)
        except Exception as error:
            raise application_error(
                "Test and save reporting sheet URL",
                "Could not read that sheet. Check the URL and sharing access.",
                error,
            ) from error
        return responses

    def clear_source_cache(self, actor: dict | None) -> None:
        self._require_admin(actor)
        try:
            self.clear_sheet_cache()
        except Exception as error:
            raise application_error(
                "Clear reporting sheet cache",
                "Could not refresh form responses. Please try again.",
                error,
            ) from error

    def get_public_viewing(self) -> bool:
        return call_infrastructure(
            "Load dashboard access setting",
            "Could not load dashboard access settings. Please try again later.",
            self.repository.get_setting,
            "public_viewing",
            True,
        )

    def can_view_dashboard(self, is_logged_in: bool) -> bool:
        return self.get_public_viewing() or is_logged_in

    def set_public_viewing(self, enabled: bool, actor: dict | None) -> None:
        self._require_admin(actor)
        call_infrastructure(
            "Save dashboard access setting",
            "Could not save dashboard access settings. Please try again later.",
            self.repository.set_setting,
            "public_viewing",
            enabled,
        )

    def list_staff(self) -> list[dict]:
        return call_infrastructure(
            "Load staff roster",
            "Could not load the staff roster. Please try again later.",
            self.repository.list_staff,
        )

    def save_roster(self, rows: list[dict], actor: dict | None) -> None:
        self.authorization.require(actor, roles.MANAGE_ROSTER)
        names = [
            str(row.get("Form name", "")).strip()
            for row in rows
            if str(row.get("Form name", "")).strip()
        ]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate form names in the table.")

        try:
            existing = {
                staff["form_name"]: staff for staff in self.repository.list_staff()
            }
            for row in rows:
                form_name = str(row.get("Form name", "")).strip()
                if not form_name:
                    continue
                previous = existing.pop(form_name, None)
                self.repository.upsert_staff(
                    form_name,
                    str(row.get("Full name", "") or ""),
                    bool(row.get("Active", True)),
                    staff_id=previous["id"] if previous else None,
                )
            for staff in existing.values():
                self.repository.delete_staff(staff["id"])
        except Exception as error:
            raise application_error(
                "Save staff roster",
                "Could not save the staff roster. Please check the database and try again.",
                error,
            ) from error

    def _require_admin(self, actor: dict | None) -> None:
        self.authorization.require_admin(actor)
