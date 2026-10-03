import pytest

from nrb.application.services.authorization import AuthorizationService
from nrb.application.services.user_management import UserManagementService


class FakeUserRepository:
    def __init__(self):
        self.users = []
        self.writes = []
        self.principals = {
            "admin-id": {"id": "admin-id", "role": "admin", "active": 1},
            "viewer-id": {"id": "viewer-id", "role": "viewer", "active": 1},
        }

    def get_user_by_id(self, user_id):
        return self.principals.get(user_id)

    def list_users(self):
        return list(self.users)

    def get_user(self, username):
        return next((user for user in self.users if user["username"] == username), None)

    def create_user(self, username, pw_hash, role="viewer", full_name=""):
        self.writes.append(("create", username, pw_hash, role, full_name))

    def update_user(self, user_id, **fields):
        self.writes.append(("update", user_id, fields))


def make_service(repository):
    return UserManagementService(
        repository,
        lambda password: f"hashed:{password}",
        AuthorizationService(repository),
    )


def test_create_user_validates_and_hashes_password():
    repository = FakeUserRepository()
    service = make_service(repository)

    service.create_user(
        "  jsmith ",
        "Jane Smith",
        "long-password",
        "viewer",
        {"id": "admin-id", "role": "admin"},
    )

    assert repository.writes == [
        ("create", "jsmith", "hashed:long-password", "viewer", "Jane Smith")
    ]


def test_create_user_rejects_duplicates_and_non_admin_without_writes():
    repository = FakeUserRepository()
    repository.users.append({"username": "jsmith"})
    service = make_service(repository)

    with pytest.raises(ValueError, match="already exists"):
        service.create_user(
            "jsmith",
            "Jane",
            "long-password",
            "viewer",
            {"id": "admin-id", "role": "admin"},
        )
    with pytest.raises(PermissionError):
        service.create_user(
            "new",
            "New User",
            "long-password",
            "viewer",
            {"id": "viewer-id", "role": "admin"},
        )

    assert repository.writes == []


@pytest.mark.parametrize("role,active", [("viewer", True), ("admin", False)])
def test_admin_cannot_demote_or_deactivate_self(role, active):
    repository = FakeUserRepository()
    service = make_service(repository)

    with pytest.raises(ValueError, match="cannot demote or deactivate"):
        service.update_user(
            "admin-id",
            role,
            active,
            "",
            {
                "id": "admin-id",
                "role": "admin",
            },
        )

    assert repository.writes == []


def test_admin_can_update_other_user_and_optional_password():
    repository = FakeUserRepository()
    service = make_service(repository)

    service.update_user(
        "user-id",
        "admin",
        True,
        "new-password",
        {
            "id": "admin-id",
            "role": "admin",
        },
    )

    assert repository.writes == [
        (
            "update",
            "user-id",
            {
                "role": "admin",
                "active": 1,
                "pw_hash": "hashed:new-password",
            },
        )
    ]
