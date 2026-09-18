"""Dispersion par étape — {{chart:dispersion_etapes}}. Temps passé (jours) par
US dans chaque statut du `workflow` configuré (project.yaml), en boîtes à
moustaches (p10/p25/médiane/p75/p90) — une boîte large signale un processus
instable, pas seulement une durée moyenne élevée.

Comme {{chart:cumulative_flow_diagram}}, nécessite `workflow` non vide (ordre
réel de progression, pas un tri par fréquence) et reconstruit la progression
de chaque US via son changelog (indicators.common.status_timeline,
resolve_status_names — mêmes helpers, mêmes règles de résolution des statuts
renommés).

Calcul des durées par statut délégué à indicators.common.status_durations —
partagé avec {{chart:temps_par_etape}}, seul autre indicateur à mesurer le
temps passé par statut.

Seuls les intervalles **clos** (l'US a quitté le statut) comptent — un
intervalle encore ouvert (US actuellement dans ce statut) est censuré, sa
durée finale inconnue ; l'inclure biaiserait la distribution vers le bas,
comme {{chart:cycle_time}} qui ne porte que sur les éléments terminés (voir
COACH_PROMPT.md §4.5).

Un intervalle clos de moins de `min_transition_seconds` (project.yaml, bloc
`dispersion_etapes`, défaut 300s = 5 min — partagé avec
{{chart:temps_par_etape}}, même notion) est également exclu : diagnostic QA
réel (projet NOS) — certains statuts amont ("Affinage métier") avaient
jusqu'à 61 % de leurs intervalles sous la barre des 10 secondes (un ticket
"entré" et "sorti" du statut à quelques secondes d'écart, signature d'une
règle d'automatisation JIRA à la création, pas d'un vrai temps de travail),
tirant leur médiane à 0 j et masquant le signal réel. Le seuil par défaut
(5 min) a été choisi après avoir comparé plusieurs valeurs sur ce projet —
voir SKILL.md/Historique pour le détail des chiffres.

Les statuts "terminé" (`done_statuses`, project.yaml — même champ que
`{{chart:cycle_time}}`/`{{chart:cumulative_flow_diagram}}`) sont exclus de la
slide, quel que soit leur nombre d'échantillons : le temps passé dans un
statut terminal n'a pas de lecture agile utile (demande explicite). Un
ticket peut être réouvert (repasser par un statut terminé puis en ressortir,
observé en réel) — ces intervalles existent dans les données mais ne sont
simplement jamais affichés.

Oscillation dans le workflow (un ticket qui repasse par un statut déjà
quitté, ex. À faire -> En cours -> Attente validation PO -> En cours ->
Attente validation PO) : chaque **visite** est mesurée et comptée
séparément — `status_durations()` ne fusionne que deux entrées consécutives
identiques dans le changelog (un doublon), jamais un retour à un statut
visité plus tôt. `items[].count` est donc un nombre de **passages mesurés**,
pas de tickets distincts : un ticket qui visite deux fois "En cours" y
contribue deux échantillons. Le nombre de tickets distincts (toutes visites
confondues) est `us_count`, au niveau de la réponse, pas par statut — vérifié
en réel sur NOS : "En cours" comptait 297 passages pour 234 tickets
distincts (63 tickets y étaient repassés au moins une fois).

Couleur par statut : reprend la couleur de groupe qu'utiliserait
{{chart:cumulative_flow_diagram}} pour ce même statut (`cfd.groups` de
project.yaml si configuré, sinon un groupe par statut) — jamais une palette
propre à cet indicateur, pour que la lecture "à faire / en cours / terminé"
reste cohérente entre les deux slides. Voir indicators.common.status_group_map
et render_agile._cfd_palette (couleur effective, calculée au rendu à partir
du nombre de groupes)."""
import render_agile
from indicators.common import resolve_status_names, status_group_map, status_durations, percentile

RENDERERS = {"dispersion_etapes": render_agile.render_dispersion_etapes}


def compute(issues, sprints, conf):
    workflow = conf.get("workflow") or []
    if not workflow:
        return {"dispersion_etapes": None}
    us_types = set(conf["us_types"])
    done_statuses = set(conf["done_statuses"])
    groups = (conf.get("cfd") or {}).get("groups")
    group_labels, name_to_group = status_group_map(workflow, groups)
    min_transition_s = (conf.get("dispersion_etapes") or {}).get("min_transition_seconds", 300)

    id_to_current_name = resolve_status_names(issues)
    durations, contributors = status_durations(issues, us_types, workflow, min_transition_s,
                                                id_to_current_name)
    measured_us = set()
    for name in workflow:
        measured_us |= contributors[name]

    items = []
    for name in workflow:
        if name in done_statuses:
            continue  # statut terminal — aucun intérêt sur cette slide (demande explicite)
        if name not in name_to_group:
            continue  # statut absent de `cfd.groups` — ignoré, comme le CFD
        vals = sorted(durations[name])
        if not vals:
            continue
        items.append({
            "name": name,
            "count": len(vals),
            "p10": percentile(vals, 0.10),
            "p25": percentile(vals, 0.25),
            "median": percentile(vals, 0.50),
            "p75": percentile(vals, 0.75),
            "p90": percentile(vals, 0.90),
            "group_index": name_to_group[name],
        })

    if not items:
        return {"dispersion_etapes": None}

    return {
        "dispersion_etapes": {
            "items": items,
            "group_labels": group_labels,
            "us_count": len(measured_us),
        }
    }
