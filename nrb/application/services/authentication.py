"""Authentication and first-administrator use cases."""

from dataclasses import dataclass
from typing import Callable, Protocol

from nrb.application.errors import call_infrastructure


class AuthenticationRepository(Protocol):
    def count_users(self) -> int: ...

    def get_user(self, username: str) -> dict | None: ...

    def create_user(
        self,
        username: str,
        pw_hash: str,
        role: str = "viewer",
        full_name: str = "",
    ) -> None: ...


@dataclass
class AuthenticationService:
    repository: AuthenticationRepository
    hash_password: Callable[[str], str]
    verify_password: Callable[[str, str], bool]

    def count_users(self) -> int:
        return call_infrastructure(
            "Count user accounts",
            "Could not check user accounts. Please try again later.",
            self.repository.count_users,
        )

    def authenticate(self, username: str, password: str) -> dict | None:
        user = call_infrastructure(
            "Look up login account",
            "Login is temporarily unavailable. Please try again later.",
            self.repository.get_user,
            username.strip(),
        )
        if not user or not self.verify_password(password, user["pw_hash"]):
            return None
        return {
            "id": user["id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "role": user["role"],
        }

    def create_first_admin(
        self,
        username: str,
        full_name: str,
        password: str,
        confirmation: str,
    ) -> None:
        if self.count_users() != 0:
            raise PermissionError("The first administrator has already been created.")
        username = username.strip()
        if not username or not password:
            raise ValueError("Username and password are required.")
        if len(password) < 8:
            raise ValueError("Use a password of at least 8 characters.")
        if password != confirmation:
            raise ValueError("Passwords do not match.")
        call_infrastructure(
            "Create first administrator account",
            "Could not create the administrator account. Please try again later.",
            self.repository.create_user,
            username,
            self.hash_password(password),
            role="admin",
            full_name=full_name.strip(),
        )
