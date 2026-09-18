"""Délai de traitement & origine Anomalies/Incidents/Travaux — {{chart:defauts_delai_origine}}.

Délai (`delay`) : jours calendaires création -> résolution, P15/médiane/
moyenne/P85 — même construction que indicators/cycle_time.py (US), mais sur
les tickets anomalie/incident/travaux (indicators.common.defect_category)
plutôt que `us_types`, et sans fenêtre temporelle (comme cycle_time.py,
jamais retouché ici) : tous les tickets terminés du périmètre JQL, quelle
que soit leur date de résolution. Pas de 4e catégorie US : échelles trop
différentes — délai création -> résolution d'une US, qui inclut l'attente
en backlog, contre celui d'un ticket anomalie/incident/travaux généralement
bien plus court — rendait la comparaison peu lisible (constaté en QA).

Origine (`origin`) : répartition par **ticket parent** (champ JIRA `parent`,
déjà récupéré par fetch_jira.py — objet abrégé {"key", "fields": {"summary"}}
fourni directement par l'API, pas besoin de résoudre le parent dans le
périmètre JQL) des tickets anomalie/incident/travaux **créés dans la
fenêtre** (même fenêtre que defauts_kpi.py/defauts_tendance.py — mois de
`sprint_start_date` -> mois courant). Un ticket sans parent est compté à
part (`no_parent`), jamais mélangé avec `other` (au-delà du top N,
TOP_N_PARENTS ci-dessous) — deux causes différentes."""
import statistics
from datetime import datetime, timezone

import render_agile
from indicators.common import parse_dt, defect_category, percentile, month_key, month_range

RENDERERS = {"defauts_delai_origine": render_agile.render_defauts_delai_origine}

CATEGORIES = ("anomalie", "incident", "travaux")
TOP_N_PARENTS = 6


def _delay_stats(items, done_statuses):
    days = []
    for it in items:
        f = it["fields"]
        if (f.get("status") or {}).get("name") not in done_statuses:
            continue
        created = parse_dt(f.get("created"))
        resolved = parse_dt(f.get("resolutiondate"))
        if created and resolved:
            days.append((resolved - created).days)
    days.sort()
    return {
        "count": len(days),
        "p15": percentile(days, 0.15),
        "median": round(statistics.median(days), 1) if days else 0,
        "mean": round(statistics.mean(days), 1) if days else 0,
        "p85": percentile(days, 0.85),
    }


def _empty_counts():
    return {cat: 0 for cat in CATEGORIES}


def compute(issues, sprints, conf):
    done_statuses = set(conf["done_statuses"])
    now = datetime.now(timezone.utc)

    categorized = [
        (it, defect_category((it["fields"].get("issuetype") or {}).get("name", ""), conf))
        for it in issues
    ]
    categorized = [(it, cat) for it, cat in categorized if cat]
    if not categorized:
        return {"defauts_delai_origine": None}

    delay = {
        cat: _delay_stats([it for it, c in categorized if c == cat], done_statuses)
        for cat in CATEGORIES
    }

    start_cfg = parse_dt(conf.get("sprint_start_date"))
    if start_cfg is None:
        created_dates = [d for it, _ in categorized if (d := parse_dt(it["fields"].get("created")))]
        start_cfg = min(created_dates) if created_dates else now
    start_m, end_m = month_key(start_cfg), month_key(now)
    months = set(month_range(start_m, end_m)) if start_m <= end_m else {end_m}

    def in_window(dt):
        return dt is not None and month_key(dt) in months

    per_parent = {}
    no_parent = _empty_counts()
    for it, cat in categorized:
        if not in_window(parse_dt(it["fields"].get("created"))):
            continue
        parent = it["fields"].get("parent")
        if not parent:
            no_parent[cat] += 1
            continue
        key = parent.get("key")
        name = (parent.get("fields") or {}).get("summary") or key
        per_parent.setdefault(key, {"name": name, **_empty_counts()})
        per_parent[key][cat] += 1

    def total(v):
        return sum(v[cat] for cat in CATEGORIES)

    ranked = sorted(per_parent.items(), key=lambda kv: -total(kv[1]))
    top, rest = ranked[:TOP_N_PARENTS], ranked[TOP_N_PARENTS:]
    other = {cat: sum(v[cat] for _, v in rest) for cat in CATEGORIES}

    return {
        "defauts_delai_origine": {
            "delay": delay,
            "origin": {
                "parents": [{"key": k, **v} for k, v in top],
                "other": other,
                "no_parent": no_parent,
            },
        }
    }
