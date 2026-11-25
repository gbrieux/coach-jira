"""Où passe le temps, étape par étape — {{chart:temps_par_etape}}. Une seule
mesure : la **médiane** du temps passé (jours) par statut du `workflow`
configuré, cumulée dans l'ordre du workflow pour reconstituer un « parcours
type » de la création à la livraison.

Complémentaire de {{chart:dispersion_etapes}} (même mesure de base, mêmes
règles — intervalles **clos** uniquement, seuil de bruit
`min_transition_seconds`, calcul délégué à indicators.common.status_durations,
statuts "terminé" (`done_statuses`) toujours exclus) mais agrégée
différemment : une seule valeur (la médiane) par statut plutôt que les 5
percentiles, additionnée dans l'ordre du workflow plutôt qu'affichée en
boîte à moustaches. Les deux lisent le même signal sous deux angles : la
dispersion (où est-ce instable ?) et le parcours cumulé (où le temps
s'accumule-t-il ?).

Les médianes ne sont **pas strictement additives** (la médiane d'une somme
n'est pas la somme des médianes) — le cumul affiché décrit un parcours
*type*, pas la moyenne réelle du lead time. Rendu (render_agile.py) porte ce
rappel en pied de slide, pas seulement dans ce docstring.

Regroupement (`cfd.groups`, project.yaml si configuré, sinon un groupe par
statut) : même mapping statut -> groupe que {{chart:cumulative_flow_diagram}}
et {{chart:dispersion_etapes}} (indicators.common.status_group_map), pour la
même cohérence de couleur — jamais une palette propre à cet indicateur.

`items[].count` est un nombre de **passages mesurés**, pas de tickets
distincts (voir dispersion_etapes.py docstring — un ticket qui repasse par
un même statut plus d'une fois y contribue un échantillon par visite,
jamais fusionné) : rendu affiché « N passages mesurés », jamais « N
tickets ». `us_count` (pied de slide) est, lui, bien un nombre de tickets
distincts, mais agrégé sur tous les statuts affichés, pas par statut."""
import render_agile
from indicators.common import filter_issues, resolve_status_names, status_group_map, status_durations, percentile
from indicators.defaults import min_transition_seconds

RENDERERS = {"temps_par_etape": render_agile.render_temps_par_etape}


def compute(issues, sprints, conf):
    workflow = conf.get("workflow") or []
    if not workflow:
        return {"temps_par_etape": None}
    done_statuses = set(conf["done_statuses"])
    groups = (conf.get("cfd") or {}).get("groups")
    group_labels, name_to_group = status_group_map(workflow, groups)
    min_transition_s = min_transition_seconds(conf)

    id_to_current_name = resolve_status_names(issues)
    durations, contributors = status_durations(
        filter_issues(issues, conf, "temps_par_etape", conf["us_types"]), workflow, min_transition_s,
                                                id_to_current_name)

    items = []
    for name in workflow:
        if name in done_statuses:
            continue  # statut terminal — même exclusion que {{chart:dispersion_etapes}}
        if name not in name_to_group:
            continue  # statut absent de `cfd.groups` — ignoré, comme le CFD
        vals = sorted(durations[name])
        if not vals:
            continue
        items.append({
            "name": name,
            "median": percentile(vals, 0.50),
            "count": len(vals),
            "group_index": name_to_group[name],
        })

    if not items:
        return {"temps_par_etape": None}

    # Groupes dans l'ordre où ils apparaissent parmi les statuts affichés
    # (pas l'ordre de `cfd.groups` si celui-ci diffère de `workflow`) — c'est
    # cet ordre qui pilote la barre macro du haut.
    group_order = []
    for it in items:
        if it["group_index"] not in group_order:
            group_order.append(it["group_index"])

    total_median = round(sum(it["median"] for it in items), 1)
    groups_out = []
    for gi in group_order:
        members = [it for it in items if it["group_index"] == gi]
        s = round(sum(m["median"] for m in members), 1)
        groups_out.append({
            "group_index": gi,
            "label": group_labels[gi],
            "median_sum": s,
            "n_statuses": len(members),
            "pct": round(100 * s / total_median) if total_median else 0,
        })

    us_count = set()
    for it in items:
        us_count |= contributors[it["name"]]

    return {
        "temps_par_etape": {
            "items": items,
            "groups": groups_out,
            "group_labels": group_labels,
            "total_median": total_median,
            "us_count": len(us_count),
        }
    }
