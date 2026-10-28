"""MongoDB adapter for admin data-source and roster settings."""

from nrb.infrastructure.repositories import mongo as db


class MongoAdminSettingsRepository:
    def get_setting(self, key, default=None):
        return db.get_setting(key, default)

    def set_setting(self, key, value):
        db.set_setting(key, value)

    def list_staff(self):
        return db.list_staff()

    def upsert_staff(self, form_name, full_name, active, staff_id=None):
        db.upsert_staff(form_name, full_name, active, staff_id)

    def delete_staff(self, staff_id):
        db.delete_staff(staff_id)
