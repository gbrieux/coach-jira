"""Cumulative Flow Diagram (US) — {{chart:cumulative_flow_diagram}}. Bandes
empilées "US ayant atteint tel statut (ou un statut suivant) à date", jour
par jour, dans l'ordre du `workflow` configuré (project.yaml).

Contrairement à {{chart:status}} (status_flow.py), pas de repli par
fréquence si `workflow` est vide : un CFD a besoin d'un vrai ordre de
progression (bac à sable -> terminé) pour que les cumuls aient un sens — un
ordre faux (ex. trié par fréquence) mélangerait des US qui n'ont pas
réellement progressé dans le même sens. Si `workflow` manque, l'indicateur
est simplement absent (`cfd: None`) plutôt que de tracer un graphique
trompeur.

Reconstruit le statut de chaque US à une date donnée à partir de l'historique
JIRA (`changelog.histories`, entrées `field == "status"` — récupéré par
fetch_jira.py via `expand=changelog`, complété si tronqué). Un statut
rencontré dans l'historique mais absent de `workflow` (une fois résolu, voir
ci-dessous) ne fait pas progresser le curseur d'étape (l'US garde sa dernière
étape connue) plutôt que de faire planter le calcul ou de fausser l'ordre.

Résolution par id de statut : `changelog.items[].toString`/`fromString` sont
le libellé du statut AU MOMENT de la transition, pas son libellé actuel — un
statut renommé depuis (ex. "To Do" -> "À faire") apparaît sous son ancien nom
dans les vieilles transitions alors que `workflow` (et `fields.status.name`)
utilisent le nom courant. Comme l'id de statut, lui, ne change pas, on
résout chaque transition vers le nom actuel observé sur les tickets qui
portent aujourd'hui ce même id, avant de la comparer à `workflow`. Un id
jamais revu en statut courant (étape transitoire par laquelle plus aucun
ticket ne stationne) reste résolu par son nom brut — best-effort, pas
d'invention de données.

Configuration optionnelle (project.yaml, bloc `cfd`), pour la lisibilité
quand `workflow` compte beaucoup de statuts :
  cfd:
    groups:            # regroupe plusieurs statuts de `workflow` en une
                        # bande — {{chart:status}} garde le détail complet,
                        # seul le CFD est affecté. Absent -> une bande par
                        # statut de `workflow` (comportement historique).
      "À faire": ["Bac à sable", "Affinage métier", "Affinage technique", "À faire"]
      "En cours": ["En cours", "Attente validation PO", "Attente livraison"]
      "Terminé": ["Terminé(e)"]
    start_date: "2026-01-01"   # bornes de dates affichées (YYYY-MM-DD).
    end_date: "2026-08-27"     # Absent -> première US créée -> aujourd'hui
                                # (comportement historique). `end_date` futur
                                # plafonné à aujourd'hui (pas d'extrapolation).
"""
import bisect
from datetime import timedelta, timezone
from datetime import datetime as _datetime

import render_agile
from indicators.common import filter_issues, parse_dt, status_timeline, resolve_status_names, status_group_map

RENDERERS = {"cumulative_flow_diagram": render_agile.render_cfd}


def _stage_labels_and_map(conf):
    """(labels, name_to_stage) pour le CFD — `cfd.groups` (project.yaml) si
    configuré, sinon une bande par statut de `workflow` dans son ordre (voir
    indicators.common.status_group_map). `(None, None)` si `workflow` est
    vide (l'appelant doit alors renoncer au CFD, voir module docstring)."""
    workflow = conf.get("workflow") or []
    groups = (conf.get("cfd") or {}).get("groups")
    labels, name_to_stage = status_group_map(workflow, groups)
    if labels is None:
        return None, None
    if groups:
        missing = [s for s in workflow if s not in name_to_stage]
        if missing:
            print(f"AVERTISSEMENT cumulative_flow_diagram: statut(s) de `workflow` absent(s) "
                  f"de `cfd.groups`, ignoré(s) dans le CFD : {', '.join(missing)}")
    return labels, name_to_stage


def _date_bounds(conf, default_start):
    """(start, end) effectifs du CFD — `cfd.start_date`/`cfd.end_date`
    (project.yaml, "YYYY-MM-DD") si configurés, sinon `default_start`
    (première US créée) -> aujourd'hui. `end_date` dans le futur est
    plafonné à aujourd'hui (pas d'extrapolation)."""
    cfd_conf = conf.get("cfd") or {}
    today = _datetime.now(timezone.utc).date()
    start_cfg = parse_dt(cfd_conf.get("start_date"))
    end_cfg = parse_dt(cfd_conf.get("end_date"))
    start = start_cfg.date() if start_cfg else default_start
    end = min(end_cfg.date(), today) if end_cfg else today
    return start, end


def compute(issues, sprints, conf):
    labels, name_to_stage = _stage_labels_and_map(conf)
    if labels is None:
        return {"cfd": None}
    n_stages = len(labels)

    # id de statut -> nom actuel, observé sur les tickets qui le portent
    # aujourd'hui (tous types, pas seulement les US : même schéma de
    # workflow). Voir module docstring.
    id_to_current_name = resolve_status_names(issues)

    stage_timelines = []  # une entrée par US : [(dt, stage_idx), ...]
    for it in filter_issues(issues, conf, "cumulative_flow_diagram", conf["us_types"]):
        points = []
        for dt, status_id, raw_name in status_timeline(it):
            name = id_to_current_name.get(status_id, raw_name)
            stage = name_to_stage.get(name)
            if stage is None or (points and stage == points[-1][1]):
                continue
            points.append((dt, stage))
        if points:
            stage_timelines.append(points)

    if not stage_timelines:
        return {"cfd": None}

    default_start = min(pts[0][0] for pts in stage_timelines).date()
    start, end = _date_bounds(conf, default_start)
    if start > end:
        print("AVERTISSEMENT cumulative_flow_diagram: cfd.start_date postérieur à "
              "cfd.end_date, indicateur ignoré.")
        return {"cfd": None}

    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    day_ends = [_datetime.combine(d, _datetime.max.time(), tzinfo=timezone.utc) for d in days]

    # reached[i][d] = nb d'US dont l'étage courant au jour d est >= i
    # (a atteint cette étape ou une suivante).
    reached = [[0] * len(days) for _ in range(n_stages)]
    for pts in stage_timelines:
        ts = [p[0] for p in pts]
        stages = [p[1] for p in pts]
        for di, day_end in enumerate(day_ends):
            idx = bisect.bisect_right(ts, day_end) - 1
            if idx < 0:
                continue
            for i in range(stages[idx] + 1):
                reached[i][di] += 1

    # À la dernière date affichée — pas forcément "aujourd'hui" si
    # `cfd.end_date` est configuré dans le passé. `todo` = bloqué à la toute
    # première étape (n'a même pas atteint la 2e) ; `in_progress` = a dépassé
    # la 1re étape mais pas encore terminé — distinction attendue par les
    # encarts du rendu (voir render_agile.render_cfd), pas seulement
    # "scope - done" qui mélangeait les deux.
    scope = reached[0][-1]
    done = reached[n_stages - 1][-1]
    if n_stages > 1:
        past_first_stage = reached[1][-1]
        todo = scope - past_first_stage
        in_progress = past_first_stage - done
    else:
        todo, in_progress = 0, 0
    return {
        "cfd": {
            "categories": [d.strftime("%d/%m") for d in days],
            "workflow": labels,
            "reached": reached,
            "totals": {"scope": scope, "todo": todo, "in_progress": in_progress, "done": done},
        }
    }
