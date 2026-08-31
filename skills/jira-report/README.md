# jira-report — Skill Claude Code / Codex

> Installation complète et convention `contexte/`/`team_id` : voir le
> [`README.md`](../../README.md) à la racine de l'espace de travail. Ce fichier
> couvre l'usage direct des scripts du skill.

Génère un PPT d'indicateurs projet (burndown, burnup, vélocité, statuts, délais)
à partir de JIRA, rempli dans un template PowerPoint annoté, enrichi d'une
synthèse coach qui croise ces données avec du contexte qualitatif équipe. Un
projet = un JQL = un PPT.

## Installation (une fois)

1. Copier ce dossier dans `skills/jira-report/` de ton espace de travail.
2. `pip install -r requirements.txt`
3. Lancer n'importe quelle commande (`/coach-refresh <clé>` par exemple) sans
   répertoire de données configuré : l'agent te demande où le créer, puis lance
   `scripts/bootstrap.py <chemin>` — voir `SKILL.md`, section « Première
   utilisation ». Ça crée `projects/`, `contexte/organisation.md` (vide),
   `templates/template.pptx` (neutre) et `.env` (à compléter).
4. Renseigner `.env` (identifiants JIRA) et ajouter un premier projet dans
   `projects/<clé>/project.yaml` (voir `scaffold/project.example.yaml`).
5. Remplacer `templates/template.pptx` (neutre par défaut) par sa propre charte
   si besoin — voir `SKILL.md`, section « Template ».

## Utilisation

```bash
python scripts/inspect_template.py          # vérifier les placeholders du template
python scripts/fetch_jira.py LMA            # extraire les données -> projects/LMA/output/data.json
python scripts/build_ppt.py LMA             # générer -> projects/LMA/output/indicateurs.pptx
# ou tout d'un coup :
python scripts/fetch_jira.py --all && python scripts/build_ppt.py --all
```

Dans Claude Code ou Codex : « génère le PPT d'indicateurs du projet LMA » suffit.
