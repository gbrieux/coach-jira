"""Répartition par statut — {{chart:status}}, dans l'ordre du workflow JIRA
configuré (project.yaml, champ `workflow`) plutôt que par fréquence."""
from collections import defaultdict

import render_agile

RENDERERS = {"status": render_agile.render_status}


def _ordered(counts, workflow):
    """Ordonne `counts` (statut -> nb) selon `workflow` (liste ordonnée,
    bac à sable -> terminé). Les statuts présents dans les données mais
    absents de `workflow` sont ajoutés à la fin (fréquence décroissante) —
    signal que `project.yaml` a besoin d'être complété plutôt qu'un statut
    silencieusement perdu. `workflow` vide = tri par fréquence (comportement
    historique)."""
    if not workflow:
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))
    ordered = {name: counts[name] for name in workflow if name in counts}
    leftover = sorted((kv for kv in counts.items() if kv[0] not in workflow),
                       key=lambda kv: -kv[1])
    ordered.update(leftover)
    return ordered


def compute(issues, sprints, conf):
    us_types = set(conf["us_types"])
    workflow = conf.get("workflow") or []
    status_counts = defaultdict(int)      # tous types
    status_counts_us = defaultdict(int)   # US uniquement (chart:status)

    for it in issues:
        f = it["fields"]
        status = (f.get("status") or {}).get("name", "Inconnu")
        itype = (f.get("issuetype") or {}).get("name", "Inconnu")
        status_counts[status] += 1
        if itype in us_types:
            status_counts_us[status] += 1

    done_statuses = set(conf["done_statuses"])
    return {
        "status_counts": _ordered(dict(status_counts), workflow),
        "status_counts_us": _ordered(dict(status_counts_us), workflow),
        # Statuts "terminé" (done_statuses, project.yaml) réellement présents
        # dans le périmètre US — pour que render_status colore ces bandes en
        # vert sans deviner (pas de heuristique sur le libellé, contrairement
        # à "attente").
        "done_statuses_us": sorted(s for s in status_counts_us if s in done_statuses),
    }
