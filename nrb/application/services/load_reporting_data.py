"""Application workflow for loading and cleaning reporting data."""

from dataclasses import dataclass
from typing import Protocol

import pandas as pd

from nrb import config
from nrb.application.errors import ApplicationError, application_error
from nrb.domain.cleaning import CleanResult, clean_responses


class ReportingDataRepository(Protocol):
    def get_setting(self, key: str, default=None): ...

    def list_staff(self, active_only: bool = False) -> list[dict]: ...


class ReportingSource(Protocol):
    def fetch_responses(self, sheet_url: str) -> pd.DataFrame: ...

    def clear_cache(self) -> None: ...


@dataclass
class ReportingData:
    raw: pd.DataFrame
    cleaned: CleanResult


@dataclass
class ReportingDataService:
    repository: ReportingDataRepository
    source: ReportingSource

    def load(self) -> ReportingData:
        """Fetch responses, load the roster, and apply reporting cleaning rules."""
        try:
            sheet_url = self.repository.get_setting(
                "sheet_url", config.DEFAULT_SHEET_URL
            )
            if not sheet_url:
                raise ApplicationError(
                    "No data source is configured yet. An admin can set the Google "
                    "Sheet URL in Admin -> Data source, or set SHEET_URL in the "
                    "app secrets."
                )
            raw = self.source.fetch_responses(sheet_url)
            roster = [staff["form_name"] for staff in self.repository.list_staff()]
        except ApplicationError:
            raise
        except Exception as error:
            raise application_error(
                "Load reporting data",
                "Could not load form responses. Check the configured sheet and try again.",
                error,
            ) from error
        return ReportingData(raw=raw, cleaned=clean_responses(raw, roster))

    def clear_cache(self) -> None:
        try:
            self.source.clear_cache()
        except Exception as error:
            raise application_error(
                "Clear reporting source cache",
                "Could not refresh form responses. Please try again.",
                error,
            ) from error
