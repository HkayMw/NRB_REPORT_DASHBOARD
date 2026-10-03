import pytest

from nrb.application.services.report_footer import ReportFooterService
from nrb.application.services.authorization import AuthorizationService
from nrb.config import DEFAULT_COMPILED_BY, DEFAULT_PLANNED_ACTIVITIES


class FakeSettingsRepository:
    def __init__(self):
        self.settings = {}
        self.writes = []
        self.principal = {"id": "admin-id", "role": "admin", "active": 1}

    def get_user_by_id(self, user_id):
        return self.principal if user_id == self.principal["id"] else None

    def get_setting(self, key, default=None):
        return self.settings.get(key, default)

    def set_setting(self, key, value):
        self.settings[key] = value
        self.writes.append((key, value))


def test_footer_uses_existing_defaults_and_setting_keys():
    repository = FakeSettingsRepository()
    service = ReportFooterService(repository, AuthorizationService(repository))

    footer = service.get_footer()

    assert footer.planned_activities == DEFAULT_PLANNED_ACTIVITIES
    assert footer.compiled_by == DEFAULT_COMPILED_BY


def test_admin_saves_both_footer_settings():
    repository = FakeSettingsRepository()
    service = ReportFooterService(repository, AuthorizationService(repository))

    saved = service.save_footer(
        "Activities", "Compiled by", {"id": "admin-id", "role": "admin"}
    )

    assert saved.planned_activities == "Activities"
    assert saved.compiled_by == "Compiled by"
    assert repository.writes == [
        ("planned_activities", "Activities"),
        ("compiled_by", "Compiled by"),
    ]


def test_non_admin_cannot_save_footer_settings():
    repository = FakeSettingsRepository()
    repository.principal = {"id": "viewer-id", "role": "viewer", "active": 1}
    service = ReportFooterService(repository, AuthorizationService(repository))

    with pytest.raises(PermissionError):
        service.save_footer(
            "Activities", "Compiled by", {"id": "viewer-id", "role": "admin"}
        )

    assert repository.writes == []
