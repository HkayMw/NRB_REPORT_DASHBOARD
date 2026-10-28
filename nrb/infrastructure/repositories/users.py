"""MongoDB repository adapter for user accounts."""

from nrb.infrastructure.repositories import mongo as db


class MongoUserRepository:
    def count_users(self):
        return db.count_users()

    def list_users(self):
        return db.list_users()

    def get_user(self, username):
        return db.get_user(username)

    def get_user_by_id(self, user_id):
        return db.get_user_by_id(user_id)

    def create_user(self, username, pw_hash, role="viewer", full_name=""):
        db.create_user(username, pw_hash, role, full_name)

    def update_user(self, user_id, **fields):
        db.update_user(user_id, **fields)
