"""Estimation vs consommé cumulés, jour par jour — {{chart:cumul_estimation_conso}}.

Trois courbes cumulées, un point par jour calendaire, du jour du premier
ticket créé dans le périmètre à aujourd'hui :

  - **estimé** (jh) : somme cumulée de `timeoriginalestimate` de tout ticket
    **hors Epic**, ajoutée au jour de sa création (`created`) — pas de sa
    résolution : un ticket estimé mais pas terminé compte dès qu'il existe.
  - **consommé** (jh) : somme cumulée de `timespent` (valeur totale à la date
    d'extraction — JIRA ne conserve pas d'historique jour par jour) des mêmes
    tickets, ajoutée à la **même date** que l'estimé ci-dessus (`created`),
    pas à la date de résolution comme {{chart:burnup}}/{{chart:conso_corrective}}.
    Choix délibéré pour que les deux courbes restent directement comparables
    sur le même axe — au prix d'une réserve de lecture : le consommé affiché
    au jour J peut inclure du temps réellement loggé bien après J, sur des
    tickets créés avant J mais exécutés plus tard (voir COACH_PROMPT.md,
    `cumul_estimation_conso_lecture`).
  - **estimé Epics** (jh) : somme cumulée de `timeoriginalestimate` porté par
    le ticket Epic **lui-même** (pas le rollup de ses enfants, déjà couvert
    par `epics.total_estimate_jh`, voir fetch_jira.py:build_epics), ajoutée
    au jour de création de l'Epic. Repère macro (estimation au lancement de
    l'Epic) en regard du micro (somme des estimations unitaires des tickets,
    courbe "estimé" ci-dessus) — les deux ne sont pas censées coïncider en
    cours de route.

"Epic" est un type de ticket JIRA fixe, jamais paramétrable — même convention
que fetch_jira.py:build_epics (pas de config `epic_types`, contrairement aux
catégories de conso_corrective.py)."""
from datetime import timedelta, timezone
from datetime import datetime as _datetime

import render_agile
from indicators.common import parse_dt, to_float

RENDERERS = {"cumul_estimation_conso": render_agile.render_cumul_estimation_conso}


def compute(issues, sprints, conf):
    spd = conf["seconds_per_day"]

    estimate_by_day = {}
    consumed_by_day = {}
    epic_estimate_by_day = {}

    for it in issues:
        f = it["fields"]
        created = parse_dt(f.get("created"))
        if created is None:
            continue
        day = created.date()
        itype = (f.get("issuetype") or {}).get("name", "")
        if itype == "Epic":
            epic_estimate_by_day[day] = (
                epic_estimate_by_day.get(day, 0.0) + to_float(f.get("timeoriginalestimate")) / spd
            )
        else:
            estimate_by_day[day] = (
                estimate_by_day.get(day, 0.0) + to_float(f.get("timeoriginalestimate")) / spd
            )
            consumed_by_day[day] = (
                consumed_by_day.get(day, 0.0) + to_float(f.get("timespent")) / spd
            )

    all_days = set(estimate_by_day) | set(consumed_by_day) | set(epic_estimate_by_day)
    if not all_days:
        return {"cumul_estimation_conso": None}

    start = min(all_days)
    end = _datetime.now(timezone.utc).date()
    if start > end:
        return {"cumul_estimation_conso": None}

    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]

    estime_jh, consomme_jh, estime_epics_jh = [], [], []
    cum_estime = cum_consomme = cum_epics = 0.0
    for d in days:
        cum_estime += estimate_by_day.get(d, 0.0)
        cum_consomme += consumed_by_day.get(d, 0.0)
        cum_epics += epic_estimate_by_day.get(d, 0.0)
        estime_jh.append(round(cum_estime, 1))
        consomme_jh.append(round(cum_consomme, 1))
        estime_epics_jh.append(round(cum_epics, 1))

    return {
        "cumul_estimation_conso": {
            "categories": [d.strftime("%d/%m/%Y") for d in days],
            "estime_jh": estime_jh,
            "consomme_jh": consomme_jh,
            "estime_epics_jh": estime_epics_jh,
            "total_estime_jh": estime_jh[-1],
            "total_consomme_jh": consomme_jh[-1],
            "total_estime_epics_jh": estime_epics_jh[-1],
            "ecart_conso_estime_jh": round(estime_jh[-1] - consomme_jh[-1], 1),
            "ecart_epics_detail_jh": round(estime_epics_jh[-1] - estime_jh[-1], 1),
        }
    }
