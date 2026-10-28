import pytest

from nrb.application.services.authorization import AuthorizationService


class FakePrincipalRepository:
    def __init__(self, principal):
        self.principal = principal
        self.lookups = []

    def get_user_by_id(self, user_id):
        self.lookups.append(user_id)
        if self.principal and self.principal["id"] == user_id:
            return self.principal
        return None


def test_admin_check_uses_current_persisted_role_not_session_role():
    repository = FakePrincipalRepository(
        {
            "id": "user-1",
            "role": "viewer",
            "active": 1,
        }
    )
    authorization = AuthorizationService(repository)

    with pytest.raises(PermissionError):
        authorization.require_admin(
            {
                "id": "user-1",
                "role": "admin",
            }
        )

    assert repository.lookups == ["user-1"]


@pytest.mark.parametrize(
    "principal", [None, {"id": "user-1", "role": "admin", "active": 0}]
)
def test_admin_check_rejects_missing_or_inactive_current_account(principal):
    authorization = AuthorizationService(FakePrincipalRepository(principal))

    with pytest.raises(PermissionError):
        authorization.require_admin({"id": "user-1", "role": "admin"})


def test_admin_check_returns_current_principal():
    current = {"id": "user-1", "role": "admin", "active": 1}
    authorization = AuthorizationService(FakePrincipalRepository(current))

    assert authorization.require_admin({"id": "user-1", "role": "viewer"}) is current


@pytest.mark.parametrize(
    "role,permission,allowed",
    [
        ("admin", "edit_schedule", True),
        ("clerk", "create_schedule", True),
        ("clerk", "manage_roster", True),
        ("clerk", "edit_schedule", False),
        ("viewer", "create_schedule", False),
    ],
)
def test_require_permission_uses_persisted_role(role, permission, allowed):
    current = {"id": "user-1", "role": role, "active": 1}
    authorization = AuthorizationService(FakePrincipalRepository(current))

    if allowed:
        assert authorization.require({"id": "user-1"}, permission) is current
    else:
        with pytest.raises(PermissionError):
            authorization.require({"id": "user-1", "role": "admin"}, permission)


def test_clerk_is_not_admin():
    authorization = AuthorizationService(
        FakePrincipalRepository({"id": "user-1", "role": "clerk", "active": 1})
    )

    with pytest.raises(PermissionError):
        authorization.require_admin({"id": "user-1"})
