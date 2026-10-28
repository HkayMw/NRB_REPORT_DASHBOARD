from io import BytesIO

import pandas as pd
import pytest

from nrb.application.errors import ApplicationError
from nrb.application.services.generate_monthly_report import MonthlyReportService


class FakeExporter:
    def __init__(self):
        self.build_args = None

    def build_monthly_workbook(
        self, clean, year, month, cfg, planned_activities, compiled_by
    ):
        self.build_args = (clean, year, month, cfg, planned_activities, compiled_by)
        return BytesIO(b"workbook")

    def suggested_filename(self, year, month):
        return f"report-{year}-{month}.xlsx"


def test_generate_monthly_report_delegates_export_and_returns_download_metadata():
    exporter = FakeExporter()
    service = MonthlyReportService(exporter)
    clean = pd.DataFrame({"date": [pd.Timestamp("2026-10-01")]})
    config = {"groups": []}

    result = service.generate(clean, 2026, 10, config, "Activities", "Compiled")

    assert exporter.build_args == (clean, 2026, 10, config, "Activities", "Compiled")
    assert result.workbook.getvalue() == b"workbook"
    assert result.filename == "report-2026-10.xlsx"


def test_exporter_failure_is_logged_and_translated(caplog):
    class BrokenExporter(FakeExporter):
        def build_monthly_workbook(self, *args):
            raise RuntimeError("filesystem secret-token")

    service = MonthlyReportService(BrokenExporter())

    with caplog.at_level("ERROR", logger="nrb"):
        with pytest.raises(ApplicationError) as raised:
            service.generate(pd.DataFrame(), 2026, 10, {}, "", "")

    assert "secret-token" not in str(raised.value)
    assert "secret-token" in caplog.text
