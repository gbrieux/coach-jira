"""Débit par étape — {{chart:debit_etapes}}. Pour chaque statut du `workflow`
configuré (project.yaml), nombre d'US **entrées** et **sorties** par sprint
sur une fenêtre récente, et stock en début/fin de fenêtre — de quoi voir où
le travail s'accumule, donc où se trouve le goulot du flux.

Complémentaire de {{chart:cumulative_flow_diagram}} (même reconstruction par
changelog, mais par statut et ramenée à un débit par sprint plutôt qu'en
cumul jour par jour) et de {{chart:temps_par_etape}}/{{chart:dispersion_etapes}}
(qui mesurent une durée de séjour, pas un débit).

Fenêtre : les `debit_etapes.window_sprints` derniers sprints **clos**
(project.yaml, défaut 3), du début du premier à la clôture du dernier
(`completeDate`, sinon `endDate`) — le sprint actif, partiel, est exclu
(COACH_PROMPT.md §1.5). Sans sprint clos (pas de `board_id`), repli sur les
`window_sprints × sprint_duration_days` derniers jours. Les débits sont
divisés par `window_sprints` : un débit **par sprint**.

Mêmes règles de lecture du changelog que {{chart:dispersion_etapes}} :
statuts résolus par id (indicators.common.resolve_status_names), et une
visite de moins de `dispersion_etapes.min_transition_seconds` (défaut 300s)
ignorée — un passage de quelques secondes est une automatisation JIRA, pas
un vrai passage dans l'étape ; il gonflerait entrées et sorties à parts
égales. Deux visites du même statut que seul ce passage séparait sont
fusionnées (pas de fausse sortie/entrée). Chaque **visite** compte : un
ticket qui repasse deux fois par un statut sur la fenêtre y compte deux
entrées (« passages », comme `dispersion_etapes.items[].count`).
`retours` : parmi les entrées, celles qui viennent d'un statut **plus
avancé** dans `workflow` (ex. « Attente validation PO » -> « En cours ») —
du retravail, qui consomme la capacité de l'étape sans faire avancer le
flux.

Statuts "terminé" (`done_statuses`) exclus de `items` — ils ne se vident
jamais ; leur débit d'entrée est porté à part (`livrees`, première entrée
dans un statut terminé depuis un statut non terminé). `arrivees` : US créées
sur la fenêtre.

`accumulation` : le statut dont le stock a le plus augmenté sur la fenêtre
(`delta_stock` > 0 ; à égalité, la plus grande couverture), et
`etape_aval` le statut suivant dans `workflow` — celui qui ne vide pas cette
file assez vite, donc le goulot probable. `None` si aucun stock n'augmente.
`couverture_sprints` = stock de fin ÷ sorties par sprint : nombre de sprints
nécessaires pour vider le stock au débit observé (loi de Little)."""
from datetime import timedelta, timezone
from datetime import datetime as _datetime

import render_agile
from indicators.common import filter_issues, parse_dt, resolve_status_names, status_group_map, status_timeline

RENDERERS = {"debit_etapes": render_agile.render_debit_etapes}


def _window(sprints, conf, n):
    """(start, end, labels) de la fenêtre — voir module docstring."""
    closed = [sp for sp in sprints if sp.get("state") == "closed" and parse_dt(sp.get("startDate"))]
    if closed:
        last = closed[-n:]
        start = parse_dt(last[0]["startDate"])
        end = parse_dt(last[-1].get("completeDate")) or parse_dt(last[-1].get("endDate"))
        return start, end, [sp["name"] for sp in last]
    end = _datetime.now(timezone.utc)
    return end - timedelta(days=n * conf["sprint_duration_days"]), end, []


def _visits(issue, id_to_current_name, min_transition_s):
    """[(statut, début, fin|None), ...] — visites de moins de
    `min_transition_s` retirées, puis visites consécutives du même statut
    fusionnées (voir module docstring)."""
    resolved = [(dt, id_to_current_name.get(sid, raw)) for dt, sid, raw in status_timeline(issue)]
    visits = []
    for i, (dt, name) in enumerate(resolved):
        end = resolved[i + 1][0] if i + 1 < len(resolved) else None
        if end is not None and (end - dt).total_seconds() < min_transition_s:
            continue
        if visits and visits[-1][0] == name:
            visits[-1] = (name, visits[-1][1], end)
        else:
            if visits:
                # La visite précédente se termine là où celle-ci commence :
                # la visite courte retirée entre les deux ne crée pas de trou.
                visits[-1] = (visits[-1][0], visits[-1][1], dt)
            visits.append((name, dt, end))
    return visits


def compute(issues, sprints, conf):
    workflow = conf.get("workflow") or []
    if not workflow:
        return {"debit_etapes": None}
    done_statuses = set(conf["done_statuses"])
    groups = (conf.get("cfd") or {}).get("groups")
    group_labels, name_to_group = status_group_map(workflow, groups)
    min_transition_s = (conf.get("dispersion_etapes") or {}).get("min_transition_seconds", 300)
    n = max(int((conf.get("debit_etapes") or {}).get("window_sprints", 3)), 1)

    start, end, sprint_labels = _window(sprints, conf, n)
    if start is None or end is None or start >= end:
        return {"debit_etapes": None}

    def in_window(dt):
        return dt is not None and start <= dt < end

    def present_at(v, t):
        return v[1] <= t and (v[2] is None or v[2] > t)

    entrees = {name: 0 for name in workflow}
    sorties = {name: 0 for name in workflow}
    retours = {name: 0 for name in workflow}
    rank = {name: i for i, name in enumerate(workflow)}
    stock_debut = {name: 0 for name in workflow}
    stock_fin = {name: 0 for name in workflow}
    arrivees = livrees = 0
    contributors = set()

    id_to_current_name = resolve_status_names(issues)
    for it in filter_issues(issues, conf, "debit_etapes", conf["us_types"]):
        visits = _visits(it, id_to_current_name, min_transition_s)
        if not visits:
            continue
        if in_window(visits[0][1]):
            arrivees += 1
        for i, v in enumerate(visits):
            name = v[0]
            if name in done_statuses and in_window(v[1]) and i > 0 and visits[i - 1][0] not in done_statuses:
                livrees += 1
            if name not in entrees:
                continue
            if in_window(v[1]):
                entrees[name] += 1
                contributors.add(it["key"])
                if i > 0 and rank.get(visits[i - 1][0], -1) > rank[name]:
                    retours[name] += 1
            if in_window(v[2]):
                sorties[name] += 1
                contributors.add(it["key"])
            if present_at(v, start):
                stock_debut[name] += 1
            if present_at(v, end):
                stock_fin[name] += 1

    items = []
    for name in workflow:
        if name in done_statuses or name not in name_to_group:
            continue  # statut terminal / absent de `cfd.groups` — mêmes exclusions que dispersion_etapes
        out_rate = round(sorties[name] / n, 1)
        items.append({
            "name": name,
            "group_index": name_to_group[name],
            "entrees": entrees[name],
            "retours": retours[name],
            "sorties": sorties[name],
            "entrees_par_sprint": round(entrees[name] / n, 1),
            "sorties_par_sprint": out_rate,
            "stock_debut": stock_debut[name],
            "stock_fin": stock_fin[name],
            "delta_stock": stock_fin[name] - stock_debut[name],
            "couverture_sprints": round(stock_fin[name] / out_rate, 1) if out_rate else None,
        })

    if not items or not contributors:
        return {"debit_etapes": None}

    growing = [r for r in items if r["delta_stock"] > 0]
    accumulation = None
    if growing:
        top = max(growing, key=lambda r: (r["delta_stock"], r["couverture_sprints"] or float("inf")))
        nxt = workflow.index(top["name"]) + 1
        accumulation = {
            "name": top["name"],
            "delta_stock": top["delta_stock"],
            "etape_aval": workflow[nxt] if nxt < len(workflow) else None,
        }

    return {
        "debit_etapes": {
            "items": items,
            "group_labels": group_labels,
            "window_sprints": n,
            "sprints": sprint_labels,
            "start": start.date().isoformat(),
            "end": end.date().isoformat(),
            "arrivees": arrivees,
            "livrees": livrees,
            "arrivees_par_sprint": round(arrivees / n, 1),
            "livrees_par_sprint": round(livrees / n, 1),
            "accumulation": accumulation,
            "us_count": len(contributors),
        }
    }
