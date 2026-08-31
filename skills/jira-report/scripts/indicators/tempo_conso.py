"""Conso Tempo (CRA) par sprint vs US terminées — {{chart:tempo_conso}}.
Barres : conso Tempo (jh), worklogs agrégés par sprint dans la fenêtre duquel
tombe leur date de log (`indicators.common.sprint_date_bucket`, même règle
que le burnup/burndown — pas le champ Sprint JIRA du ticket loggé). Ligne
(axe secondaire) : nb d'US terminées par sprint, réutilisé tel quel depuis
`indicators.burnup._build_rollup` (même rollup que {{chart:burnup}} /
{{liste_sprints}}) plutôt que recalculé ici — une seule source de vérité
pour "US terminées par sprint".

Tempo (app JIRA de CRA/timesheet) n'est pas installée sur tous les projets
suivis par ce skill. `conf["tempo_worklogs"]` (calculé par
`fetch_jira.py:fetch_tempo_worklogs`, avant l'appel à `compute()`) vaut
`None` si `TEMPO_API_TOKEN` est absent de `.env`, ou si l'appel à l'API
Tempo échoue (app absente/inaccessible sur cette instance) — dans ce cas
l'indicateur reste présent dans le template mais {{chart:tempo_conso}}
affiche un message plutôt qu'un graphique vide."""
from collections import defaultdict

import render_agile
from indicators.burnup import _build_rollup
from indicators.common import BACKLOG_KEY, parse_dt, sprint_date_bucket, sprint_label

RENDERERS = {"tempo_conso": render_agile.render_tempo_conso}


def compute(issues, sprints, conf):
    worklogs = conf.get("tempo_worklogs")
    if worklogs is None:
        return {"tempo_conso": None}

    spd = conf["seconds_per_day"]
    conso_by_bucket = defaultdict(float)
    for w in worklogs:
        # w["date"] (Tempo startDate) est une date "YYYY-MM-DD" sans heure ni
        # fuseau -> parse_dt() la renvoie naïve, alors que les dates de sprint
        # (created/resolutiondate JIRA) sont toujours "aware" (suffixe Z) :
        # comparer les deux plante (TypeError). Minuit UTC est arbitraire
        # mais anodin ici — seul le jour compte pour situer le worklog dans
        # la fenêtre du sprint.
        date = w.get("date")
        dt = parse_dt(f"{date}T00:00:00Z") if date else None
        bucket = sprint_date_bucket(dt, sprints)
        conso_by_bucket[bucket] += (w.get("seconds") or 0) / spd

    rollup = _build_rollup(issues, sprints, conf)
    if not rollup:
        return {"tempo_conso": None}

    categories, conso_jh, done_us = [], [], []
    for b in rollup:
        key = BACKLOG_KEY if b["sprint"] == "Sprint 0" else b["sprint"]
        categories.append(sprint_label(b["num"], b["end"]))
        conso_jh.append(round(conso_by_bucket.get(key, 0.0), 1))
        done_us.append(b["done_us"])

    total_conso_jh = round(sum(conso_jh), 1)
    total_done_us = sum(done_us)
    return {
        "tempo_conso": {
            "categories": categories,
            "conso_jh": conso_jh,
            "done_us": done_us,
            "total_conso_jh": total_conso_jh,
            "total_done_us": total_done_us,
            "avg_jh_per_us": round(total_conso_jh / total_done_us, 1) if total_done_us else None,
        }
    }
