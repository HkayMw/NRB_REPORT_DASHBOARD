import pandas as pd
import pytest

from nrb.application.errors import ApplicationError
from nrb.application.services.admin_settings import AdminSettingsService
from nrb.application.services.authorization import AuthorizationService
from nrb.config import DEFAULT_SHEET_URL


class FakeAdminSettingsRepository:
    def __init__(self):
        self.settings = {}
        self.staff = [
            {
                "id": "1",
                "form_name": "Alice",
                "full_name": "Alice Example",
                "active": 1,
            },
        ]
        self.writes = []
        self.principals = {
            "admin-id": {
                "id": "admin-id",
                "role": "admin",
                "active": 1,
            }
        }

    def get_user_by_id(self, user_id):
        return self.principals.get(user_id)

    def get_setting(self, key, default=None):
        return self.settings.get(key, default)

    def set_setting(self, key, value):
        self.settings[key] = value
        self.writes.append(("setting", key, value))

    def list_staff(self):
        return list(self.staff)

    def upsert_staff(self, form_name, full_name, active, staff_id=None):
        self.writes.append(("upsert", form_name, full_name, active, staff_id))

    def delete_staff(self, staff_id):
        self.writes.append(("delete", staff_id))


def make_service(repository, fetched=None, cleared=None):
    fetched = fetched if fetched is not None else pd.DataFrame({"Name": ["Alice"]})
    cleared = cleared if cleared is not None else []
    return AdminSettingsService(
        repository,
        fetch_responses=lambda url: fetched,
        clear_sheet_cache=lambda: cleared.append(True),
        authorization=AuthorizationService(repository),
    )


def test_sheet_url_uses_default_and_saves_only_after_successful_fetch():
    repository = FakeAdminSettingsRepository()
    service = make_service(repository)
    admin = {"id": "admin-id", "role": "admin"}

    assert service.get_sheet_url() == DEFAULT_SHEET_URL
    responses = service.test_and_save_sheet_url("valid-url", admin)

    assert len(responses) == 1
    assert repository.settings["sheet_url"] == "valid-url"


@pytest.mark.parametrize(
    "public_viewing,is_logged_in,expected",
    [(True, False, True), (False, True, True), (False, False, False)],
)
def test_dashboard_access_policy(public_viewing, is_logged_in, expected):
    repository = FakeAdminSettingsRepository()
    repository.settings["public_viewing"] = public_viewing
    service = make_service(repository)

    assert service.can_view_dashboard(is_logged_in) is expected


def test_failed_sheet_fetch_does_not_save_url_or_expose_technical_error(caplog):
    repository = FakeAdminSettingsRepository()
    service = AdminSettingsService(
        repository,
        fetch_responses=lambda _: (_ for _ in ()).throw(
            RuntimeError("request failed with secret-token")
        ),
        clear_sheet_cache=lambda: None,
        authorization=AuthorizationService(repository),
    )

    with caplog.at_level("ERROR", logger="nrb"):
        with pytest.raises(ApplicationError) as raised:
            service.test_and_save_sheet_url(
                "bad-url", {"id": "admin-id", "role": "admin"}
            )

    assert "sheet_url" not in repository.settings
    assert "secret-token" not in str(raised.value)
    assert "secret-token" in caplog.text


def test_roster_rejects_duplicates_before_writing():
    repository = FakeAdminSettingsRepository()
    service = make_service(repository)

    with pytest.raises(ValueError, match="Duplicate form names"):
        service.save_roster(
            [
                {"Form name": "Bob"},
                {"Form name": " Bob "},
            ],
            {"id": "admin-id", "role": "admin"},
        )

    assert repository.writes == []


def test_roster_mutation_rejects_viewer():
    repository = FakeAdminSettingsRepository()
    service = make_service(repository)

    with pytest.raises(PermissionError):
        repository.principals["viewer-id"] = {
            "id": "viewer-id",
            "role": "viewer",
            "active": 1,
        }
        service.save_roster([], {"id": "viewer-id", "role": "viewer"})

    assert repository.writes == []


def test_stale_admin_session_is_rejected_after_demotion():
    repository = FakeAdminSettingsRepository()
    service = make_service(repository)
    repository.principals["admin-id"]["role"] = "viewer"

    with pytest.raises(PermissionError):
        service.set_public_viewing(False, {"id": "admin-id", "role": "admin"})

    assert repository.writes == []


def test_clerk_can_save_roster_but_not_change_data_source():
    repository = FakeAdminSettingsRepository()
    repository.principals["clerk-id"] = {"id": "clerk-id", "role": "clerk", "active": 1}
    service = make_service(repository)
    clerk = {"id": "clerk-id", "role": "clerk"}

    service.save_roster(
        [{"Form name": "Alice", "Full name": "A", "Active": True}], clerk
    )
    with pytest.raises(PermissionError):
        service.set_public_viewing(False, clerk)
    with pytest.raises(PermissionError):
        service.test_and_save_sheet_url("https://example.com", clerk)

    assert repository.writes == [("upsert", "Alice", "A", True, "1")]
