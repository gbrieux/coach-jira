#!/usr/bin/env python3
"""Extrait les données JIRA et calcule toutes les séries d'indicateurs.

Usage:
    python scripts/fetch_jira.py <clé>
    python scripts/fetch_jira.py --all

Écrit projects/<clé>/output/data.json dans le répertoire de données (voir
scripts/workspace.py). Le calcul de chaque indicateur (burnup, burndown,
vélocité, cycle time, statuts, types...) vit dans indicators/ — un module par
indicateur, voir indicators/__init__.py.

Deux sources JIRA :
  - Search API v3 (/rest/api/3/search/jql) : les tickets du JQL
  - Agile API v1 (/rest/agile/1.0/board/{id}/sprint) : dates + état des sprints
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import timezone
from datetime import datetime as _datetime

import requests
from dotenv import load_dotenv

import indicators
from indicators.common import parse_dt, to_float
from workspace import data_root, output_dir, list_project_keys, load_project_config, DataDirNotConfigured


def die(msg):
    print(f"ERREUR: {msg}", file=sys.stderr)
    sys.exit(1)


try:
    DATA_ROOT = data_root()
except DataDirNotConfigured as e:
    die(str(e))

load_dotenv(DATA_ROOT / ".env")

BASE_URL = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
EMAIL = os.environ.get("JIRA_EMAIL", "")
TOKEN = os.environ.get("JIRA_API_TOKEN", "")

# 1 jour-homme = 8h = 28800 s (paramétrable par projet via seconds_per_day)
DEFAULTS = {
    "sprint_field": "customfield_10020",
    "story_points_field": "customfield_10016",
    "seconds_per_day": 28800,
    "done_statuses": ["Done", "Terminé", "Terminé(e)", "Closed", "Resolved", "Fermé(e)"],
    "us_types": ["User Story", "Story"],   # types comptés comme US pour vélocité/cycle time
    "anomaly_types": [],                    # types comptés comme "anomalie" pour {{chart:conso_corrective}}
    "incident_types": [],                   # types comptés comme "incident" pour {{chart:conso_corrective}}
    "tech_types": [],                       # types comptés comme "US tech" pour {{chart:conso_corrective}}
                                             # (US techniques hors us_types, ex. Technical Story)
    "board_id": None,                       # requis pour dates/état des sprints
    "sprint_start_date": None,              # YYYY-MM-DD ; filtre les sprints plus anciens
    "sprint_duration_days": 21,             # durée calendaire d'un sprint, pour la projection burnup
    "workflow": [],                         # statuts JIRA ordonnés (bac à sable -> terminé) ;
                                             # {{chart:status}} suit cet ordre. Vide = tri par
                                             # fréquence (comportement historique), voir status_flow.py
    "cfd": {},                              # config optionnelle de {{chart:cumulative_flow_diagram}} :
                                             # `groups` (regroupe des statuts de `workflow` en une
                                             # bande, lisibilité), `start_date`/`end_date` (bornes
                                             # affichées) — voir indicators/cumulative_flow_diagram.py
}


def session():
    if not (BASE_URL and EMAIL and TOKEN):
        die("Identifiants JIRA absents (.env). Renseigner JIRA_BASE_URL/EMAIL/API_TOKEN.")
    s = requests.Session()
    s.auth = (EMAIL, TOKEN)
    s.headers.update({"Accept": "application/json"})
    return s


# ---------------------------------------------------------------- Search API
def search_all(s, jql, fields, expand=None):
    """`expand` : chaîne délimitée par des virgules (ex. "changelog") —
    contrairement à `fields`, cette API rejette une liste JSON (400 Invalid
    request payload) sur ce endpoint (`/search/jql`, contrairement à l'ancien
    `/search`)."""
    url = f"{BASE_URL}/rest/api/3/search/jql"
    issues, token = [], None
    while True:
        payload = {"jql": jql, "fields": fields, "maxResults": 100}
        if expand:
            payload["expand"] = ",".join(expand) if isinstance(expand, (list, tuple)) else expand
        if token:
            payload["nextPageToken"] = token
        r = s.post(url, json=payload)
        if r.status_code == 400:
            die(f"JQL rejeté (400): {r.text[:300]}")
        if r.status_code in (401, 403):
            die(f"Auth refusée ({r.status_code}). Vérifier token/droits.")
        r.raise_for_status()
        data = r.json()
        issues.extend(data.get("issues", []))
        token = data.get("nextPageToken")
        if not token or data.get("isLast", False):
            break
    return issues


def fetch_full_changelog(s, issue_key):
    """Changelog complet d'un ticket, paginé via l'endpoint dédié. Nécessaire
    pour les tickets où `expand=changelog` sur /search/jql a été tronqué à une
    seule page (~40 entrées observées, quel que soit `maxResults` demandé côté
    recherche) — un ticket très remanié en perdrait les transitions les plus
    anciennes, faussant le statut initial reconstruit par
    indicators/cumulative_flow_diagram.py. Retourne une liste de
    {"created": ..., "items": [...]}, même forme que `changelog.histories`
    du search, pour que le consommateur n'ait pas à distinguer les deux
    sources."""
    url = f"{BASE_URL}/rest/api/3/issue/{issue_key}/changelog"
    out, start = [], 0
    while True:
        r = s.get(url, params={"startAt": start, "maxResults": 100})
        r.raise_for_status()
        data = r.json()
        values = data.get("values", [])
        out.extend({"created": v.get("created"), "items": v.get("items", [])} for v in values)
        if data.get("isLast", True) or not values:
            break
        start += len(values)
    return out


def complete_truncated_changelogs(s, issues):
    """Remplace `changelog.histories` par l'historique complet (voir
    fetch_full_changelog) pour chaque ticket dont la page renvoyée par
    /search/jql ne couvrait pas `changelog.total`. Mute `issues` en place."""
    truncated = [
        it for it in issues
        if (it.get("changelog") or {}).get("total", 0) > len((it.get("changelog") or {}).get("histories", []))
    ]
    if truncated:
        print(f"  historique tronqué sur {len(truncated)} ticket(s), récupération complète...")
    for it in truncated:
        it["changelog"]["histories"] = fetch_full_changelog(s, it["key"])


# ---------------------------------------------------------------- Agile API
def parse_sprint_start_date(value):
    """Valide la date de début configurée et la normalise en UTC."""
    if not value:
        return None
    parsed = parse_dt(value)
    if parsed is None:
        die("sprint_start_date invalide. Format attendu : YYYY-MM-DD.")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def fetch_sprints(s, board_id, sprint_start_date=None):
    """Liste les sprints datés d'un board à partir de la date configurée."""
    if not board_id:
        return []
    min_start = parse_sprint_start_date(sprint_start_date)
    url = f"{BASE_URL}/rest/agile/1.0/board/{board_id}/sprint"
    out, start = [], 0
    while True:
        r = s.get(url, params={"startAt": start, "maxResults": 50})
        if r.status_code in (401, 403):
            die(f"Auth refusée sur l'Agile API ({r.status_code}). Board {board_id} accessible ?")
        if r.status_code == 404:
            die(f"Board {board_id} introuvable (404). Vérifier board_id dans project.yaml.")
        r.raise_for_status()
        data = r.json()
        for sp in data.get("values", []):
            start_date = parse_dt(sp.get("startDate"))
            # Un sprint non daté ne peut pas être positionné dans les indicateurs.
            if start_date is None:
                continue
            if start_date.tzinfo is None:
                start_date = start_date.replace(tzinfo=timezone.utc)
            if min_start and start_date.astimezone(timezone.utc) < min_start:
                continue
            out.append({
                "id": sp["id"],
                "name": sp["name"],
                "state": sp.get("state"),              # future | active | closed
                "startDate": sp.get("startDate"),
                "endDate": sp.get("endDate"),
                "completeDate": sp.get("completeDate"),
            })
        if data.get("isLast", True):
            break
        start += len(data.get("values", []))
    out.sort(key=lambda x: x["startDate"])
    return out


def build_epics(issues, conf):
    """Avancement par EPIC : rattachement via le champ `parent`. Estim./Conso
    (jh) agrègent TOUS les types de tickets rattachés à l'EPIC ; l'avancement
    (US terminées / US totales) ne compte que les User Story rattachées.

    Reste ici plutôt que dans indicators/ : alimente {{liste_epics}}, une
    table de rapport comme {{liste_sprints}}, pas un graphique par indicateur."""
    us_types = set(conf["us_types"])
    done_statuses = set(conf["done_statuses"])
    spd = conf["seconds_per_day"]

    epics_meta = {}
    for it in issues:
        f = it["fields"]
        if (f.get("issuetype") or {}).get("name") == "Epic":
            epics_meta[it["key"]] = {
                "key": it["key"],
                "name": f.get("summary", ""),
                "status": (f.get("status") or {}).get("name", "Inconnu"),
            }

    rollup = defaultdict(lambda: {"estimate_jh": 0.0, "conso_jh": 0.0, "us_done": 0, "us_total": 0})
    for it in issues:
        f = it["fields"]
        itype = (f.get("issuetype") or {}).get("name", "")
        if itype == "Epic":
            continue
        parent = f.get("parent")
        epic_key = parent.get("key") if parent else None
        if epic_key not in epics_meta:
            continue
        r = rollup[epic_key]
        r["estimate_jh"] += to_float(f.get("timeoriginalestimate")) / spd
        r["conso_jh"] += to_float(f.get("timespent")) / spd
        if itype in us_types:
            r["us_total"] += 1
            if (f.get("status") or {}).get("name") in done_statuses:
                r["us_done"] += 1

    items = []
    for key, meta in epics_meta.items():
        r = rollup.get(key, {"estimate_jh": 0.0, "conso_jh": 0.0, "us_done": 0, "us_total": 0})
        estimate_jh = round(r["estimate_jh"], 1)
        conso_jh = round(r["conso_jh"], 1)
        us_done, us_total = r["us_done"], r["us_total"]
        items.append({
            "key": key,
            "name": meta["name"],
            "status": meta["status"],
            "estimate_jh": estimate_jh,
            "conso_jh": conso_jh,
            "raf_theo_jh": round(estimate_jh - conso_jh, 1),
            "us_done": us_done,
            "us_remaining": us_total - us_done,
            "us_total": us_total,
            "avancement_pct": round(100 * us_done / us_total, 1) if us_total else 0.0,
            "started": conso_jh > 0,
        })
    items.sort(key=lambda e: -e["conso_jh"])

    total_estimate = round(sum(e["estimate_jh"] for e in items), 1)
    total_conso = round(sum(e["conso_jh"] for e in items), 1)
    us_done_total = sum(e["us_done"] for e in items)
    us_total_total = sum(e["us_total"] for e in items)
    avancement_frac = us_done_total / us_total_total if us_total_total else 0.0
    projection_jh = round(total_conso / avancement_frac, 1) if avancement_frac else None
    previsibilite_pct = (
        round(100 * (projection_jh - total_estimate) / total_estimate, 1)
        if projection_jh is not None and total_estimate else None
    )

    return {
        "items": items,
        "total_estimate_jh": total_estimate,
        "total_conso_jh": total_conso,
        "total_raf_theo_jh": round(total_estimate - total_conso, 1),
        "avancement_pct": round(avancement_frac * 100, 1),
        "us_done_total": us_done_total,
        "us_total": us_total_total,
        "projection_theorique_jh": projection_jh,
        "previsibilite_pct": previsibilite_pct,
        "not_started_count": sum(1 for e in items if not e["started"]),
    }


# ---------------------------------------------------------------- metrics
def build_metrics(issues, sprints, conf):
    """Assemble les métriques de base (comptages globaux, épics, tableau des
    sprints) et délègue le reste à indicators/ — un compute(issues, sprints,
    conf) par module, fusionné ici. Ajouter un indicateur : voir
    indicators/__init__.py, aucune modification requise dans ce fichier."""
    metrics = {
        "total_issues": len(issues),
        "total_story_points": round(
            sum(to_float(it["fields"].get(conf["story_points_field"])) for it in issues), 1
        ),
        "sprints": sprints,
    }

    for module in indicators.all_modules():
        compute = getattr(module, "compute", None)
        if compute:
            metrics.update(compute(issues, sprints, conf))

    # {{liste_sprints}} réutilise le rollup calculé par indicators/burnup.py.
    metrics["sprint_table"] = metrics.get("burnup", [])
    metrics["epics"] = build_epics(issues, conf)
    return metrics


def process(key, conf, s):
    conf = {**DEFAULTS, **conf}
    if "jql" not in conf:
        die(f"Projet {key}: aucun JQL dans project.yaml.")
    print(f"[{key}] JQL: {conf['jql']}")
    fields = [
        "summary", "status", "issuetype", "created", "resolutiondate",
        "timespent", "timeoriginalestimate", "fixVersions", "components",
        "parent", conf["story_points_field"], conf["sprint_field"],
    ]
    # expand=changelog : historique des statuts, consommé par
    # indicators/cumulative_flow_diagram.py — pas persisté dans data.json
    # (seules les métriques calculées le sont), donc pas de coût de stockage.
    # /search/jql tronque cet historique à une seule page par ticket (~40
    # entrées observées) ; complete_truncated_changelogs récupère le reste
    # pour les tickets très remaniés (appel dédié par ticket, un peu de temps
    # en plus mais indispensable — sinon le statut reconstruit peut diverger
    # du statut réel du ticket).
    issues = search_all(s, conf["jql"], fields, expand=["changelog"])
    print(f"[{key}] {len(issues)} tickets récupérés")
    complete_truncated_changelogs(s, issues)

    sprints = fetch_sprints(s, conf.get("board_id"), conf.get("sprint_start_date"))
    if sprints:
        print(f"[{key}] {len(sprints)} sprints (board {conf['board_id']})")
    elif conf.get("board_id"):
        print(f"[{key}] aucun sprint daté ne respecte sprint_start_date")
    else:
        print(f"[{key}] pas de board_id -> burnup/vélocité sans dates de sprint")

    metrics = build_metrics(issues, sprints, conf)
    out = {
        "project_key": key,
        "project_name": conf.get("name", key),
        "generated_at": _datetime.now(timezone.utc).isoformat(),
        "jql": conf["jql"],
        "metrics": metrics,
    }
    p = output_dir(key) / "data.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{key}] écrit {p}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project_key", nargs="?")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    s = session()
    if args.all:
        keys = list_project_keys()
        if not keys:
            die("Aucun projet dans projects/. Voir skills/jira-report/scaffold/project.example.yaml.")
        for k in keys:
            process(k, load_project_config(k), s)
    elif args.project_key:
        try:
            conf = load_project_config(args.project_key)
        except FileNotFoundError as e:
            die(str(e))
        process(args.project_key, conf, s)
    else:
        die("Préciser une clé projet ou --all.")


if __name__ == "__main__":
    main()
