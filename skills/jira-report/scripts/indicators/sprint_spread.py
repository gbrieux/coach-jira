"""Répartition des US par nombre de sprints — {{chart:sprint_spread}}.

Porte aussi l'encart « Temps de cycle d'un ticket » de la même slide
(`sprint_cycle_time`) : pour chaque US terminée, délai calendaire (jours)
entre son **entrée en sprint** et son **premier passage dans un statut
terminé** (`done_statuses`).

- Entrée en sprint = le plus tardif de (1) la première affectation à un
  sprint (changelog, champ « Sprint » ; à défaut la date de création, cas
  d'une US créée directement dans un sprint) et (2) la date de début du
  premier sprint de l'US — une US ajoutée avant le démarrage du sprint
  commence au démarrage, une US ajoutée en cours de sprint à son ajout.
- Fin = première transition vers un statut de `done_statuses` (par exemple
  « Attente livraison recette métier », première étape terminée côté
  sprint), à défaut `resolutiondate`.
- Toutes les US terminées comptent, y compris celles qui ont traversé
  plusieurs sprints (même périmètre que la répartition) ; une US sans date
  d'entrée ou de fin exploitable, ou terminée avant d'entrer en sprint, est
  exclue plutôt qu'estimée. Calcul partagé avec {{chart:sprint_cycle_trend}}
  (indicators.common.sprint_cycle)."""
from collections import defaultdict

import render_agile
from indicators.common import filter_issues, parse_dt, percentile, resolve_status_names, sprint_cycle, sprint_names

RENDERERS = {"sprint_spread": render_agile.render_sprint_spread}


def compute(issues, sprints, conf):
    done_statuses = set(conf["done_statuses"])
    spr_field = conf["sprint_field"]
    sprint_starts = {s["name"]: parse_dt(s.get("startDate")) for s in sprints or [] if s.get("name")}
    id_to_current_name = resolve_status_names(issues)

    counts = defaultdict(int)  # nb de sprints traversés -> nb d'US
    cycle_days = []
    for it in filter_issues(issues, conf, "sprint_spread", conf["us_types"]):
        f = it["fields"]
        status = (f.get("status") or {}).get("name", "Inconnu")
        if status not in done_statuses:
            continue
        nb_sprints = len(set(sprint_names(f.get(spr_field))))
        if nb_sprints == 0:
            continue
        counts[nb_sprints] += 1

        _sprint, days = sprint_cycle(it, spr_field, done_statuses, sprint_starts, id_to_current_name)
        if days is not None:
            cycle_days.append(days)

    cyc = sorted(cycle_days)
    workflow = conf.get("workflow") or []
    done_label = next((s for s in workflow if s in done_statuses), None)
    return {
        "sprint_spread": dict(sorted(counts.items())),
        "sprint_cycle_time": {
            "count": len(cyc),
            "p15": percentile(cyc, 0.15),
            "median": percentile(cyc, 0.50),
            "p85": percentile(cyc, 0.85),
            "done_label": done_label,
        },
    }
