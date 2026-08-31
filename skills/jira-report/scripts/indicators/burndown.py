"""Burndown du sprint en cours (US) — {{chart:burndown}}."""
from datetime import timedelta, timezone
from datetime import datetime as _datetime

import render_agile
from indicators.common import parse_dt, sprint_names, to_float

RENDERERS = {
    "burndown": render_agile.render_burndown,
    "burndown_NB": render_agile.render_burndown_nb,
    "burndown_SP": render_agile.render_burndown_sp,
}


def compute(issues, sprints, conf):
    """Burndown du sprint EN COURS (actif) uniquement, en nombre de US :
    reste à faire jour par jour vs droite idéale. Périmètre = toute US dont
    le champ Sprint JIRA inclut le sprint actif à date (reports inclus, pas
    seulement les US ajoutées pendant ce sprint)."""
    us_types = set(conf["us_types"])
    done_statuses = set(conf["done_statuses"])
    spr_field = conf["sprint_field"]
    sp_field = conf["story_points_field"]

    active = next((s for s in sprints if s["state"] == "active"), None)
    if not active:
        return {"burndown_sprint": None}
    start = parse_dt(active["startDate"])
    end = parse_dt(active["endDate"])
    if not start or not end:
        return {"burndown_sprint": None}

    scope_issues = []
    for it in issues:
        f = it["fields"]
        itype = (f.get("issuetype") or {}).get("name", "")
        if itype not in us_types:
            continue
        if active["name"] in sprint_names(f.get(spr_field)):
            scope_issues.append(f)
    scope = len(scope_issues)
    if scope == 0:
        return {"burndown_sprint": None}
    scope_sp = round(sum(to_float(f.get(sp_field)) for f in scope_issues), 1)

    total_days = max((end.date() - start.date()).days, 1)
    today = _datetime.now(timezone.utc).date()

    categories, ideal, real, ideal_sp, real_sp = [], [], [], [], []
    for d in range(total_days + 1):
        day = (start + timedelta(days=d)).date()
        categories.append(day.strftime("%d/%m"))
        ideal.append(round(scope - scope * d / total_days, 1))
        ideal_sp.append(round(scope_sp - scope_sp * d / total_days, 1))
        if day <= today:
            done_by_day = sum(
                1 for f in scope_issues
                if (f.get("status") or {}).get("name") in done_statuses
                and (r := parse_dt(f.get("resolutiondate"))) and r.date() <= day
            )
            done_sp_by_day = sum(
                to_float(f.get(sp_field)) for f in scope_issues
                if (f.get("status") or {}).get("name") in done_statuses
                and (r := parse_dt(f.get("resolutiondate"))) and r.date() <= day
            )
            real.append(scope - done_by_day)
            real_sp.append(round(scope_sp - done_sp_by_day, 1))
        else:
            real.append(None)
            real_sp.append(None)

    return {
        "burndown_sprint": {
            "sprint": active["name"],
            "scope": scope,
            "scope_sp": scope_sp,
            "categories": categories,
            "ideal": ideal,
            "real": real,
            "ideal_sp": ideal_sp,
            "real_sp": real_sp,
        }
    }
