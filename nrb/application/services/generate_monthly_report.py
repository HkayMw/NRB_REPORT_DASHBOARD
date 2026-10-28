"""Application use case for generating a monthly report workbook."""

from dataclasses import dataclass
from io import BytesIO
from typing import Protocol

import pandas as pd

from nrb.application.errors import call_infrastructure


class MonthlyReportExporter(Protocol):
    def build_monthly_workbook(
        self,
        clean: pd.DataFrame,
        year: int,
        month: int,
        cfg: dict,
        planned_activities: str,
        compiled_by: str,
    ) -> BytesIO: ...

    def suggested_filename(self, year: int, month: int) -> str: ...


@dataclass(frozen=True)
class GeneratedMonthlyReport:
    workbook: BytesIO
    filename: str


@dataclass
class MonthlyReportService:
    exporter: MonthlyReportExporter

    def generate(
        self,
        clean: pd.DataFrame,
        year: int,
        month: int,
        cfg: dict,
        planned_activities: str,
        compiled_by: str,
    ) -> GeneratedMonthlyReport:
        workbook = call_infrastructure(
            "Generate monthly Excel report",
            "Could not generate the Excel report. Please try again later.",
            self.exporter.build_monthly_workbook,
            clean,
            year,
            month,
            cfg,
            planned_activities,
            compiled_by,
        )
        filename = call_infrastructure(
            "Build monthly report filename",
            "Could not prepare the Excel report download. Please try again later.",
            self.exporter.suggested_filename,
            year,
            month,
        )
        return GeneratedMonthlyReport(workbook, filename)
