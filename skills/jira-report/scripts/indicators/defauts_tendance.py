"""Tendance Anomalies & Incidents — {{chart:defauts_tendance}}. Par
catégorie (anomalie/incident, voir indicators.common.defect_category) :
série mensuelle créées/résolues + stock ouvert en fin de mois, et
répartition par ancienneté du backlog actuellement ouvert.

Même fenêtre que defauts_kpi.py (mois de `sprint_start_date` -> mois
courant, repli sur le plus ancien ticket sinon) — voir sa docstring pour le
détail des définitions créées/résolues.

Stock ouvert en fin de mois : approximation à partir de `created`/
`resolutiondate` seuls (pas de reconstruction par changelog, contrairement à
{{chart:cumulative_flow_diagram}}) — un ticket est compté ouvert à la date
de césure `cutoff` si `created < cutoff` et (`resolutiondate` absent ou
`resolutiondate >= cutoff`). Le mois courant (non terminé) est coupé à
"maintenant", pas à sa fin calendaire.

Ancienneté du backlog actuellement ouvert : tranches configurables via
`defect_age_buckets` (project.yaml, jours), voir indicators.common.
age_bucket_labels/age_bucket_index."""
from datetime import datetime, timezone

import render_agile
from indicators.common import (
    parse_dt, to_float, defect_category, month_key, month_range,
    age_bucket_labels, age_bucket_index,
)

RENDERERS = {"defauts_tendance": render_agile.render_defauts_tendance}

CATEGORIES = ("anomalie", "incident")


def _cutoff(month_k, now):
    y, m = month_k
    if month_k == month_key(now):
        return now
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    return datetime(ny, nm, 1, tzinfo=timezone.utc)


def compute(issues, sprints, conf):
    done_statuses = set(conf["done_statuses"])
    bounds = conf.get("defect_age_buckets") or [7, 30, 90]
    now = datetime.now(timezone.utc)

    categorized = [
        (it, defect_category((it["fields"].get("issuetype") or {}).get("name", ""), conf))
        for it in issues
    ]
    categorized = [(it, cat) for it, cat in categorized if cat]
    if not categorized:
        return {"defauts_tendance": None}

    start_cfg = parse_dt(conf.get("sprint_start_date"))
    if start_cfg is None:
        created_dates = [d for it, _ in categorized if (d := parse_dt(it["fields"].get("created")))]
        start_cfg = min(created_dates) if created_dates else now
    start_m, end_m = month_key(start_cfg), month_key(now)
    months = month_range(start_m, end_m) if start_m <= end_m else [end_m]
    categories = [f"{mk[1]:02d}/{str(mk[0])[2:]}" for mk in months]

    result = {"categories": categories, "age_buckets": {"labels": age_bucket_labels(bounds)}}

    window_start_cutoff = datetime(start_m[0], start_m[1], 1, tzinfo=timezone.utc)

    for cat in CATEGORIES:
        items = [it for it, c in categorized if c == cat]
        created_dt = {it["key"]: parse_dt(it["fields"].get("created")) for it in items}
        resolved_dt = {}
        for it in items:
            if (it["fields"].get("status") or {}).get("name") in done_statuses:
                resolved_dt[it["key"]] = parse_dt(it["fields"].get("resolutiondate"))

        def stock_at(cutoff):
            return sum(
                1 for it in items
                if (cd := created_dt[it["key"]]) and cd < cutoff
                and (resolved_dt.get(it["key"]) is None or resolved_dt[it["key"]] >= cutoff)
            )

        created_series, resolved_series, stock_series = [], [], []
        for mk in months:
            created_series.append(sum(1 for d in created_dt.values() if d and month_key(d) == mk))
            resolved_series.append(sum(
                1 for k, d in resolved_dt.items() if d and month_key(d) == mk
            ))
            stock_series.append(stock_at(_cutoff(mk, now)))

        open_items = [
            it for it in items
            if (it["fields"].get("status") or {}).get("name") not in done_statuses
        ]
        age_counts = [0] * (len(bounds) + 1)
        for it in open_items:
            cd = created_dt[it["key"]]
            if cd is None:
                continue
            age_counts[age_bucket_index((now - cd).days, bounds)] += 1

        result[cat] = {
            "created": created_series,
            "resolved": resolved_series,
            "stock": stock_series,
            "stock_start": stock_at(window_start_cutoff),
            "stock_end": stock_series[-1] if stock_series else 0,
        }
        result["age_buckets"][cat] = age_counts

    return {"defauts_tendance": result}
