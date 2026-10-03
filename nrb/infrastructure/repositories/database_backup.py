"""MongoDB adapter for administrative status and backup operations."""

from nrb.infrastructure.repositories import mongo as db


class MongoDatabaseBackupRepository:
    def ping(self):
        return db.ping()

    def export_all(self):
        return db.export_all()

    def import_all(self, dump):
        db.import_all(dump)
