"""Un module par indicateur — ajouter un indicateur = ajouter un .py ici,
sans toucher aux autres fichiers (voir SKILL.md, section « Indicateurs »).

Chaque module peut exposer, indépendamment l'un de l'autre :
  - compute(issues, sprints, conf) -> dict
      Calcule sa part de métriques ; le dict retourné est fusionné dans
      metrics par fetch_jira.py:build_metrics(). Les clés doivent être
      propres à ce module (pas de collision avec un autre indicateur).
  - RENDERERS: dict[str, callable]
      {placeholder: render(slide, shape, data, template_path, page_num, total_pages)}
      Dispatché par build_ppt.py pour chaque {{chart:<placeholder>}} rencontré
      dans le template. Le callable dessine le graphique/tableau natif — voir
      render_agile.py pour les rendus « design agile » existants, réutilisables
      depuis un nouveau module sans les dupliquer.

common.py (préfixé `_`... non, nommé explicitement `common`, exclu de la
découverte automatique) porte les helpers partagés (parsing de date,
pourcentiles, etc.) sans dépendre d'aucun module indicateur — à importer
avec `from indicators.common import ...`.
"""
import importlib
import pkgutil

_EXCLUDED = {"common"}


def all_modules():
    """Importe et retourne tous les modules indicateurs (hors common.py),
    dans l'ordre alphabétique du nom de fichier — stable et prévisible."""
    mods = []
    for info in sorted(pkgutil.iter_modules(__path__), key=lambda i: i.name):
        if info.name in _EXCLUDED or info.name.startswith("_"):
            continue
        mods.append(importlib.import_module(f"{__name__}.{info.name}"))
    return mods
