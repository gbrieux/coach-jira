"""Helpers transverses aux scripts CLI du skill — aucune dépendance vers le
répertoire de données ni vers python-pptx, importable partout (scripts,
tests)."""
import re
import sys

# Tout placeholder de template `{{...}}` (texte, coach, chart) — utilisé par
# build_ppt.py (remplacement + QA), inspect_template.py et qa_placeholders.py.
PLACEHOLDER_RE = re.compile(r"\{\{[^}]+\}\}")
# `{{chart:<nom>}}` seul — <nom> = clé de RENDERERS d'un module indicators/.
CHART_PLACEHOLDER_RE = re.compile(r"\{\{chart:(\w+)\}\}")


def die(msg):
    """Message d'erreur sur stderr puis sortie 1 — convention commune des
    scripts CLI du skill."""
    print(f"ERREUR: {msg}", file=sys.stderr)
    sys.exit(1)
