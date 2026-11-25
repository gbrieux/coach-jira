"""Valeurs par défaut de project.yaml — source unique.

Importé par fetch_jira.py (fusion `{**DEFAULTS, **conf}`), par les modules
indicateurs (défauts des sous-clés optionnelles) et par tests/fixtures.py
(DEFAULT_CONF) : ne jamais recopier ces valeurs ailleurs. Un nouveau champ
project.yaml s'ajoute ici + dans scaffold/project.example.yaml (doc).

Module pur (aucun import du répertoire de données, de .env ni de
fetch_jira.py) — exclu de la découverte automatique (voir
indicators/__init__.py).
"""

# Champs JIRA Cloud standard (surchargeables par projet).
SPRINT_FIELD = "customfield_10020"
STORY_POINTS_FIELD = "customfield_10016"

# Défauts des sous-clés optionnelles (blocs `dispersion_etapes`/`debit_etapes`
# de project.yaml) — lus par plusieurs indicateurs, voir min_transition_seconds().
MIN_TRANSITION_SECONDS = 300   # 5 min : bruit d'automatisation JIRA en dessous
DEBIT_WINDOW_SPRINTS = 3

# 1 jour-homme = 8h = 28800 s (paramétrable par projet via seconds_per_day)
DEFAULTS = {
    "sprint_field": SPRINT_FIELD,
    "story_points_field": STORY_POINTS_FIELD,
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
                                             # `min_transition_seconds` (défaut MIN_TRANSITION_SECONDS)
                                             # — durée plancher sous laquelle un intervalle clos est
                                             # ignoré (bruit d'automatisation JIRA : transitions à la
                                             # création en quelques secondes, pas un vrai temps passé)
                                             # — voir indicators/dispersion_etapes.py
    "debit_etapes": {},                     # config optionnelle de {{chart:debit_etapes}} :
                                             # `window_sprints` (défaut DEBIT_WINDOW_SPRINTS) — nombre
                                             # de derniers sprints clos mesurés — voir
                                             # indicators/debit_etapes.py
    "ticket_filter": {},                    # {<placeholder>: [types JIRA]} par indicateur, filtre
                                             # en mémoire ; clé absente = filtre historique de
                                             # l'indicateur (us_types ou tous), liste vide = tous
                                             # les tickets — voir indicators/common.py:ticket_types
}


def min_transition_seconds(conf):
    """Plancher de durée d'un passage dans un statut, partagé par
    dispersion_etapes / temps_par_etape / debit_etapes (clé
    `dispersion_etapes.min_transition_seconds` de project.yaml)."""
    return (conf.get("dispersion_etapes") or {}).get("min_transition_seconds", MIN_TRANSITION_SECONDS)
