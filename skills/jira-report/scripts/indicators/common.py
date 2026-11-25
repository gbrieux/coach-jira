"""Helpers partagés entre modules indicateurs (et fetch_jira.py) — aucune
dépendance vers un module indicateur ni vers fetch_jira.py, pour éviter tout
import circulaire. Exclu de la découverte automatique (voir indicators/__init__.py).
"""
from datetime import datetime

# Type de ticket JIRA natif (non paramétrable, identique sur toutes les
# instances) — utilisé par fetch_jira.build_epics et cumul_estimation_conso.
EPIC_TYPE = "Epic"


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


def issue_type(issue):
    return (issue["fields"].get("issuetype") or {}).get("name", "Inconnu")


# ---------------------------------------------------- filtre par type de ticket
def ticket_types(conf, key, default=None):
    """Types de tickets JIRA retenus par l'indicateur `key` (nom du
    placeholder `{{chart:<key>}}`) : `conf["ticket_filter"][key]` s'il est
    défini (project.yaml), sinon `default` (le filtre historique de
    l'indicateur — `us_types` pour les indicateurs US, aucun pour les
    autres). Renvoie un set, ou None = tous les tickets (liste vide ou
    absente)."""
    types = (conf.get("ticket_filter") or {}).get(key, default)
    return set(types) if types else None


def filter_issues(issues, conf, key, default=None):
    """Sous-ensemble de `issues` retenu par `ticket_types(conf, key, default)`
    — filtre en mémoire, après l'unique requête JQL du projet."""
    types = ticket_types(conf, key, default)
    if types is None:
        return list(issues)
    return [it for it in issues if issue_type(it) in types]


def sprint_label(num, end_iso):
    """'S<num> (dd/mm)' — numéro de sprint + date de fin (dernier jour du sprint)."""
    end = parse_dt(end_iso)
    return f"S{num}" + (f" ({end.strftime('%d/%m')})" if end else "")


# ------------------------------------------------------- historique de statut
# Partagé par cumulative_flow_diagram.py et dispersion_etapes.py, tous deux
# reconstruisant la progression d'un ticket à partir du changelog JIRA
# (expand=changelog, voir fetch_jira.py).
def status_timeline(issue):
    """[(datetime, status_id, status_name_brut), ...] trié, un point par
    changement de statut réel (transitions consécutives vers le même
    id dédupliquées). `status_name_brut` est le libellé tel qu'enregistré au
    moment de la transition — à résoudre vers le nom actuel via l'id, voir
    resolve_status_names(). Le premier point vient du statut d'origine du
    plus ancien changement (son `from`/`fromString`), ou du statut courant si
    le ticket n'a jamais changé de statut."""
    f = issue["fields"]
    created = parse_dt(f.get("created"))
    if created is None:
        return []
    histories = (issue.get("changelog") or {}).get("histories") or []
    changes = []
    for h in histories:
        hdt = parse_dt(h.get("created"))
        if hdt is None:
            continue
        for item in h.get("items", []):
            if item.get("field") == "status":
                changes.append((hdt, item.get("from"), item.get("fromString"),
                                 item.get("to"), item.get("toString")))
    changes.sort(key=lambda c: c[0])

    current = f.get("status") or {}
    if changes:
        first_id, first_name = changes[0][1], (changes[0][2] or changes[0][4])
    else:
        first_id, first_name = current.get("id"), current.get("name")

    timeline = [(created, first_id, first_name)]
    for hdt, _from_id, _from_name, to_id, to_name in changes:
        if (to_id, to_name) != (timeline[-1][1], timeline[-1][2]):
            timeline.append((hdt, to_id, to_name))
    return timeline


def resolve_status_names(issues):
    """id de statut -> nom actuel, observé sur les tickets (tous types) qui
    le portent aujourd'hui. `status_timeline()` renvoie des libellés tels
    qu'enregistrés au moment de la transition — un statut renommé depuis (ex.
    "To Do" -> "À faire") apparaît sous son ancien nom dans les vieilles
    transitions ; comme l'id, lui, ne change pas, on résout chaque transition
    vers le nom actuel via cette table avant de la comparer à `workflow`. Un
    id jamais revu en statut courant reste résolu par son nom brut —
    best-effort, pas d'invention de données."""
    id_to_current_name = {}
    for it in issues:
        st = it["fields"].get("status") or {}
        if st.get("id"):
            id_to_current_name[st["id"]] = st.get("name")
    return id_to_current_name


def status_group_map(workflow, groups):
    """(labels, name_to_group) pour un regroupement de statuts de `workflow`
    configuré (`cfd.groups`, project.yaml, voir cumulative_flow_diagram.py) —
    un label et un index de groupe par statut. `groups` absent/vide -> repli
    une entrée par statut de `workflow`, dans son ordre (chaque statut son
    propre groupe). `workflow` vide -> `(None, None)`, rien à grouper."""
    if not workflow:
        return None, None
    if not groups:
        return list(workflow), {name: i for i, name in enumerate(workflow)}
    labels = list(groups.keys())
    name_to_group = {}
    for group_i, names in enumerate(groups.values()):
        for name in names:
            name_to_group[name] = group_i
    return labels, name_to_group


def status_durations(issues, workflow, min_transition_seconds, id_to_current_name):
    """(durations, contributors) — partagé par dispersion_etapes.py et
    temps_par_etape.py, seuls consommateurs du temps passé par statut US.

    `durations[statut]` : liste de durées (jours, float) des intervalles
    **clos** (l'US a quitté le statut) d'au moins `min_transition_seconds` —
    en dessous, l'intervalle est ignoré (bruit d'automatisation JIRA à la
    création, pas un vrai temps passé ; voir dispersion_etapes.py docstring
    pour le diagnostic qui a fixé ce seuil). Un intervalle encore ouvert (US
    actuellement dans ce statut) n'est jamais compté, sa durée finale étant
    inconnue — même logique que {{chart:cycle_time}} (COACH_PROMPT.md §4.5).

    `contributors[statut]` : clés des US ayant produit au moins un tel
    intervalle pour ce statut — un même ticket peut apparaître dans
    plusieurs statuts. À l'appelant d'agréger le sous-ensemble de statuts
    qui l'intéresse (`dispersion_etapes.us_count` prend tout `workflow`,
    `temps_par_etape.us_count` seulement les statuts affichés).

    `issues` : déjà filtrés par type par l'appelant (`filter_issues`)."""
    durations = {name: [] for name in workflow}
    contributors = {name: set() for name in workflow}
    for it in issues:
        resolved = [
            (dt, id_to_current_name.get(status_id, raw_name))
            for dt, status_id, raw_name in status_timeline(it)
        ]
        for (dt1, name1), (dt2, _name2) in zip(resolved, resolved[1:]):
            if name1 not in durations:
                continue
            seconds = (dt2 - dt1).total_seconds()
            if seconds < min_transition_seconds:
                continue
            durations[name1].append(seconds / 86400)
            contributors[name1].add(it["key"])
    return durations, contributors


# ------------------------------------------ temps de cycle depuis l'entrée en sprint
# Partagé par sprint_spread.py (encart « Temps de cycle d'un ticket ») et
# sprint_cycle_trend.py (évolution par sprint) — une seule règle de mesure.
def _first_sprint_added(issue):
    """Date de la première affectation à un sprint (changelog, champ
    « Sprint »), ou None."""
    dates = []
    for h in (issue.get("changelog") or {}).get("histories") or []:
        hdt = parse_dt(h.get("created"))
        if hdt is None:
            continue
        for item in h.get("items", []):
            if (item.get("field") or "").lower() == "sprint" and (item.get("to") or item.get("toString")):
                dates.append(hdt)
    return min(dates) if dates else None


def first_sprint(raw, sprint_starts):
    """(nom, date de début) du premier sprint de l'US — celui qui démarre le
    plus tôt. Date lue sur le champ sprint du ticket (`startDate`), à défaut
    sur la liste des sprints du board (`sprint_starts` : nom -> datetime).
    (None, None) si aucun sprint daté."""
    best = (None, None)
    for entry in (raw if isinstance(raw, list) else [raw] if raw else []):
        names = sprint_names([entry])
        if not names:
            continue
        dt = parse_dt(entry.get("startDate")) if isinstance(entry, dict) else None
        dt = dt or sprint_starts.get(names[0])
        if dt is not None and (best[1] is None or dt < best[1]):
            best = (names[0], dt)
    return best


def sprint_cycle(issue, spr_field, done_statuses, sprint_starts, id_to_current_name):
    """(nom du sprint d'entrée, jours) — délai calendaire entre l'entrée en
    sprint et le premier passage dans un statut de `done_statuses`.

    Entrée = le plus tardif de la première affectation à un sprint (à défaut
    la création, cas d'une US créée directement dans un sprint) et du début
    du premier sprint : une US ajoutée avant le démarrage commence au
    démarrage, une US ajoutée en cours de sprint à son ajout. Fin = première
    transition vers un `done_statuses`, à défaut `resolutiondate`.
    `jours` vaut None si l'une des deux dates manque ou si l'US est terminée
    avant d'entrer en sprint — exclue plutôt qu'estimée."""
    f = issue["fields"]
    sprint_name, sprint_start = first_sprint(f.get(spr_field), sprint_starts)
    added = _first_sprint_added(issue) or parse_dt(f.get("created"))
    candidates = [d for d in (added, sprint_start) if d is not None]
    done_at = None
    for dt, status_id, raw_name in status_timeline(issue)[1:]:
        if id_to_current_name.get(status_id, raw_name) in done_statuses:
            done_at = dt
            break
    done_at = done_at or parse_dt(f.get("resolutiondate"))
    if not candidates or done_at is None:
        return sprint_name, None
    days = (done_at - max(candidates)).total_seconds() / 86400
    return sprint_name, (days if days >= 0 else None)


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


# --------------------------------------------------------- Défauts (ano/inc)
# Partagé par indicators/defauts_kpi.py, defauts_tendance.py,
# defauts_delai_origine.py ({{chart:defauts_*}}) — distinct de
# conso_corrective.py::_category (4 catégories, jamais retouché, voir
# CLAUDE.md « Ajouter un indicateur »).
def defect_category(itype, conf):
    """"anomalie"/"incident"/"travaux" pour un type de ticket JIRA exact
    (anomaly_types/incident_types/work_types, project.yaml) ; None si le
    type n'est dans aucune des listes (ticket hors périmètre des
    indicateurs Défauts). "travaux" n'est utilisé que par
    defauts_delai_origine.py (defauts_kpi.py/defauts_tendance.py ignorent
    tout ce qui n'est pas anomalie/incident, par choix — voir leurs
    docstrings)."""
    if itype in conf.get("anomaly_types", []):
        return "anomalie"
    if itype in conf.get("incident_types", []):
        return "incident"
    if itype in conf.get("work_types", []):
        return "travaux"
    return None


def month_key(dt):
    return (dt.year, dt.month)


def month_range(start_key, end_key):
    """Liste de (année, mois) de `start_key` à `end_key` inclus."""
    y, m = start_key
    out = []
    while (y, m) <= end_key:
        out.append((y, m))
        m = m + 1 if m < 12 else 1
        y = y if m > 1 else y + 1
    return out


def age_bucket_labels(bounds):
    """Étiquettes des tranches d'ancienneté à partir de bornes (jours)
    triées, ex. [7, 30, 90] -> ['0-7 j', '8-30 j', '31-90 j', '+90 j']."""
    labels, prev = [], 0
    for b in bounds:
        labels.append(f"{prev}-{b} j")
        prev = b + 1
    labels.append(f"+{bounds[-1]} j")
    return labels


def age_bucket_index(days, bounds):
    """Index de la tranche (0-based, aligné sur age_bucket_labels) contenant
    `days`."""
    for i, b in enumerate(bounds):
        if days <= b:
            return i
    return len(bounds)
