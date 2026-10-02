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
from indicators.common import filter_issues, parse_dt, to_float
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

# Tempo (app JIRA de CRA/timesheet) : API séparée (api.tempo.io), token dédié
# — absent (.env) sur les instances qui n'ont pas Tempo installé, voir
# fetch_tempo_worklogs() et indicators/tempo_conso.py.
TEMPO_TOKEN = os.environ.get("TEMPO_API_TOKEN", "")
TEMPO_API_URL = "https://api.tempo.io/4/worklogs"

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
    "subtask_types": [],                    # types comptés comme "Sous-tâche" pour {{chart:conso_corrective}}
    "work_types": [],                       # types comptés comme "Travaux" pour {{chart:conso_corrective}}
                                             # ET comme "travaux" (3e catégorie) pour
                                             # {{chart:defauts_delai_origine}} — champ partagé entre les
                                             # deux indicateurs, comme anomaly_types/incident_types
    "defect_age_buckets": [1, 7, 15, 30],    # bornes (jours) des tranches d'ancienneté du backlog
                                             # ouvert sur {{chart:defauts_tendance}} — [1,7,15,30] donne
                                             # 5 tranches : 0-1j / 2-7j / 8-15j / 16-30j / +30j
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
    "dispersion_etapes": {},                # config optionnelle de {{chart:dispersion_etapes}} :
                                             # `min_transition_seconds` (défaut 300 = 5 min) — durée
                                             # plancher sous laquelle un intervalle clos est ignoré
                                             # (bruit d'automatisation JIRA : transitions à la création
                                             # en quelques secondes, pas un vrai temps passé) — voir
                                             # indicators/dispersion_etapes.py
    "ticket_filter": {},                    # {<placeholder>: [types JIRA]} par indicateur, filtre
                                             # en mémoire ; clé absente = filtre historique de
                                             # l'indicateur (us_types ou tous), liste vide = tous
                                             # les tickets — voir indicators/common.py:ticket_types
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
    """Avancement par EPIC — aligné sur {{chart:cumul_estimation_conso}} pour
    que les deux slides affichent les mêmes totaux :

      - **Estimation EPIC initiale** (jh) : `timeoriginalestimate` porté par
        le ticket Epic **lui-même** (pas le rollup de ses enfants, conservé à
        part dans `detail_estimate_jh`). Total = `total_estime_epics_jh` de
        cumul_estimation_conso.
      - **Consommé** (jh) : `timespent` des tickets non-Epic rattachés à l'EPIC
        via `parent` — directement, ou via leur ticket parent (sous-tâche ->
        US -> EPIC). Les tickets sans EPIC forment une ligne « Sans EPIC »
        (`no_epic`) : total = `total_consomme_jh` de cumul_estimation_conso.
      - **Avancement** (US terminées / US totales) : toutes les User Story du
        périmètre, y compris celles sans EPIC.

    Même population que cumul_estimation_conso (`ticket_filter` de la clé
    `cumul_estimation_conso`), pour garantir l'égalité des totaux.

    Reste ici plutôt que dans indicators/ : alimente {{liste_epics}}, une
    table de rapport comme {{liste_sprints}}, pas un graphique par indicateur."""
    us_types = set(conf["us_types"])
    done_statuses = set(conf["done_statuses"])
    spd = conf["seconds_per_day"]
    population = filter_issues(issues, conf, "cumul_estimation_conso")

    epics_meta = {}
    parent_of = {}
    for it in population:
        f = it["fields"]
        parent = f.get("parent")
        parent_of[it["key"]] = parent.get("key") if parent else None
        if (f.get("issuetype") or {}).get("name") == "Epic":
            epics_meta[it["key"]] = {
                "key": it["key"],
                "name": f.get("summary", ""),
                "status": (f.get("status") or {}).get("name", "Inconnu"),
                "estimate_jh": to_float(f.get("timeoriginalestimate")) / spd,
            }

    def epic_of(key):
        seen = set()
        cur = parent_of.get(key)
        while cur and cur not in seen:
            if cur in epics_meta:
                return cur
            seen.add(cur)
            cur = parent_of.get(cur)
        return None

    def empty():
        return {"detail_estimate_jh": 0.0, "conso_jh": 0.0, "us_done": 0, "us_total": 0, "n": 0}

    rollup = defaultdict(empty)
    no_epic = empty()
    for it in population:
        f = it["fields"]
        itype = (f.get("issuetype") or {}).get("name", "")
        if itype == "Epic":
            continue
        epic_key = epic_of(it["key"])
        r = rollup[epic_key] if epic_key else no_epic
        r["n"] += 1
        r["detail_estimate_jh"] += to_float(f.get("timeoriginalestimate")) / spd
        r["conso_jh"] += to_float(f.get("timespent")) / spd
        if itype in us_types:
            r["us_total"] += 1
            if (f.get("status") or {}).get("name") in done_statuses:
                r["us_done"] += 1

    def row(r, estimate_jh):
        estimate_jh = round(estimate_jh, 1)
        conso_jh = round(r["conso_jh"], 1)
        us_done, us_total = r["us_done"], r["us_total"]
        return {
            "estimate_jh": estimate_jh,
            "detail_estimate_jh": round(r["detail_estimate_jh"], 1),
            "conso_jh": conso_jh,
            "raf_theo_jh": round(estimate_jh - conso_jh, 1),
            "us_done": us_done,
            "us_remaining": us_total - us_done,
            "us_total": us_total,
            "avancement_pct": round(100 * us_done / us_total, 1) if us_total else 0.0,
            "started": conso_jh > 0,
        }

    items = []
    for key, meta in epics_meta.items():
        items.append({
            "key": key,
            "name": meta["name"],
            "status": meta["status"],
            **row(rollup.get(key, empty()), meta["estimate_jh"]),
        })
    items.sort(key=lambda e: -e["conso_jh"])

    no_epic_row = None
    if no_epic["n"]:
        # Pas d'estimation EPIC initiale possible : 0 par construction.
        no_epic_row = {"key": "—", "name": "Sans EPIC", "status": "—",
                       "ticket_count": no_epic["n"], **row(no_epic, 0.0)}

    all_rows = items + ([no_epic_row] if no_epic_row else [])
    # Totaux sur les valeurs brutes (pas la somme des lignes arrondies), pour
    # retomber exactement sur les totaux de cumul_estimation_conso.
    raw_rows = list(rollup.values()) + [no_epic]
    total_estimate = round(sum(meta["estimate_jh"] for meta in epics_meta.values()), 1)
    total_conso = round(sum(r["conso_jh"] for r in raw_rows), 1)
    us_done_total = sum(e["us_done"] for e in all_rows)
    us_total_total = sum(e["us_total"] for e in all_rows)
    avancement_frac = us_done_total / us_total_total if us_total_total else 0.0
    projection_jh = round(total_conso / avancement_frac, 1) if avancement_frac else None
    previsibilite_pct = (
        round(100 * (projection_jh - total_estimate) / total_estimate, 1)
        if projection_jh is not None and total_estimate else None
    )

    return {
        "items": items,
        "no_epic": no_epic_row,
        "total_estimate_jh": total_estimate,
        "total_detail_estimate_jh": round(sum(r["detail_estimate_jh"] for r in raw_rows), 1),
        "total_conso_jh": total_conso,
        "total_raf_theo_jh": round(total_estimate - total_conso, 1),
        "avancement_pct": round(avancement_frac * 100, 1),
        "us_done_total": us_done_total,
        "us_total": us_total_total,
        "projection_theorique_jh": projection_jh,
        "previsibilite_pct": previsibilite_pct,
        "not_started_count": sum(1 for e in items if not e["started"]),
    }


# ------------------------------------------------------------------ tempo
def fetch_tempo_worklogs(issue_ids, date_from, date_to):
    """Récupère les worklogs Tempo (jh, CRA) des tickets du périmètre JQL
    (`issue_ids`, ids JIRA numériques), entre `date_from`/`date_to`
    (YYYY-MM-DD). `None` si Tempo n'est pas configuré (`TEMPO_API_TOKEN`
    absent de `.env`) ou si l'appel échoue (app absente/inaccessible sur
    cette instance) — dans ce cas {{chart:tempo_conso}} / {{chart:tempo_types}}
    affichent un message plutôt qu'un graphique vide, voir
    indicators/tempo_conso.py et indicators/tempo_types.py. Chaque worklog
    porte `issue_id` (id JIRA numérique en chaîne) en plus de `date`/`seconds`
    — tempo_types.py s'en sert pour retrouver le type de ticket loggé.

    L'API Tempo Cloud (api.tempo.io) n'a pas d'endpoint « worklogs d'une
    liste d'issues » : on récupère tous les worklogs de la période (paginé
    via `metadata.next`) et on filtre côté client sur les ids du périmètre
    — raisonnable, la période est déjà bornée par `sprint_start_date`."""
    if not TEMPO_TOKEN or not issue_ids:
        return None
    wanted = {str(i) for i in issue_ids}
    headers = {"Authorization": f"Bearer {TEMPO_TOKEN}", "Accept": "application/json"}
    out = []
    url = TEMPO_API_URL
    params = {"limit": 1000, "from": date_from, "to": date_to}
    try:
        while url:
            r = requests.get(url, headers=headers, params=params, timeout=30)
            if r.status_code != 200:
                return None
            data = r.json()
            for w in data.get("results", []):
                issue_id = str((w.get("issue") or {}).get("id", ""))
                if issue_id in wanted:
                    out.append({
                        "date": w.get("startDate"),
                        "seconds": w.get("timeSpentSeconds") or 0,
                        "issue_id": issue_id,
                    })
            url = (data.get("metadata") or {}).get("next")
            params = None  # 'next' porte déjà tous les paramètres de requête
    except requests.RequestException:
        return None
    return out


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

    date_from = conf.get("sprint_start_date") or "2000-01-01"
    date_to = _datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conf["tempo_worklogs"] = fetch_tempo_worklogs([it["id"] for it in issues], date_from, date_to)
    if conf["tempo_worklogs"] is None:
        print(f"[{key}] Tempo: pas de données (token absent de .env, ou app Tempo indisponible sur ce projet)")
    else:
        print(f"[{key}] Tempo: {len(conf['tempo_worklogs'])} worklog(s) dans le périmètre")

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
