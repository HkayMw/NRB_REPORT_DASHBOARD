"""Use cases for administrator-managed user accounts."""

from dataclasses import dataclass
from typing import Callable, Protocol

from nrb.application.errors import call_infrastructure
from nrb.application.services.authorization import AuthorizationService
from nrb.domain import roles


class UserRepository(Protocol):
    def list_users(self) -> list[dict]: ...

    def get_user(self, username: str) -> dict | None: ...

    def get_user_by_id(self, user_id: str) -> dict | None: ...

    def create_user(
        self,
        username: str,
        pw_hash: str,
        role: str = "viewer",
        full_name: str = "",
    ) -> None: ...

    def update_user(self, user_id: str, **fields) -> None: ...


@dataclass
class UserManagementService:
    repository: UserRepository
    hash_password: Callable[[str], str]
    authorization: AuthorizationService

    def list_users(self) -> list[dict]:
        return call_infrastructure(
            "Load user accounts",
            "Could not load user accounts. Please try again later.",
            self.repository.list_users,
        )

    def create_user(
        self,
        username: str,
        full_name: str,
        password: str,
        role: str,
        actor: dict | None,
    ) -> None:
        self._require_admin(actor)
        username = username.strip()
        if not username or len(password) < 8:
            raise ValueError(
                "Username required; password must be at least 8 characters."
            )
        if role not in roles.ROLES:
            raise ValueError("Role must be viewer, clerk or admin.")
        if call_infrastructure(
            "Check username availability",
            "Could not check username availability. Please try again later.",
            self.repository.get_user,
            username,
        ):
            raise ValueError("Username already exists.")
        call_infrastructure(
            "Create user account",
            "Could not create the user account. Please try again later.",
            self.repository.create_user,
            username,
            self.hash_password(password),
            role,
            full_name.strip(),
        )

    def update_user(
        self,
        user_id: str,
        role: str,
        active: bool,
        new_password: str,
        actor: dict | None,
    ) -> None:
        principal = self.authorization.require_admin(actor)
        if role not in roles.ROLES:
            raise ValueError("Role must be viewer, clerk or admin.")
        if principal["id"] == user_id and (role != roles.ADMIN or not active):
            raise ValueError("You cannot demote or deactivate your own account.")

        fields = {"role": role, "active": int(active)}
        if new_password:
            if len(new_password) < 8:
                raise ValueError("Password must be at least 8 characters.")
            fields["pw_hash"] = self.hash_password(new_password)
        call_infrastructure(
            "Update user account",
            "Could not update the user account. Please try again later.",
            self.repository.update_user,
            user_id,
            **fields,
        )

    def _require_admin(self, actor: dict | None) -> None:
        self.authorization.require_admin(actor)
