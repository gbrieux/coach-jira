"""Répartition des US par nombre de sprints — {{chart:sprint_spread}}."""
from collections import defaultdict

import render_agile
from indicators.common import sprint_names

RENDERERS = {"sprint_spread": render_agile.render_sprint_spread}


def compute(issues, sprints, conf):
    us_types = set(conf["us_types"])
    done_statuses = set(conf["done_statuses"])
    spr_field = conf["sprint_field"]

    counts = defaultdict(int)  # nb de sprints traversés -> nb d'US
    for it in issues:
        f = it["fields"]
        itype = (f.get("issuetype") or {}).get("name", "Inconnu")
        status = (f.get("status") or {}).get("name", "Inconnu")
        if itype not in us_types or status not in done_statuses:
            continue
        nb_sprints = len(set(sprint_names(f.get(spr_field))))
        if nb_sprints == 0:
            continue
        counts[nb_sprints] += 1

    return {"sprint_spread": dict(sorted(counts.items()))}
