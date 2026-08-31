"""Charge corrective — {{chart:conso_corrective}}. Part de la consommation
(jh) par mois sur tickets terminés, ventilée en 4 catégories : anomalie /
incident / Us / US tech. 100% empilé : chaque mois affiche une part relative,
pas un volume absolu — voir render_agile.render_conso_corrective.

Périmètre limité à ces 4 catégories, comme les indicateurs US-scopés qui
ignorent déjà tout type hors `us_types` (burnup, burndown, vélocité, statuts,
cycle time) : un ticket terminé dont le type n'apparaît dans aucune des 4
listes ci-dessous n'est compté ni au numérateur ni au dénominateur — pas de
5e bucket "Autre" qui diluerait la lecture anomalie/incident vs Us/US tech.

Catégorisation par type de ticket JIRA exact (project.yaml, jamais deviné à
partir du libellé) :
  anomaly_types:  ["Anomalie", "Bug"]     # priorité 1
  incident_types: ["Incident"]            # priorité 2
  tech_types:     ["Technical Story"]     # "US tech" — priorité 3
  us_types:       ["User Story", "Story"] # "Us" — déjà utilisé par les autres
                                           # indicateurs US-scopés, priorité 4
Un type présent dans plusieurs listes (mauvaise config) est classé dans la
première catégorie qui le contient, dans l'ordre ci-dessus.

Mois = mois de `resolutiondate` (date de passage dans un statut de
`done_statuses`), pas la date de création. Bornes affichées : du mois de
`sprint_start_date` (project.yaml, s'il est configuré — sinon le mois du
premier ticket résolu dans le périmètre) jusqu'au mois courant, tous les mois
intermédiaires inclus même sans ticket résolu ce mois-là (colonne vide plutôt
qu'absente de la frise, comme sur l'exemple de référence de l'indicateur)."""
from collections import defaultdict
from datetime import timezone
from datetime import datetime as _datetime

import render_agile
from indicators.common import parse_dt, to_float

RENDERERS = {"conso_corrective": render_agile.render_conso_corrective}

CATEGORIES = ["anomalie", "incident", "us", "us_tech"]


def _category(itype, conf):
    if itype in conf["anomaly_types"]:
        return "anomalie"
    if itype in conf["incident_types"]:
        return "incident"
    if itype in conf["tech_types"]:
        return "us_tech"
    if itype in conf["us_types"]:
        return "us"
    return None


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
    done_statuses = set(conf["done_statuses"])
    spd = conf["seconds_per_day"]

    by_month = defaultdict(lambda: defaultdict(float))
    for it in issues:
        f = it["fields"]
        if (f.get("status") or {}).get("name") not in done_statuses:
            continue
        cat = _category((f.get("issuetype") or {}).get("name", ""), conf)
        if cat is None:
            continue
        resolved = parse_dt(f.get("resolutiondate"))
        if resolved is None:
            continue
        by_month[_month_key(resolved)][cat] += to_float(f.get("timespent")) / spd

    if not by_month:
        return {"conso_corrective": None}

    start_cfg = parse_dt(conf.get("sprint_start_date"))
    start = _month_key(start_cfg) if start_cfg else min(by_month)
    end = _month_key(_datetime.now(timezone.utc))
    if start > end:
        return {"conso_corrective": None}

    months = _month_range(start, end)
    series = {cat: [round(by_month.get(mk, {}).get(cat, 0.0), 2) for mk in months] for cat in CATEGORIES}
    totals_jh = {cat: round(sum(series[cat]), 1) for cat in CATEGORIES}
    total_jh = round(sum(totals_jh.values()), 1)
    corrective_jh = round(totals_jh["anomalie"] + totals_jh["incident"], 1)

    return {
        "conso_corrective": {
            "categories": [f"01/{mk[1]:02d}/{mk[0]}" for mk in months],
            "series": series,
            "totals_jh": totals_jh,
            "total_jh": total_jh,
            "corrective_jh": corrective_jh,
            "corrective_pct": round(100 * corrective_jh / total_jh, 1) if total_jh else 0.0,
        }
    }
