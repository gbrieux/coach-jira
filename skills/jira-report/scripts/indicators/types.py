"""Types de tickets — {{chart:types}} (compte) et {{chart:types_conso}} (jh)."""
from collections import defaultdict

import render_agile
from indicators.common import to_float

RENDERERS = {
    "types": render_agile.render_types,
    "types_conso": render_agile.render_types_conso,
}


def compute(issues, sprints, conf):
    spd = conf["seconds_per_day"]
    type_counts = defaultdict(int)
    type_conso = defaultdict(float)

    for it in issues:
        f = it["fields"]
        itype = (f.get("issuetype") or {}).get("name", "Inconnu")
        type_counts[itype] += 1
        type_conso[itype] += to_float(f.get("timespent")) / spd

    return {
        "type_counts": dict(type_counts),
        "type_conso_jh": {k: round(v, 1) for k, v in type_conso.items()},
    }
