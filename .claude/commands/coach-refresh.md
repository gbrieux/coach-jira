---
description: Rafraîchit les données JIRA d'un projet et réécrit la synthèse coach à partir des données fraîches, sans régénérer le PPT
argument-hint: <project_key>
---

Racine effective : `skills/jira-report/`. `projects/`, `contexte/`, `templates/`
et `.env` ci-dessous sont dans le répertoire de données, pas dans ce dossier —
voir `SKILL.md`.

0. **Répertoire de données absent ?** Si `scripts/fetch_jira.py`/`resolve_context.py`
   échouent avec `DataDirNotConfigured` (aucun répertoire de données configuré) :
   demander à l'utilisateur où le créer (ex. un dossier sibling du skill dans son
   espace de travail — jamais deviné), lancer une seule fois
   `python scripts/bootstrap.py <chemin_choisi>`, puis reprendre à l'étape 1.
   Voir `SKILL.md`, section « Première utilisation ».

1. **Données JIRA.**
   ```bash
   python scripts/fetch_jira.py $1
   ```
   (ou `python scripts/fetch_jira.py --all` si `$1` est absent ou vaut `--all`.)

2. **Résoudre le contexte.**
   ```bash
   python scripts/resolve_context.py $1
   ```
   Si la commande échoue (team_id absent de `projects/$1/project.yaml`, ou fichier
   `contexte/<team_id>.md` / `contexte/organisation.md` introuvable) : afficher
   l'erreur telle quelle à l'utilisateur et **s'arrêter là** — les données JIRA
   restent rafraîchies, mais pas de synthèse écrite sans contexte résolu.

   Si `$1` vaut `--all` ou est absent (refresh multi-projets), répéter les étapes
   2 et 3 pour chaque projet de `projects/`.

3. **Synthèse coach.** Rédiger le contenu de la clé `coaching` (objet structuré) en
   suivant `COACH_PROMPT.md`, à partir des données JIRA qui viennent d'être
   rafraîchies **et** du contexte résolu à l'étape 2 (`organisation.md` +
   `contexte/<team_id>.md`). Montrer un résumé de ce qui va être écrit n'est pas
   nécessaire ici (contrairement à un ajout dans `contexte/`) — mais si la
   rédaction fait ressortir un fait qui mériterait d'être conservé dans le
   contexte équipe, suivre la section « Proposer un ajout de contexte » de
   `COACH_PROMPT.md` (proposer, attendre confirmation, jamais écrire en
   silence). Écrire la synthèse avec :
   ```bash
   python scripts/set_coaching.py $1 <coaching_utf8.json>
   ```

Ne pas lancer `build_ppt.py` — cette commande rafraîchit `projects/$1/output/data.json`
(données + synthèse), rien d'autre. Pour générer le PPT à partir de ce JSON déjà
enrichi, utiliser `/coach-ppt $1`.
