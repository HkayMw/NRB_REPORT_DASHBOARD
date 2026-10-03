"""MongoDB persistence adapter for team schedules."""

from nrb.infrastructure.repositories import mongo as db


class MongoScheduleRepository:
    def list_staff(self, active_only=False):
        return db.list_staff(active_only)

    def list_teams(self, active_only=False):
        return db.list_teams(active_only)

    def assignment_history(self):
        return db.assignment_history()

    def save_schedule(self, week_start, week_end, assignments, created_by=""):
        db.save_schedule(week_start, week_end, assignments, created_by)

    def upsert_team(
        self,
        name,
        reports_as_section,
        min_size,
        max_size,
        pinned_members,
        active=1,
        sort_order=0,
        team_id=None,
    ):
        db.upsert_team(
            name,
            reports_as_section,
            min_size,
            max_size,
            pinned_members,
            active,
            sort_order,
            team_id,
        )

    def delete_team(self, team_id):
        db.delete_team(team_id)

    def list_schedules(self, limit=30):
        return db.list_schedules(limit)

    def get_schedule(self, week_start):
        return db.get_schedule(week_start)

    def delete_schedule(self, week_start):
        db.delete_schedule(week_start)
