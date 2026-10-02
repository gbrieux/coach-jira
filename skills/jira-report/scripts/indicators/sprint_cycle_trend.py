"""Évolution du temps de cycle (US) par sprint — {{chart:sprint_cycle_trend}}.

Même mesure que l'encart « Temps de cycle d'un ticket » de
{{chart:sprint_spread}} (indicators.common.sprint_cycle : entrée en sprint
-> premier passage dans un `done_statuses`, jours calendaires), ventilée par
**sprint d'entrée** (le premier sprint de l'US, celui qui démarre le plus
tôt) : P15 / médiane / P85 par sprint, dans l'ordre des sprints du board.

Rattachement au sprint d'entrée -> les sprints récents sont **incomplets** :
leurs US encore ouvertes n'ont pas de temps de cycle, et seules les plus
rapides y figurent déjà — leur médiane est mécaniquement basse. `open`
(US entrées dans ce sprint, pas encore terminées) le rend visible au rendu
plutôt que de le laisser passer pour une amélioration. Sprints futurs
(`state == "future"`) exclus."""
import render_agile
from indicators.common import parse_dt, percentile, resolve_status_names, sprint_cycle

RENDERERS = {"sprint_cycle_trend": render_agile.render_sprint_cycle_trend}


def compute(issues, sprints, conf):
    if not sprints:
        return {"sprint_cycle_trend": None}
    us_types = set(conf["us_types"])
    done_statuses = set(conf["done_statuses"])
    spr_field = conf["sprint_field"]
    sprint_starts = {s["name"]: parse_dt(s.get("startDate")) for s in sprints if s.get("name")}
    id_to_current_name = resolve_status_names(issues)

    days_by_sprint = {s["name"]: [] for s in sprints}
    open_by_sprint = {s["name"]: 0 for s in sprints}
    for it in issues:
        f = it["fields"]
        if (f.get("issuetype") or {}).get("name") not in us_types:
            continue
        status = (f.get("status") or {}).get("name")
        sprint_name, days = sprint_cycle(it, spr_field, done_statuses, sprint_starts, id_to_current_name)
        if sprint_name not in days_by_sprint:
            continue  # sans sprint, ou sprint hors board / antérieur à sprint_start_date
        if status not in done_statuses:
            open_by_sprint[sprint_name] += 1
        elif days is not None:
            days_by_sprint[sprint_name].append(days)

    items = []
    for s in sprints:
        if s.get("state") == "future":
            continue  # pas encore démarré -> rien à mesurer, n'encombre pas l'axe
        vals = sorted(days_by_sprint[s["name"]])
        items.append({
            "sprint": s["name"],
            "state": s.get("state"),
            "count": len(vals),
            "open": open_by_sprint[s["name"]],
            "p15": percentile(vals, 0.15) if vals else None,
            "median": percentile(vals, 0.50) if vals else None,
            "p85": percentile(vals, 0.85) if vals else None,
        })
    if not any(it["count"] for it in items):
        return {"sprint_cycle_trend": None}
    return {"sprint_cycle_trend": {"items": items}}
