"""Vélocité / engagement par sprint (US) — {{chart:velocity}}."""
import statistics
from collections import defaultdict

import render_agile
from indicators.common import BACKLOG_KEY, sprint_names, to_float

RENDERERS = {
    "velocity": render_agile.render_velocity,
    "velocity_NB": render_agile.render_velocity_nb,
    "velocity_SP": render_agile.render_velocity_sp,
}


def compute(issues, sprints, conf):
    us_types = set(conf["us_types"])
    done_statuses = set(conf["done_statuses"])
    sp_field = conf["story_points_field"]
    spr_field = conf["sprint_field"]

    velocity_sp = defaultdict(float)              # sprint -> SP terminés
    engaged_sp = defaultdict(float)                # sprint -> SP engagés (1er sprint du champ)
    engaged_us_per_sprint = defaultdict(int)       # sprint -> nb US engagées (1er sprint du champ)
    completed_us_per_sprint = defaultdict(int)     # sprint -> nb US terminées (dernier sprint du champ)

    for it in issues:
        f = it["fields"]
        itype = (f.get("issuetype") or {}).get("name", "Inconnu")
        if itype not in us_types:
            continue
        status = (f.get("status") or {}).get("name", "Inconnu")
        sp = to_float(f.get(sp_field))
        spr_list = sprint_names(f.get(spr_field))
        first_sprint = spr_list[0] if spr_list else BACKLOG_KEY
        last_sprint = spr_list[-1] if spr_list else BACKLOG_KEY

        engaged_us_per_sprint[first_sprint] += 1
        engaged_sp[first_sprint] += sp
        if status in done_statuses:
            velocity_sp[last_sprint] += sp
            completed_us_per_sprint[last_sprint] += 1

    velocity_series = []
    if sprints:
        for sp_meta in sprints:
            n = sp_meta["name"]
            velocity_series.append({
                "sprint": n,
                "engaged": engaged_us_per_sprint.get(n, 0),
                "done": completed_us_per_sprint.get(n, 0),
                "sp_engaged": round(engaged_sp.get(n, 0), 1),
                "sp_done": round(velocity_sp.get(n, 0), 1),
            })

    done_counts = [v["done"] for v in velocity_series if v["done"] > 0]
    avg_velocity = round(sum(done_counts) / len(done_counts), 1) if done_counts else 0
    # Médiane US en excluant les sprints à 0 terminé (ligne rouge chart:velocity)
    median_velocity_us = round(statistics.median(done_counts), 1) if done_counts else 0
    sp_done_vals = [v["sp_done"] for v in velocity_series if v["done"] > 0]
    median_velocity_sp = round(statistics.median(sp_done_vals), 1) if sp_done_vals else 0

    return {
        "velocity": velocity_series,
        "avg_velocity": avg_velocity,
        "median_velocity_us": median_velocity_us,
        "median_velocity_sp": median_velocity_sp,
    }
