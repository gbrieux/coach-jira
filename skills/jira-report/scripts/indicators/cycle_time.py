"""Cycle time (US) — {{chart:cycle_time}} (P15/médiane/moyenne/P85)."""
import statistics

import render_agile
from indicators.common import filter_issues, parse_dt, percentile

RENDERERS = {"cycle_time": render_agile.render_cycle_time}


def compute(issues, sprints, conf):
    issues = filter_issues(issues, conf, "cycle_time", conf["us_types"])
    done_statuses = set(conf["done_statuses"])

    cycle_us = []
    for it in issues:
        f = it["fields"]
        status = (f.get("status") or {}).get("name", "Inconnu")
        if status not in done_statuses:
            continue
        created = parse_dt(f.get("created"))
        resolved = parse_dt(f.get("resolutiondate"))
        if created and resolved:
            cycle_us.append((resolved - created).days)

    cyc = sorted(cycle_us)
    return {
        "cycle_time": {
            "count": len(cyc),
            "p15": percentile(cyc, 0.15),
            "median": round(statistics.median(cyc), 1) if cyc else 0,
            "mean": round(statistics.mean(cyc), 1) if cyc else 0,
            "p85": percentile(cyc, 0.85),
        }
    }
