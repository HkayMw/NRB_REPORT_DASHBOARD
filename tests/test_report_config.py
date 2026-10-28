import pandas as pd

from nrb.domain import report_config
from nrb.application.services.authorization import AuthorizationService
from nrb.application.services.report_configuration import ReportConfigService
from nrb.infrastructure.repositories import report_config as repository


def test_default_report_config_is_valid():
    assert report_config.validate(report_config.DEFAULT_REPORT_CONFIG) == []


def test_compute_block_sums_rows_and_ignores_missing_values():
    frame = pd.DataFrame({"A": [2, None], "B": [3, 4]})
    block = {
        "rows": [
            {"label": "Combined", "fields": ["A", "B"]},
            {"label": "A only", "fields": ["A"]},
        ]
    }

    assert report_config.compute_block(frame, block) == {
        "rows": [("Combined", 9), ("A only", 2)],
        "total": 11,
    }


def test_invalid_layout_is_rejected_before_persistence(monkeypatch):
    class FakeRepository:
        def __init__(self):
            self.writes = []
            self.principal = {"id": "admin-id", "role": "admin", "active": 1}

        def get_user_by_id(self, user_id):
            return self.principal if user_id == self.principal["id"] else None

        def get_report_config(self):
            return report_config.DEFAULT_REPORT_CONFIG

        def save_report_config(self, cfg):
            self.writes.append(cfg)

    fake_repository = FakeRepository()
    service = ReportConfigService(
        fake_repository, AuthorizationService(fake_repository)
    )

    try:
        service.save_report_config({"groups": []}, {"id": "admin-id", "role": "admin"})
    except ValueError as error:
        assert "non-empty 'groups' list" in str(error)
    else:
        raise AssertionError("Expected invalid report layout to be rejected")

    assert fake_repository.writes == []


def test_save_valid_layout_passes_to_repository():
    class FakeRepository:
        def __init__(self):
            self.writes = []
            self.principal = {"id": "admin-id", "role": "admin", "active": 1}

        def get_user_by_id(self, user_id):
            return self.principal if user_id == self.principal["id"] else None

        def get_report_config(self):
            return report_config.DEFAULT_REPORT_CONFIG

        def save_report_config(self, cfg):
            self.writes.append(cfg)

    fake_repository = FakeRepository()
    service = ReportConfigService(
        fake_repository, AuthorizationService(fake_repository)
    )
    layout = {
        "groups": [
            {
                "title": "Group",
                "blocks": [
                    {
                        "title": "Block",
                        "rows": [
                            {"label": "Rows", "fields": ["New applicants captured"]}
                        ],
                    }
                ],
            }
        ]
    }

    service.save_report_config(layout, {"id": "admin-id", "role": "admin"})

    assert fake_repository.writes == [layout]


def test_non_admin_cannot_save_report_config():
    class FakeRepository:
        def __init__(self):
            self.writes = []
            self.principal = {"id": "viewer-id", "role": "viewer", "active": 1}

        def get_user_by_id(self, user_id):
            return self.principal if user_id == self.principal["id"] else None

        def get_report_config(self):
            return report_config.DEFAULT_REPORT_CONFIG

        def save_report_config(self, cfg):
            self.writes.append(cfg)

    fake_repository = FakeRepository()
    service = ReportConfigService(
        fake_repository, AuthorizationService(fake_repository)
    )

    try:
        service.save_report_config(
            report_config.DEFAULT_REPORT_CONFIG,
            {"id": "viewer-id", "role": "admin"},
        )
    except PermissionError as error:
        assert "Administrator access" in str(error)
    else:
        raise AssertionError("Expected report-layout mutation to require admin")

    assert fake_repository.writes == []


def test_mongo_repository_uses_setting_key_and_domain_default(monkeypatch):
    writes = []
    monkeypatch.setattr(
        repository.db, "get_setting", lambda key, default: (key, default)
    )
    monkeypatch.setattr(repository.db, "set_setting", lambda *args: writes.append(args))
    layout = {
        "groups": [
            {
                "title": "Group",
                "blocks": [
                    {
                        "title": "Block",
                        "rows": [
                            {"label": "Rows", "fields": ["New applicants captured"]}
                        ],
                    }
                ],
            }
        ]
    }
    adapter = repository.MongoReportConfigRepository()

    assert adapter.get_report_config() == (
        "report_config",
        report_config.DEFAULT_REPORT_CONFIG,
    )
    adapter.save_report_config(layout)

    assert writes == [("report_config", layout)]
