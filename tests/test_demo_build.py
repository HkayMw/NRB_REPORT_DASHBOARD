"""Checks for the public demo build: synthetic data, seeding and demo logins."""

import mongomock
import pandas as pd
import pytest

from nrb import config
from nrb.application.services.authorization import AuthorizationService
from nrb.application.services.user_management import UserManagementService
from nrb.domain.cleaning import clean_responses
from nrb.infrastructure.data_sources import demo_csv
from nrb.infrastructure.repositories import mongo
from nrb.infrastructure.repositories.users import MongoUserRepository


@pytest.fixture
def demo_db(monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", True)
    client = mongomock.MongoClient()
    monkeypatch.setattr(mongo, "get_uri", lambda: "mongomock://test")
    monkeypatch.setattr(mongo, "_client", lambda uri: client)
    mongo.init_db()
    return client


def test_demo_responses_cover_the_full_range_and_clean():
    raw = demo_csv.fetch_responses.__wrapped__("ignored")
    roster = [form for form, _ in config.DEMO_ROSTER]
    result = clean_responses(raw, roster, today=config.DEMO_AS_OF)

    dates = result.clean["date"]
    assert dates.min() <= pd.Timestamp(config.DEMO_DATA_START) + pd.Timedelta(days=3)
    assert dates.max() >= pd.Timestamp(config.DEMO_AS_OF) - pd.Timedelta(days=3)
    assert len(result.clean) > 3000
    # The data quality page has realistic problems to show.
    assert not result.dropped_duplicates.empty
    assert not result.unknown_names.empty
    assert not result.issues.empty
    assert "Future date" not in set(result.issues["issue"])


def test_demo_names_are_fictional_roster_only():
    raw = demo_csv.fetch_responses.__wrapped__("ignored")
    roster = {form for form, _ in config.DEMO_ROSTER}
    names = {n.strip() for cell in raw["Name"].dropna() for n in cell.split(",")}
    unknown = names - roster
    # Only lowercase free-text surnames (the planted "unknown name" rows) remain.
    assert all(name.islower() for name in unknown)


def test_init_seeds_matching_schedules(demo_db):
    schedules = mongo.list_schedules(limit=500)
    assert len(schedules) > 100
    team_ids = {t["id"] for t in mongo.list_teams()}
    for schedule in schedules:
        assert {a["team_id"] for a in schedule["assignments"]} <= team_ids


def test_demo_accounts_are_created_and_restored(demo_db):
    mongo.ensure_demo_accounts(lambda pw: f"hash:{pw}")
    usernames = {u["username"] for u in mongo.list_users()}
    assert usernames >= config.DEMO_USERNAMES

    admin = mongo.get_user("demo_admin")
    mongo.update_user(admin["id"], active=0, role="viewer")
    mongo.ensure_demo_accounts(lambda pw: f"hash:{pw}")
    restored = mongo.get_user("demo_admin")
    assert restored["active"] == 1 and restored["role"] == "admin"


def test_live_mode_seeds_no_demo_data(monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", False)
    client = mongomock.MongoClient()
    monkeypatch.setattr(mongo, "get_uri", lambda: "mongomock://test")
    monkeypatch.setattr(mongo, "_client", lambda uri: client)
    mongo.init_db()
    assert mongo.list_schedules() == []
    assert {s["form_name"] for s in mongo.list_staff()} == {
        form for form, _ in config.DEFAULT_ROSTER
    }


def test_demo_accounts_cannot_be_edited(demo_db):
    mongo.ensure_demo_accounts(lambda pw: f"hash:{pw}")
    repository = MongoUserRepository()
    service = UserManagementService(
        repository, lambda pw: f"hash:{pw}", AuthorizationService(repository)
    )
    admin = repository.get_user("demo_admin")
    viewer = repository.get_user("demo_viewer")
    with pytest.raises(PermissionError):
        service.update_user(viewer["id"], "viewer", True, "newpassword", admin)
