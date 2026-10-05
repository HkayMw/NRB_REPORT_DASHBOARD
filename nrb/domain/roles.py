"""User roles and what each one may do.

Admins may do everything. Clerks run the week-to-week work: they create
schedules and keep the staff roster current, but cannot change or delete a
saved schedule, manage users, teams, data sources, report layout or the
database. Viewers only read. Downloading the monthly report needs a login,
not a permission.
"""

VIEWER = "viewer"
CLERK = "clerk"
ADMIN = "admin"
ROLES = (VIEWER, CLERK, ADMIN)

CREATE_SCHEDULE = "create_schedule"
EDIT_SCHEDULE = "edit_schedule"  # change or delete a saved schedule
MANAGE_ROSTER = "manage_roster"

_ROLE_PERMISSIONS = {
    VIEWER: frozenset(),
    CLERK: frozenset({CREATE_SCHEDULE, MANAGE_ROSTER}),
}


def has_permission(role: str | None, permission: str) -> bool:
    if role == ADMIN:
        return True
    return permission in _ROLE_PERMISSIONS.get(role, frozenset())
