import mongomock

from nrb.infrastructure.repositories import mongo
from nrb.infrastructure.repositories.schedules import MongoScheduleRepository
from nrb.infrastructure.repositories.users import MongoUserRepository


def test_mongo_repository_round_trips_user_and_schedule(monkeypatch):
    client = mongomock.MongoClient()
    monkeypatch.setattr(mongo, "get_uri", lambda: "mongomock://test")
    monkeypatch.setattr(mongo, "_client", lambda uri: client)

    mongo.init_db()
    users = MongoUserRepository()
    schedules = MongoScheduleRepository()
    users.create_user(" admin ", "stored-hash", "admin", "A. User")
    team = mongo.list_teams(active_only=True)[0]
    assignments = [(team["id"], "Alice", 0)]
    schedules.save_schedule("2026-10-05", "2026-10-09", assignments, "admin")

    user = users.get_user("admin")
    schedule = schedules.get_schedule("2026-10-05")

    assert user["pw_hash"] == "stored-hash"
    assert user["role"] == "admin"
    assert schedule["schedule"]["week_end"] == "2026-10-09"
    assert schedule["assignments"] == [
        {
            "team_id": team["id"],
            "staff_name": "Alice",
            "position": 0,
            "team_name": team["name"],
        }
    ]
    assert schedules.assignment_history() == [
        {
            "week_start": "2026-10-05",
            "team_id": team["id"],
            "staff_name": "Alice",
        }
    ]
