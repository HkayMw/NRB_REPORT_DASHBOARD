"""Authorization checks against the current persisted user account."""

from dataclasses import dataclass
from typing import Protocol


class PrincipalRepository(Protocol):
    def get_user_by_id(self, user_id: str) -> dict | None: ...


@dataclass
class AuthorizationService:
    repository: PrincipalRepository

    def require_admin(self, actor: dict | None) -> dict:
        if not actor or not actor.get("id"):
            raise PermissionError("Administrator access is required for this action.")

        current = self.repository.get_user_by_id(actor["id"])
        if not current or not current.get("active"):
            raise PermissionError("Your account is inactive or no longer exists.")
        if current.get("role") != "admin":
            raise PermissionError("Administrator access is required for this action.")
        return current
