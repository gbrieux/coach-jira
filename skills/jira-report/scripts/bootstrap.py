#!/usr/bin/env python3
"""Crée le répertoire de données à l'emplacement choisi (première utilisation).

Usage:
    python scripts/bootstrap.py <chemin>

Ne jamais deviner le chemin : c'est à l'agent de le demander explicitement à
l'utilisateur (voir SKILL.md, section « Première utilisation ») avant
d'appeler ce script. Idempotent — refuse d'écraser un répertoire de données
déjà configuré (voir workspace.bootstrap).
"""
import argparse
import sys

from workspace import bootstrap


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", help="Chemin où créer le répertoire de données (ex. répertoire "
                                  "sibling du skill dans l'espace de travail)")
    args = ap.parse_args()
    try:
        root = bootstrap(args.path)
    except RuntimeError as e:
        print(f"ERREUR: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Répertoire de données créé : {root}")
    print("  - contexte/organisation.md (squelette vide, à compléter)")
    print("  - templates/template.pptx (neutre, à remplacer par votre charte)")
    print("  - .env (à compléter : JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN)")
    print("  - projects/ (vide — voir scaffold/project.example.yaml pour ajouter un projet)")


if __name__ == "__main__":
    main()
