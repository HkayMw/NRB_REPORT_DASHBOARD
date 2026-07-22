"""Fair section/team allocation and WhatsApp-style schedule text export.

Fairness rule: for every open slot, prefer the person who has gone longest
without serving on that team (never-served ranks first), tie-broken by fewer
total assignments overall, then by name for determinism. Pinned members are
always placed on their team first.
"""

from datetime import date

from nrb import config, db, weeks


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


def generate_schedule(available: list, teams: list, history: list) -> dict:
    """Returns {team_id: [staff_name, ...]}. `available` = staff form_names
    on duty this week; `teams` = active team dicts from db.list_teams()."""
    last_on_team, totals = _recency_maps(history)
    NEVER = 10 ** 6

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
        t = sorted(open_teams, key=lambda t: (len(assignment[t["id"]]), t["sort_order"]))[0]
        name = pick(t, pool)
        assignment[t["id"]].append(name)
        pool.remove(name)

    return {"assignment": assignment, "unplaced": pool}


def whatsapp_text(week_start: date, assignments_by_team: list, roster_full_names: dict) -> str:
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


def scheduled_staff_for(day) -> dict:
    """{staff_name: team_name} scheduled for the week containing `day`."""
    monday, _ = weeks.work_week_of(day)
    sched = db.get_schedule(monday.isoformat())
    if not sched:
        return {}
    return {a["staff_name"]: a["team_name"] for a in sched["assignments"]}
