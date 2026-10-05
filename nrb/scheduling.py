"""Fair section/team allocation and WhatsApp-style schedule text export.

Fairness rule: for every open slot, prefer the person who has gone longest
without serving on that team (never-served ranks first), tie-broken by fewer
total assignments overall, then by name for determinism. Pinned members are
always placed on their team first.
"""

from datetime import date, timedelta

from nrb import config, weeks


def _recency_maps(history):
    """last_on_team[(team_id, name)] = weeks-ago rank; totals[name] = count."""
    last_on_team, totals = {}, {}
    week_ranks = {}
    for h in history:  # newest first
        week_ranks.setdefault(h["week_start"], len(week_ranks))
        key = (h["team_id"], h["staff_name"])
        if key not in last_on_team:
            last_on_team[key] = week_ranks[h["week_start"]]
        totals[h["staff_name"]] = totals.get(h["staff_name"], 0) + 1
    return last_on_team, totals


def validate_schedule(
    week_start: str,
    week_end: str,
    assignments: list[tuple[str, str, int]],
    teams: list[dict],
    active_staff: list[dict],
    available_staff: list[str],
) -> None:
    """Reject schedules that violate date, roster, capacity, or pin rules."""
    try:
        start = date.fromisoformat(week_start)
        end = date.fromisoformat(week_end)
    except (TypeError, ValueError) as error:
        raise ValueError("Schedule dates must be valid ISO dates.") from error
    if start.weekday() != 0:
        raise ValueError("Schedule week must start on a Monday.")
    if end != start + timedelta(days=4):
        raise ValueError("Schedule week must end on the Friday after its Monday.")

    teams_by_id = {str(team["id"]): team for team in teams}
    active_names = {staff["form_name"] for staff in active_staff}
    available_names = set(available_staff)
    if len(available_names) != len(available_staff):
        raise ValueError("Available staff must not contain duplicates.")
    if not available_names <= active_names:
        raise ValueError("Available staff must all be active roster members.")

    for team in teams:
        pinned = team.get("pinned_members", [])
        if not isinstance(pinned, list) or not set(pinned) <= active_names:
            raise ValueError(
                f"Pinned members for team '{team['name']}' must be active staff."
            )

    counts = {team_id: 0 for team_id in teams_by_id}
    assigned_team_by_staff = {}
    for team_id, staff_name, _position in assignments:
        team_id = str(team_id)
        if team_id not in teams_by_id:
            raise ValueError("Assignments may only use active teams.")
        if staff_name not in active_names:
            raise ValueError(f"'{staff_name}' is not active roster staff.")
        if staff_name not in available_names:
            raise ValueError(f"'{staff_name}' is not available this week.")
        if staff_name in assigned_team_by_staff:
            raise ValueError(f"'{staff_name}' may only be assigned once per week.")
        counts[team_id] += 1
        assigned_team_by_staff[staff_name] = team_id

    for team_id, team in teams_by_id.items():
        count = counts[team_id]
        if count < team["min_size"] or count > team["max_size"]:
            raise ValueError(
                f"Team '{team['name']}' must have between {team['min_size']} "
                f"and {team['max_size']} members."
            )
        for pinned_name in team.get("pinned_members", []):
            if (
                pinned_name in available_names
                and assigned_team_by_staff.get(pinned_name) != team_id
            ):
                raise ValueError(
                    f"Available pinned member '{pinned_name}' must be assigned "
                    f"to team '{team['name']}'."
                )


def generate_schedule(available: list, teams: list, history: list) -> dict:
    """Returns {team_id: [staff_name, ...]}. `available` = staff form_names
    on duty this week; `teams` and `history` are supplied by the caller."""
    last_on_team, totals = _recency_maps(history)
    NEVER = 10**6

    assignment = {t["id"]: [] for t in teams}
    pool = list(dict.fromkeys(available))

    # 1. Pinned members first.
    for t in teams:
        for name in t["pinned_members"]:
            if name in pool:
                assignment[t["id"]].append(name)
                pool.remove(name)

    def pick(team, pool):
        def score(name):
            ago = last_on_team.get((team["id"], name), NEVER)
            return (-ago, totals.get(name, 0), name)  # longest-ago first

        return sorted(pool, key=score)[0]

    # 2. Fill every team to min_size, most-constrained teams first.
    for t in sorted(teams, key=lambda t: -(t["min_size"] - len(assignment[t["id"]]))):
        while len(assignment[t["id"]]) < t["min_size"] and pool:
            name = pick(t, pool)
            assignment[t["id"]].append(name)
            pool.remove(name)

    # 3. Spread remaining people up to max_size, emptiest teams first.
    while pool:
        open_teams = [t for t in teams if len(assignment[t["id"]]) < t["max_size"]]
        if not open_teams:
            break
        t = sorted(
            open_teams, key=lambda t: (len(assignment[t["id"]]), t["sort_order"])
        )[0]
        name = pick(t, pool)
        assignment[t["id"]].append(name)
        pool.remove(name)

    return {"assignment": assignment, "unplaced": pool}


def whatsapp_text(
    week_start: date, assignments_by_team: list, roster_full_names: dict
) -> str:
    """assignments_by_team: [(team_name, [staff_form_name, ...])] in display order."""
    monday, friday = week_start, week_start
    if week_start.weekday() == 0:
        monday, friday = weeks.work_week_of(week_start)
    lines = [f"*_Work Schedule - Week of {weeks.pretty_range(monday, friday)}_*", ""]
    for team_name, members in assignments_by_team:
        if not members:
            continue
        lines.append(f"*_{team_name}:_*")
        for i, m in enumerate(members, 1):
            lines.append(f"{i}. {roster_full_names.get(m, m)}")
        lines.append("")
    lines.append(config.SCHEDULE_FOOTER)
    return "\n".join(lines)
