"""Burnup release (US) — {{chart:burnup}} — et le rollup par sprint qui
l'alimente, réutilisé tel quel comme source de {{liste_sprints}} (build_ppt.py)."""
import math
import re
import statistics
from collections import defaultdict
from datetime import timedelta, timezone
from datetime import datetime as _datetime

import render_agile
from indicators.common import (
    BACKLOG_KEY, FORECAST_MAX_HORIZON, parse_dt, percentile, sprint_date_bucket,
    sprint_label, sprint_names, to_float,
)

RENDERERS = {
    "burnup": render_agile.render_burnup,
    "burnup_NB": render_agile.render_burnup_nb,
    "burnup_SP": render_agile.render_burnup_sp,
}


def _build_rollup(issues, sprints, conf):
    """Rollup US par sprint : ajouts/terminés/estimation/conso, cumulés dans
    l'ordre chronologique des sprints (+ "Sprint 0" pour le backlog jamais
    affecté à un sprint). Alimente à la fois le burnup et le tableau des
    sprints (liste_sprints)."""
    us_types = set(conf["us_types"])
    done_statuses = set(conf["done_statuses"])
    spd = conf["seconds_per_day"]
    sp_field = conf["story_points_field"]

    added_us_per_sprint = defaultdict(int)
    done_us_per_sprint = defaultdict(int)
    estimate_us_per_sprint = defaultdict(float)
    conso_us_per_sprint = defaultdict(float)
    added_sp_per_sprint = defaultdict(float)
    done_sp_per_sprint = defaultdict(float)

    for it in issues:
        f = it["fields"]
        itype = (f.get("issuetype") or {}).get("name", "Inconnu")
        if itype not in us_types:
            continue
        status = (f.get("status") or {}).get("name", "Inconnu")
        estimate_days = to_float(f.get("timeoriginalestimate")) / spd
        consumed_days = to_float(f.get("timespent")) / spd
        sp = to_float(f.get(sp_field))
        created = parse_dt(f.get("created"))
        resolved = parse_dt(f.get("resolutiondate"))

        # added_us/done_us se basent sur la fenêtre de date (created/resolved),
        # pas sur le champ Sprint JIRA — voir sprint_date_bucket.
        added_bucket = sprint_date_bucket(created, sprints)
        added_us_per_sprint[added_bucket] += 1
        estimate_us_per_sprint[added_bucket] += estimate_days
        added_sp_per_sprint[added_bucket] += sp

        if status in done_statuses:
            done_bucket = sprint_date_bucket(resolved, sprints)
            done_us_per_sprint[done_bucket] += 1
            conso_us_per_sprint[done_bucket] += consumed_days
            done_sp_per_sprint[done_bucket] += sp

    burnup = []
    if not sprints:
        return burnup

    has_backlog = any(
        d.get(BACKLOG_KEY) for d in (added_us_per_sprint, done_us_per_sprint)
    )
    sprints_for_burnup = sprints
    if has_backlog:
        # "Sprint 0" porte le cumul de tout ce qui précède le 1er sprint
        # retenu — daté sur `sprint_start_date` (le plancher configuré) plutôt
        # que sur le début réel de ce 1er sprint, qui peut lui tomber
        # plusieurs jours/semaines plus tard (aucun sprint Jira ne démarre
        # forcément pile à la date configurée).
        sprint0 = {
            "name": "Sprint 0",
            "state": "backlog",  # exclu du calcul de vélocité (sprints "closed" uniquement)
            "startDate": None,
            "endDate": conf.get("sprint_start_date") or sprints[0]["startDate"],
        }
        sprints_for_burnup = [sprint0] + sprints

    cum_added_us = cum_done_us = 0
    cum_estimate_us_jh = cum_conso_us_jh = 0.0
    cum_added_sp = cum_done_sp = 0.0
    for sp_meta in sprints_for_burnup:
        name = sp_meta["name"]
        key = BACKLOG_KEY if name == "Sprint 0" else name
        num_match = re.search(r"(\d+)\s*$", name or "")
        added_us = added_us_per_sprint.get(key, 0)
        done_us = done_us_per_sprint.get(key, 0)
        estimate_us_jh = round(estimate_us_per_sprint.get(key, 0.0), 1)
        conso_us_jh = round(conso_us_per_sprint.get(key, 0.0), 1)
        added_sp = round(added_sp_per_sprint.get(key, 0.0), 1)
        done_sp = round(done_sp_per_sprint.get(key, 0.0), 1)
        cum_added_us += added_us
        cum_done_us += done_us
        cum_estimate_us_jh += estimate_us_jh
        cum_conso_us_jh += conso_us_jh
        cum_added_sp += added_sp
        cum_done_sp += done_sp
        burnup.append({
            "sprint": name,
            "num": int(num_match.group(1)) if num_match else None,
            "start": sp_meta["startDate"],
            "end": sp_meta["endDate"],
            "state": sp_meta["state"],
            "done_us": done_us,
            "done_cumul_us": cum_done_us,
            "added_us": added_us,
            "scope_cumul_us": cum_added_us,
            "estimate_us_jh": estimate_us_jh,
            "scope_cumul_us_jh": round(cum_estimate_us_jh, 1),
            "conso_us_jh": conso_us_jh,
            "conso_cumul_us_jh": round(cum_conso_us_jh, 1),
            "added_sp": added_sp,
            "scope_cumul_sp": round(cum_added_sp, 1),
            "done_sp": done_sp,
            "done_cumul_sp": round(cum_done_sp, 1),
        })
    return burnup


def _build_burnup_release(burnup, sprint_duration_days):
    """Burnup release en US : périmètre cumulé vs terminé cumulé (comptage US),
    plus 3 courbes de tendance (pessimiste/médiane/optimiste) projetées depuis
    la fin du sprint en cours jusqu'à ce que le périmètre actuel (US ajoutées
    à date) soit atteint, à partir de la vélocité US des sprints clos."""
    if not burnup:
        return None

    # Sprint "en cours" = le dernier sprint déjà démarré (actif ou clos,
    # backlog inclus) — on exclut les sprints "future" déjà planifiés dans
    # Jira mais pas encore commencés : la projection les remplace par ses
    # propres échéances (sprint_duration_days), pas par les dates Jira.
    started = [b for b in burnup if b["state"] != "future"]
    anchor = started[-1] if started else burnup[-1]
    anchor_pos = next(i for i, b in enumerate(burnup) if b["sprint"] == anchor["sprint"])
    real_burnup = burnup[: anchor_pos + 1]

    categories = [sprint_label(b["num"], b["end"]) for b in real_burnup]
    category_dates = [b["end"] for b in real_burnup]
    scope_vals = [b["scope_cumul_us"] for b in real_burnup]
    done_vals = [b["done_cumul_us"] for b in real_burnup]
    scope_sp_vals = [b["scope_cumul_sp"] for b in real_burnup]
    done_sp_vals = [b["done_cumul_sp"] for b in real_burnup]

    start_done = anchor["done_cumul_us"]
    target = anchor["scope_cumul_us"]
    remaining = target - start_done

    # Vélocité US : sprints clos, en écartant les 0 (un sprint sans aucune US
    # terminée ne reflète pas une vraie capacité — il fausserait le
    # pessimiste/médian vers le bas).
    velocities = sorted(
        v for v in (b["done_us"] for b in burnup if b["state"] == "closed") if v > 0
    )

    result = {
        "categories": categories,
        "category_dates": category_dates,
        "scope_cumul_us": scope_vals,
        "done_cumul_us": done_vals,
        "scope_cumul_sp": scope_sp_vals,
        "done_cumul_sp": done_sp_vals,
        "anchor_index": anchor_pos,
        "trend_pessimist": None,
        "trend_median": None,
        "trend_optimist": None,
    }
    if len(velocities) < 3 or remaining <= 0:
        return result

    v_pess = percentile(velocities, 0.15)
    v_med = round(statistics.median(velocities), 1)
    v_opt = percentile(velocities, 0.85)

    # Dates projetées : durée calendaire configurée (sprint_duration_days),
    # appliquée depuis la fin du sprint en cours.
    last_end = parse_dt(anchor["end"]) or _datetime.now(timezone.utc)
    last_num = anchor["num"] or 0

    def horizon(v):
        return FORECAST_MAX_HORIZON if v <= 0 else min(math.ceil(remaining / v), FORECAST_MAX_HORIZON)

    n_max = max(horizon(v_pess), horizon(v_med), horizon(v_opt))

    future_categories, future_dates = [], []
    for i in range(1, n_max + 1):
        proj_end = last_end + timedelta(days=sprint_duration_days * i)
        proj_end_iso = proj_end.isoformat()
        future_categories.append(sprint_label(last_num + i, proj_end_iso))
        future_dates.append(proj_end_iso)

    def trend_series(v):
        vals = [None] * (len(real_burnup) - 1) + [start_done]
        for i in range(1, n_max + 1):
            vals.append(min(round(start_done + v * i), target))
        return vals

    result["categories"] = categories + future_categories
    result["category_dates"] = category_dates + future_dates
    result["scope_cumul_us"] = scope_vals + [target] * n_max
    result["done_cumul_us"] = done_vals + [None] * n_max
    result["scope_cumul_sp"] = scope_sp_vals + [anchor["scope_cumul_sp"]] * n_max
    result["done_cumul_sp"] = done_sp_vals + [None] * n_max
    result["trend_pessimist"] = trend_series(v_pess)
    result["trend_median"] = trend_series(v_med)
    result["trend_optimist"] = trend_series(v_opt)
    result["velocity_us"] = {"pessimist": v_pess, "median": v_med, "optimist": v_opt}
    return result


def compute(issues, sprints, conf):
    burnup = _build_rollup(issues, sprints, conf)
    return {
        "burnup": burnup,
        "burnup_release": _build_burnup_release(burnup, conf["sprint_duration_days"]),
    }
