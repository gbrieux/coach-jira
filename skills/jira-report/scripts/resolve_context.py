#!/usr/bin/env python3
"""Résout le contexte qualitatif (équipe) d'un projet ou d'une équipe.

Usage:
    python scripts/resolve_context.py NOS_R1      # clé de projects/<clé>/project.yaml
    python scripts/resolve_context.py NOS         # team_id directement

Résolution : argument → clé de projet (team_id associé, lu dans
projects/<clé>/project.yaml) ; si aucune clé ne correspond, l'argument est
traité directement comme un team_id. `organisation.md` (toujours lu) et
`contexte/<team_id>.md` sont requis tous les deux — échec propre (message
clair, pas de traceback) si l'un des deux manque, pour que l'analyse soit
identique quel que soit le coach qui l'exécute.

Sortie (succès) : JSON sur stdout —
{"resolved_as": "project"|"team", "project_key": str|None, "team_id": str,
 "organisation_md": str, "team_md": str, "team_md_path": str}
"""
import argparse
import json
import sys

from workspace import data_root, list_project_keys, load_project_config, DataDirNotConfigured

# Sortie/erreurs toujours en UTF-8 quel que soit le codepage de la console
# (le contexte peut contenir des symboles absents de cp1252, ex. ≤/≥).
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def die(msg):
    print(f"ERREUR: {msg}", file=sys.stderr)
    sys.exit(1)


try:
    DATA_ROOT = data_root()
except DataDirNotConfigured as e:
    die(str(e))

CONTEXTE_DIR = DATA_ROOT / "contexte"


def resolve(arg):
    project_keys = list_project_keys()

    if arg in project_keys:
        conf = load_project_config(arg)
        team_id = conf.get("team_id")
        if not team_id:
            die(f"Projet '{arg}' n'a pas de team_id défini dans project.yaml "
                f"— impossible de résoudre le contexte équipe.")
        resolved_as, project_key = "project", arg
    else:
        team_id = arg
        resolved_as, project_key = "team", None

    team_path = CONTEXTE_DIR / f"{team_id}.md"
    if not team_path.exists():
        if resolved_as == "project":
            die(f"{team_path} introuvable pour l'équipe '{team_id}' "
                f"(résolue depuis le projet '{project_key}').")
        else:
            die(f"'{arg}' n'est ni une clé de projet connue, ni un team_id "
                f"connu ({team_path} introuvable).")

    org_path = CONTEXTE_DIR / "organisation.md"
    if not org_path.exists():
        die(f"{org_path} introuvable — ce fichier est requis "
            "(contexte transverse toujours lu, pour que l'analyse soit identique "
            "pour tous les coachs).")

    return {
        "resolved_as": resolved_as,
        "project_key": project_key,
        "team_id": team_id,
        "organisation_md": org_path.read_text(encoding="utf-8"),
        "team_md": team_path.read_text(encoding="utf-8"),
        "team_md_path": team_path.relative_to(DATA_ROOT).as_posix(),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("project_key_or_team_id")
    args = ap.parse_args()
    result = resolve(args.project_key_or_team_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
