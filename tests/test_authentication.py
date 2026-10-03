import pytest

from nrb.application.services.authentication import AuthenticationService
from nrb.domain.passwords import hash_password, verify_password


class FakeAuthenticationRepository:
    def __init__(self, users=None):
        self.users = list(users or [])
        self.created = []

    def count_users(self):
        return len(self.users)

    def get_user(self, username):
        return next(
            (
                user
                for user in self.users
                if user["username"] == username and user.get("active", 1)
            ),
            None,
        )

    def create_user(self, username, pw_hash, role="viewer", full_name=""):
        user = {
            "id": str(len(self.users) + 1),
            "username": username,
            "pw_hash": pw_hash,
            "role": role,
            "full_name": full_name,
            "active": 1,
        }
        self.users.append(user)
        self.created.append(user)


def service_for(repository):
    return AuthenticationService(repository, hash_password, verify_password)


def test_password_hashes_are_salted_and_verify_correct_password():
    first = hash_password("long-password")
    second = hash_password("long-password")

    assert first != second
    assert verify_password("long-password", first)
    assert not verify_password("incorrect-password", first)


def test_authenticate_returns_safe_user_identity():
    repository = FakeAuthenticationRepository()
    repository.create_user(
        "jsmith", hash_password("long-password"), "viewer", "Jane Smith"
    )
    service = service_for(repository)

    result = service.authenticate(" jsmith ", "long-password")

    assert result == {
        "id": "1",
        "username": "jsmith",
        "full_name": "Jane Smith",
        "role": "viewer",
    }
    assert "pw_hash" not in result
    assert service.authenticate("jsmith", "wrong-password") is None
    assert service.authenticate("missing", "long-password") is None


def test_first_admin_is_created_only_for_empty_database():
    repository = FakeAuthenticationRepository()
    service = service_for(repository)

    service.create_first_admin(
        " admin ", "Admin User", "long-password", "long-password"
    )

    assert len(repository.created) == 1
    assert repository.created[0]["username"] == "admin"
    assert repository.created[0]["role"] == "admin"
    assert verify_password("long-password", repository.created[0]["pw_hash"])
    with pytest.raises(PermissionError, match="already been created"):
        service.create_first_admin("other", "Other", "long-password", "long-password")


@pytest.mark.parametrize(
    "username,password,confirmation,message",
    [
        ("", "long-password", "long-password", "required"),
        ("admin", "short", "short", "at least 8"),
        ("admin", "long-password", "different", "do not match"),
    ],
)
def test_first_admin_validates_inputs(username, password, confirmation, message):
    repository = FakeAuthenticationRepository()
    service = service_for(repository)

    with pytest.raises(ValueError, match=message):
        service.create_first_admin(username, "Admin", password, confirmation)

    assert repository.created == []
