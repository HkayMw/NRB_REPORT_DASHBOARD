"""Authorization checks against the current persisted user account."""

from dataclasses import dataclass
from typing import Protocol

from nrb.domain import roles


class PrincipalRepository(Protocol):
    def get_user_by_id(self, user_id: str) -> dict | None: ...


@dataclass
class AuthorizationService:
    repository: PrincipalRepository

    def require_admin(self, actor: dict | None) -> dict:
        current = self._current(
            actor, "Administrator access is required for this action."
        )
        if current.get("role") != roles.ADMIN:
            raise PermissionError("Administrator access is required for this action.")
        return current

    def require(self, actor: dict | None, permission: str) -> dict:
        current = self._current(actor, "You do not have permission for this action.")
        if not roles.has_permission(current.get("role"), permission):
            raise PermissionError("You do not have permission for this action.")
        return current

    def _current(self, actor: dict | None, message: str) -> dict:
        if not actor or not actor.get("id"):
            raise PermissionError(message)

        current = self.repository.get_user_by_id(actor["id"])
        if not current or not current.get("active"):
            raise PermissionError("Your account is inactive or no longer exists.")
        return current
