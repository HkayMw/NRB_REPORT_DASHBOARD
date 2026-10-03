import pytest

from nrb.application.errors import ApplicationError
from nrb.application.services.database_backup import (
    BackupRestoreError,
    BackupValidationError,
    DatabaseBackupService,
)
from nrb.application.services.authorization import AuthorizationService


def valid_backup():
    return {
        "users": [],
        "settings": [],
        "staff": [],
        "teams": [],
        "schedules": [
            {
                "week_start": "2026-10-05",
                "week_end": "2026-10-09",
                "created_by": "admin",
                "created_at": "2026-10-03T12:00:00+00:00",
                "assignments": [
                    {
                        "team_id": "team-id",
                        "staff_name": "Alice",
                        "position": 0,
                    }
                ],
            }
        ],
    }


class FakeBackupRepository:
    def __init__(self):
        self.current = {"version": "before"}
        self.imports = []
        self.fail_next_import = False
        self.fail_rollback = False
        self.fail_export = False
        self.principals = {
            "admin-id": {"id": "admin-id", "role": "admin", "active": 1},
            "viewer-id": {"id": "viewer-id", "role": "viewer", "active": 1},
        }

    def get_user_by_id(self, user_id):
        return self.principals.get(user_id)

    def ping(self):
        return True, "fake database"

    def export_all(self):
        if self.fail_export:
            raise RuntimeError("mongo URI contains secret-token")
        return dict(self.current)

    def import_all(self, dump):
        self.imports.append(dump)
        if self.fail_next_import:
            self.fail_next_import = False
            raise RuntimeError("restore failed")
        if self.fail_rollback:
            raise RuntimeError("restore and recovery both failed")
        self.current = dict(dump)


def test_invalid_backup_is_rejected_before_snapshot_or_import():
    repository = FakeBackupRepository()
    service = DatabaseBackupService(repository, AuthorizationService(repository))

    with pytest.raises(BackupValidationError, match="exactly these collections"):
        service.restore_backup({"users": []}, {"id": "admin-id", "role": "admin"})

    assert repository.imports == []


def test_invalid_schedule_assignment_is_rejected_before_import():
    repository = FakeBackupRepository()
    service = DatabaseBackupService(repository, AuthorizationService(repository))
    payload = valid_backup()
    payload["schedules"][0]["assignments"][0]["position"] = "first"

    with pytest.raises(BackupValidationError, match="invalid field types"):
        service.restore_backup(payload, {"id": "admin-id", "role": "admin"})

    assert repository.imports == []


def test_restore_failure_imports_pre_restore_snapshot():
    repository = FakeBackupRepository()
    repository.fail_next_import = True
    service = DatabaseBackupService(repository, AuthorizationService(repository))

    with pytest.raises(BackupRestoreError, match="snapshot was restored"):
        service.restore_backup(valid_backup(), {"id": "admin-id", "role": "admin"})

    assert repository.imports == [valid_backup(), {"version": "before"}]
    assert repository.current == {"version": "before"}


def test_failed_rollback_reports_recovery_failure():
    repository = FakeBackupRepository()
    repository.fail_next_import = True
    repository.fail_rollback = True
    service = DatabaseBackupService(repository, AuthorizationService(repository))

    with pytest.raises(BackupRestoreError, match="recovery also failed"):
        service.restore_backup(valid_backup(), {"id": "admin-id", "role": "admin"})


def test_restore_requires_admin():
    repository = FakeBackupRepository()
    service = DatabaseBackupService(repository, AuthorizationService(repository))

    with pytest.raises(PermissionError):
        service.restore_backup(valid_backup(), {"id": "viewer-id", "role": "admin"})

    assert repository.imports == []


def test_backup_export_failure_uses_safe_message_and_logs_cause(caplog):
    repository = FakeBackupRepository()
    repository.fail_export = True
    service = DatabaseBackupService(repository, AuthorizationService(repository))

    with caplog.at_level("ERROR", logger="nrb"):
        with pytest.raises(ApplicationError) as raised:
            service.create_backup({"id": "admin-id", "role": "admin"})

    assert "secret-token" not in str(raised.value)
    assert "secret-token" in caplog.text


def test_status_adapter_failure_is_safe_and_logged(caplog):
    repository = FakeBackupRepository()
    repository.ping = lambda: (_ for _ in ()).throw(RuntimeError("driver secret-token"))
    service = DatabaseBackupService(repository, AuthorizationService(repository))

    with caplog.at_level("ERROR", logger="nrb"):
        result = service.database_status({"id": "admin-id", "role": "admin"})

    assert result == (False, "Connection check failed. See application logs.")
    assert "secret-token" in caplog.text
