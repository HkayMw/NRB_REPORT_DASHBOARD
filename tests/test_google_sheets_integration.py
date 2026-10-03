from types import SimpleNamespace

import pytest

from nrb.infrastructure.data_sources import google_sheets


def test_fetch_responses_requests_csv_and_drops_empty_rows_and_columns(monkeypatch):
    calls = []
    response = SimpleNamespace(
        headers={"content-type": "text/csv"},
        content=b"Name,Count,Empty\nAlice,2,\n,,\nBob,3,\n",
        raise_for_status=lambda: None,
    )

    def fake_get(url, timeout):
        calls.append((url, timeout))
        return response

    monkeypatch.setattr(google_sheets.requests, "get", fake_get)
    google_sheets.fetch_responses.clear()

    result = google_sheets.fetch_responses(
        "https://docs.google.com/spreadsheets/d/sheet-id/edit#gid=42"
    )

    assert calls == [
        (
            "https://docs.google.com/spreadsheets/d/sheet-id/export?format=csv&gid=42",
            30,
        )
    ]
    assert result.to_dict(orient="records") == [
        {"Name": "Alice", "Count": 2},
        {"Name": "Bob", "Count": 3},
    ]
    google_sheets.fetch_responses.clear()


def test_fetch_responses_rejects_html_response(monkeypatch):
    response = SimpleNamespace(
        headers={"content-type": "text/html"},
        content=b"<html>sign in</html>",
        raise_for_status=lambda: None,
    )
    monkeypatch.setattr(google_sheets.requests, "get", lambda *args, **kwargs: response)
    google_sheets.fetch_responses.clear()

    with pytest.raises(RuntimeError, match="instead of CSV"):
        google_sheets.fetch_responses(
            "https://docs.google.com/spreadsheets/d/sheet-id/edit"
        )

    google_sheets.fetch_responses.clear()
