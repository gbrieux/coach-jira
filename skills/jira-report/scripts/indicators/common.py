"""Helpers partagés entre modules indicateurs (et fetch_jira.py) — aucune
dépendance vers un module indicateur ni vers fetch_jira.py, pour éviter tout
import circulaire. Exclu de la découverte automatique (voir indicators/__init__.py).
"""
from datetime import datetime


def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def percentile(sorted_vals, p):
    if not sorted_vals:
        return 0
    k = (len(sorted_vals) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return round(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo), 1)


def parse_dt(val):
    if not val:
        return None
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except ValueError:
        return None


def sprint_names(raw):
    """Le champ sprint est une liste ; renvoie tous les noms (un ticket peut
    traverser plusieurs sprints — c'est ce qu'on voyait dans l'export Excel)."""
    if not raw:
        return []
    names = []
    for entry in (raw if isinstance(raw, list) else [raw]):
        if isinstance(entry, dict):
            names.append(entry.get("name"))
        elif isinstance(entry, str) and "name=" in entry:
            names.append(entry.split("name=")[1].split(",")[0])
        elif entry:
            names.append(str(entry))
    return [n for n in names if n]


def sprint_label(num, end_iso):
    """'S<num> (dd/mm)' — numéro de sprint + date de fin (dernier jour du sprint)."""
    end = parse_dt(end_iso)
    return f"S{num}" + (f" ({end.strftime('%d/%m')})" if end else "")


# Clé de bucket pour les tickets déjà créés mais jamais affectés à un sprint
# (backlog) — matérialisée en "Sprint 0" dans le burnup/tableau pour que le
# périmètre cumulé US parte du vrai chiffre dès le début, pas de 0.
BACKLOG_KEY = "__sprint0__"

# Horizon max de projection (en sprints) pour éviter une extrapolation sans fin
# si la vélocité pessimiste tombe à 0.
FORECAST_MAX_HORIZON = 30


def sprint_date_bucket(dt, sprints):
    """Sprint (par nom, triés chronologiquement) dans la fenêtre
    [startDate, endDate] duquel `dt` tombe — indépendamment du champ Sprint
    JIRA du ticket. Utilisé pour `created` (added_us) et `resolutiondate`
    (done_us). BACKLOG_KEY ("Sprint 0") si `dt` est strictement antérieur au
    début du 1er sprint, ou si la date/les sprints manquent. Une date après
    la fin du dernier sprint connu (ou dans un creux entre deux sprints) est
    rattachée au sprint en cours à ce moment-là (le dernier dont le début
    est déjà passé)."""
    if not sprints or dt is None:
        return BACKLOG_KEY
    first_start = parse_dt(sprints[0]["startDate"])
    if first_start and dt < first_start:
        return BACKLOG_KEY
    idx = 0
    for i, sp in enumerate(sprints):
        start = parse_dt(sp["startDate"])
        if start and dt < start:
            break
        idx = i
        end = parse_dt(sp["endDate"])
        if end and dt < end:
            break
    return sprints[idx]["name"]
