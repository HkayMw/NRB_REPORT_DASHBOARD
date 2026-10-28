"""Authorized database diagnostics and recoverable backup operations."""

from dataclasses import dataclass
import logging
from typing import Protocol

from nrb.application.errors import call_infrastructure
from nrb.application.services.authorization import AuthorizationService

logger = logging.getLogger("nrb")


COLLECTION_FIELDS = {
    "users": {"username", "pw_hash", "role", "active", "full_name"},
    "settings": {"_id", "value"},
    "staff": {"form_name", "full_name", "active"},
    "teams": {
        "name",
        "reports_as_section",
        "min_size",
        "max_size",
        "pinned_members",
        "active",
        "sort_order",
    },
    "schedules": {"week_start", "week_end", "created_by", "created_at", "assignments"},
}


class BackupRepository(Protocol):
    def ping(self) -> tuple[bool, str]: ...

    def export_all(self) -> dict: ...

    def import_all(self, dump: dict) -> None: ...


class BackupValidationError(ValueError):
    """Backup payload is not a complete supported export."""


class BackupRestoreError(RuntimeError):
    """Restore failed, with recovery status in the exception message."""


@dataclass
class DatabaseBackupService:
    repository: BackupRepository
    authorization: AuthorizationService

    def database_status(self, actor: dict | None) -> tuple[bool, str]:
        self._require_admin(actor)
        try:
            return self.repository.ping()
        except Exception:
            logger.exception("Check database status failed")
            return False, "Connection check failed. See application logs."

    def create_backup(self, actor: dict | None) -> dict:
        self._require_admin(actor)
        return call_infrastructure(
            "Export database backup",
            "Backup could not be created. Please check application logs.",
            self.repository.export_all,
        )

    def restore_backup(self, payload: dict, actor: dict | None) -> None:
        self._require_admin(actor)
        self.validate_backup(payload)

        previous = call_infrastructure(
            "Create pre-restore database snapshot",
            "A recovery snapshot could not be created. Restore was not started.",
            self.repository.export_all,
        )
        try:
            self.repository.import_all(payload)
        except Exception as restore_error:
            logger.exception("Restore database backup failed")
            try:
                self.repository.import_all(previous)
            except Exception as rollback_error:
                logger.exception("Recover pre-restore database snapshot failed")
                raise BackupRestoreError(
                    "Restore failed and automatic recovery also failed. "
                    "Do not retry; inspect the database before further changes."
                ) from rollback_error
            raise BackupRestoreError(
                "Restore failed; the pre-restore database snapshot was restored."
            ) from restore_error

    @staticmethod
    def validate_backup(payload: dict) -> None:
        if not isinstance(payload, dict):
            raise BackupValidationError("Backup must be a JSON object.")
        if set(payload) != set(COLLECTION_FIELDS):
            raise BackupValidationError(
                "Backup must contain exactly these collections: "
                + ", ".join(COLLECTION_FIELDS)
                + "."
            )
        for collection, required_fields in COLLECTION_FIELDS.items():
            documents = payload[collection]
            if not isinstance(documents, list):
                raise BackupValidationError(
                    f"Backup collection '{collection}' must be a list."
                )
            for index, document in enumerate(documents):
                if not isinstance(document, dict):
                    raise BackupValidationError(
                        f"Backup record {index + 1} in '{collection}' must be an object."
                    )
                missing = required_fields - document.keys()
                if missing:
                    raise BackupValidationError(
                        f"Backup record {index + 1} in '{collection}' is missing: "
                        + ", ".join(sorted(missing))
                        + "."
                    )
                DatabaseBackupService._validate_document(collection, document, index)
                if collection == "schedules":
                    DatabaseBackupService._validate_assignments(document, index)

    @staticmethod
    def _validate_document(collection: str, document: dict, index: int) -> None:
        record = index + 1
        strings_by_collection = {
            "users": ("username", "pw_hash", "role", "full_name"),
            "staff": ("form_name", "full_name"),
            "teams": ("name", "reports_as_section"),
            "schedules": ("week_start", "week_end", "created_by", "created_at"),
        }
        for field in strings_by_collection.get(collection, ()):
            if not isinstance(document[field], str):
                raise BackupValidationError(
                    f"Field '{field}' in '{collection}' record {record} must be text."
                )

        if collection == "users":
            if document["role"] not in {"viewer", "admin"}:
                raise BackupValidationError(
                    f"Role in user record {record} must be viewer or admin."
                )
            DatabaseBackupService._validate_active(document["active"], "users", record)
        elif collection == "settings":
            if not isinstance(document["_id"], str) or not document["_id"]:
                raise BackupValidationError(
                    f"Setting record {record} must have a non-empty string key."
                )
        elif collection == "staff":
            DatabaseBackupService._validate_active(document["active"], "staff", record)
        elif collection == "teams":
            minimum, maximum = document["min_size"], document["max_size"]
            if (
                not isinstance(minimum, int)
                or not isinstance(maximum, int)
                or minimum < 0
                or maximum < minimum
            ):
                raise BackupValidationError(
                    f"Team record {record} has invalid minimum or maximum size."
                )
            if not isinstance(document["pinned_members"], list) or not all(
                isinstance(name, str) for name in document["pinned_members"]
            ):
                raise BackupValidationError(
                    f"Pinned members in team record {record} must be a list of names."
                )
            if not isinstance(document["sort_order"], int):
                raise BackupValidationError(
                    f"Sort order in team record {record} must be an integer."
                )
            DatabaseBackupService._validate_active(document["active"], "teams", record)
        elif collection == "schedules":
            if not isinstance(document["assignments"], list):
                raise BackupValidationError(
                    f"Assignments in schedule record {record} must be a list."
                )

    @staticmethod
    def _validate_active(value, collection: str, record: int) -> None:
        if not isinstance(value, (bool, int)) or value not in (0, 1):
            raise BackupValidationError(
                f"Active flag in {collection} record {record} must be 0 or 1."
            )

    @staticmethod
    def _validate_assignments(schedule: dict, index: int) -> None:
        assignments = schedule["assignments"]
        if not isinstance(assignments, list):
            raise BackupValidationError(
                f"Assignments in schedule record {index + 1} must be a list."
            )
        for assignment_index, assignment in enumerate(assignments):
            required = {"team_id", "staff_name", "position"}
            if not isinstance(assignment, dict) or not required <= assignment.keys():
                raise BackupValidationError(
                    f"Assignment {assignment_index + 1} in schedule record "
                    f"{index + 1} is invalid."
                )
            if (
                not isinstance(assignment["team_id"], str)
                or not isinstance(assignment["staff_name"], str)
                or not isinstance(assignment["position"], int)
            ):
                raise BackupValidationError(
                    f"Assignment {assignment_index + 1} in schedule record "
                    f"{index + 1} has invalid field types."
                )

    def _require_admin(self, actor: dict | None) -> None:
        self.authorization.require_admin(actor)
