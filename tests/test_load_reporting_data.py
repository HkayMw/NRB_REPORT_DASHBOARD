import pandas as pd
import pytest

from nrb.application.errors import ApplicationError
from nrb.application.services.load_reporting_data import ReportingDataService


class FakeRepository:
    def __init__(self):
        self.calls = []

    def get_setting(self, key, default=None):
        self.calls.append(("setting", key, default))
        return "sheet-url"

    def list_staff(self, active_only=False):
        self.calls.append(("roster", active_only))
        return [{"form_name": "S.Chirwa"}]


class FakeSource:
    def __init__(self, raw):
        self.raw = raw
        self.urls = []
        self.cache_cleared = False

    def fetch_responses(self, url):
        self.urls.append(url)
        return self.raw

    def clear_cache(self):
        self.cache_cleared = True


def test_execute_fetches_sheet_and_roster_then_cleans_responses():
    raw = pd.DataFrame(
        {
            "Timestamp": ["2026-09-01 09:00:00"],
            "Name": ["S.Chirwa"],
            "Date": ["2026-09-01"],
            "Assigned Section": ["ID CAPTURING"],
        }
    )
    repository = FakeRepository()
    source = FakeSource(raw)
    service = ReportingDataService(repository, source)

    result = service.load()

    assert source.urls == ["sheet-url"]
    assert repository.calls[1:] == [("roster", False)]
    assert result.raw is raw
    assert len(result.cleaned.clean) == 1
    assert result.cleaned.unknown_names.empty


def test_service_clears_source_cache_through_adapter():
    source = FakeSource(pd.DataFrame())
    service = ReportingDataService(FakeRepository(), source)

    service.clear_cache()

    assert source.cache_cleared


def test_source_failure_returns_safe_error_and_logs_technical_cause(caplog):
    class BrokenSource(FakeSource):
        def fetch_responses(self, url):
            raise RuntimeError("connection failed for mongodb://secret-token")

    service = ReportingDataService(FakeRepository(), BrokenSource(pd.DataFrame()))

    with caplog.at_level("ERROR", logger="nrb"):
        with pytest.raises(ApplicationError) as raised:
            service.load()

    assert "secret-token" not in str(raised.value)
    assert "Check the configured sheet" in str(raised.value)
    assert "secret-token" in caplog.text
