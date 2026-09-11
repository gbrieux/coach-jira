"""Temps Tempo par type de ticket et par mois — {{chart:tempo_types}}.
Barres empilées en volume absolu (jh) : worklogs Tempo agrégés par mois de
la date du log (`w["date"]`, pas la date de résolution du ticket ni son
champ Sprint JIRA), une série par type de ticket JIRA exact (`issuetype.name`
du ticket loggé) — tous les types rencontrés dans le périmètre, sans
regroupement (contrairement à {{chart:conso_corrective}}, limité à 4
catégories configurées).

Tempo (app JIRA de CRA/timesheet) n'est pas installée sur tous les projets
suivis par ce skill : `conf["tempo_worklogs"]` vaut `None` si
`TEMPO_API_TOKEN` est absent de `.env`, ou si l'appel à l'API Tempo échoue
(app absente/inaccessible sur cette instance) — dans ce cas l'indicateur
reste présent dans le template mais {{chart:tempo_types}} affiche un message
plutôt qu'un graphique vide (voir fetch_jira.py:fetch_tempo_worklogs et
indicators/tempo_conso.py, même principe).

Le type de ticket d'un worklog est retrouvé via `issue_id` (porté par chaque
worklog depuis fetch_jira.py:fetch_tempo_worklogs) rapporté à `issues` —
un worklog dont l'id ne correspond à aucun ticket du périmètre (cas
théorique, décalage entre la fenêtre Tempo et le JQL) est classé "Inconnu"
plutôt qu'ignoré silencieusement.

Mois = mois du worklog, bornes comme conso_corrective : du mois de
`sprint_start_date` (project.yaml, si configuré, sinon le mois du premier
worklog du périmètre) jusqu'au mois courant, tous les mois intermédiaires
inclus même sans worklog ce mois-là."""
from collections import defaultdict
from datetime import timezone
from datetime import datetime as _datetime

import render_agile
from indicators.common import parse_dt

RENDERERS = {"tempo_types": render_agile.render_tempo_types}


def _month_key(dt):
    return (dt.year, dt.month)


def _month_range(start, end):
    y, m = start
    out = []
    while (y, m) <= end:
        out.append((y, m))
        m = m + 1 if m < 12 else 1
        y = y if m > 1 else y + 1
    return out


def compute(issues, sprints, conf):
    worklogs = conf.get("tempo_worklogs")
    if not worklogs:
        return {"tempo_types": None}

    spd = conf["seconds_per_day"]
    type_by_issue = {
        str(it.get("id")): (it["fields"].get("issuetype") or {}).get("name", "Inconnu")
        for it in issues
    }

    by_month = defaultdict(lambda: defaultdict(float))
    for w in worklogs:
        dt = parse_dt(f"{w['date']}T00:00:00Z") if w.get("date") else None
        if dt is None:
            continue
        itype = type_by_issue.get(str(w.get("issue_id")), "Inconnu")
        by_month[_month_key(dt)][itype] += (w.get("seconds") or 0) / spd

    if not by_month:
        return {"tempo_types": None}

    start_cfg = parse_dt(conf.get("sprint_start_date"))
    start = _month_key(start_cfg) if start_cfg else min(by_month)
    end = _month_key(_datetime.now(timezone.utc))
    if start > end:
        return {"tempo_types": None}

    months = _month_range(start, end)

    types_total = defaultdict(float)
    for month_data in by_month.values():
        for itype, jh in month_data.items():
            types_total[itype] += jh
    types_order = sorted(types_total, key=lambda t: -types_total[t])

    series = {
        itype: [round(by_month.get(mk, {}).get(itype, 0.0), 2) for mk in months]
        for itype in types_order
    }
    totals_jh = {itype: round(v, 1) for itype, v in types_total.items()}
    total_jh = round(sum(totals_jh.values()), 1)

    return {
        "tempo_types": {
            "categories": [f"01/{mk[1]:02d}/{mk[0]}" for mk in months],
            "types_order": types_order,
            "series": series,
            "totals_jh": totals_jh,
            "total_jh": total_jh,
        }
    }
