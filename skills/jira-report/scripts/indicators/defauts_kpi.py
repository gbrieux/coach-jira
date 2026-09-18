"""Indicateurs clés Anomalies & Incidents — {{chart:defauts_kpi}}. Cartes de
synthèse (créées / résolues / backlog ouvert à date / charge / taux de
défaut), catégorisation anomalie/incident via
indicators.common.defect_category (anomaly_types/incident_types,
project.yaml) — indépendant de {{chart:conso_corrective}} (4 catégories,
jamais retouché ici, voir CLAUDE.md « Ajouter un indicateur »).

Définitions (issues des échanges de conception, voir aussi
defauts_tendance.py et defauts_delai_origine.py) :
  - fenêtre = mois de `sprint_start_date` (project.yaml) -> mois courant ;
    à défaut, mois du plus ancien ticket anomalie/incident du périmètre
    (repli identique à conso_corrective.py).
  - créées : tickets du type dont le mois de `created` tombe dans la
    fenêtre (tous statuts).
  - résolues : tickets du type terminés (`done_statuses`) dont le mois de
    `resolutiondate` tombe dans la fenêtre.
  - backlog ouvert à date : tickets du type actuellement hors
    `done_statuses`, sans limite de date de création (peut être antérieur
    à la fenêtre affichée) — un stock, pas un flux.
  - jh : somme des `timespent` (jh) des tickets du type terminés dans la
    fenêtre — même construction que conso_corrective, mais ici jamais
    additif avec créées/résolues/backlog (périmètres différents ; une
    légende de page l'explique, voir render_agile.render_defauts_kpi).
  - taux de défaut : jh de la catégorie ÷ jh total (TOUS types de tickets,
    terminés, même fenêtre) — un ratio de charge, pas un ratio de comptage
    (nb anomalies / nb tickets)."""
from datetime import datetime, timezone

import render_agile
from indicators.common import parse_dt, to_float, defect_category, month_key, month_range

RENDERERS = {"defauts_kpi": render_agile.render_defauts_kpi}

CATEGORIES = ("anomalie", "incident")


def compute(issues, sprints, conf):
    done_statuses = set(conf["done_statuses"])
    spd = conf["seconds_per_day"]
    now = datetime.now(timezone.utc)

    categorized = [
        (it, defect_category((it["fields"].get("issuetype") or {}).get("name", ""), conf))
        for it in issues
    ]
    categorized = [(it, cat) for it, cat in categorized if cat]
    if not categorized:
        return {"defauts_kpi": None}

    start_cfg = parse_dt(conf.get("sprint_start_date"))
    if start_cfg is None:
        created_dates = [d for it, _ in categorized if (d := parse_dt(it["fields"].get("created")))]
        start_cfg = min(created_dates) if created_dates else now
    start_m, end_m = month_key(start_cfg), month_key(now)
    months = set(month_range(start_m, end_m)) if start_m <= end_m else {end_m}
    window_months = len(months)

    def in_window(dt):
        return dt is not None and month_key(dt) in months

    by_cat = {}
    for cat in CATEGORIES:
        items = [it for it, c in categorized if c == cat]
        created = sum(1 for it in items if in_window(parse_dt(it["fields"].get("created"))))
        resolved_items = [
            it for it in items
            if (it["fields"].get("status") or {}).get("name") in done_statuses
            and in_window(parse_dt(it["fields"].get("resolutiondate")))
        ]
        resolved = len(resolved_items)
        jh = round(sum(to_float(it["fields"].get("timespent")) for it in resolved_items) / spd, 1)
        open_items = [
            it for it in items
            if (it["fields"].get("status") or {}).get("name") not in done_statuses
        ]
        open_over_90d = sum(
            1 for it in open_items
            if (d := parse_dt(it["fields"].get("created"))) and (now - d).days > 90
        )
        by_cat[cat] = {
            "created": created,
            "resolved": resolved,
            "open_now": len(open_items),
            "open_over_90d": open_over_90d,
            "jh": jh,
            "jh_per_resolved": round(jh / resolved, 2) if resolved else None,
            "per_month": round(created / window_months, 1) if window_months else 0.0,
        }

    total_jh = 0.0
    for it in issues:
        f = it["fields"]
        if (f.get("status") or {}).get("name") not in done_statuses:
            continue
        if in_window(parse_dt(f.get("resolutiondate"))):
            total_jh += to_float(f.get("timespent")) / spd
    total_jh = round(total_jh, 1)

    for cat in CATEGORIES:
        jh = by_cat[cat]["jh"]
        by_cat[cat]["defect_rate_pct"] = round(100 * jh / total_jh, 1) if total_jh else 0.0

    return {
        "defauts_kpi": {
            **by_cat,
            "total_jh": total_jh,
            "window_months": window_months,
        }
    }
