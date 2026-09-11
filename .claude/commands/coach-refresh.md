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

1. **Archiver la synthèse précédente — avant tout le reste.** `fetch_jira.py`
   (étape suivante) réécrit `data.json` en entier, ce qui perdrait le `coaching`
   actuel s'il n'est pas archivé d'abord (voir COACH_PROMPT.md, étape 3, pour le
   `delta`) :
   ```bash
   python scripts/coaching_history.py archive $1
   ```
   Idempotent (ne réarchive pas un coaching identique au dernier déjà présent) et
   sans effet si `data.json` n'a pas encore de `coaching` — ne jamais sauter cette
   étape sous prétexte qu'elle semble inutile ce coup-ci.

2. **Données JIRA.**
   ```bash
   python scripts/fetch_jira.py $1
   ```
   (ou `python scripts/fetch_jira.py --all` si `$1` est absent ou vaut `--all` —
   dans ce cas, répéter l'étape 1 pour chaque projet avant cette étape.)

3. **Résoudre le contexte.**
   ```bash
   python scripts/resolve_context.py $1
   ```
   Si la commande échoue (team_id absent de `projects/$1/project.yaml`, ou fichier
   `contexte/<team_id>.md` / `contexte/organisation.md` introuvable) : afficher
   l'erreur telle quelle à l'utilisateur et **s'arrêter là** — les données JIRA
   restent rafraîchies, mais pas de synthèse écrite sans contexte résolu.

   Si `$1` vaut `--all` ou est absent (refresh multi-projets), répéter les étapes
   1 à 4 pour chaque projet de `projects/`.

4. **Synthèse coach.** Rédiger le contenu de la clé `coaching` (objet structuré) en
   suivant `COACH_PROMPT.md`, à partir des données JIRA qui viennent d'être
   rafraîchies, du contexte résolu à l'étape 3 (`organisation.md` +
   `contexte/<team_id>.md`), et de la dernière synthèse archivée pour le `delta` :
   ```bash
   python scripts/coaching_history.py last $1
   ```
   (rien s'il n'y a pas encore d'historique — dans ce cas, ne pas produire le
   champ `delta`, voir COACH_PROMPT.md). Montrer un résumé de ce qui va être écrit
   n'est pas nécessaire ici (contrairement à un ajout dans `contexte/`) — mais si
   la rédaction fait ressortir un fait qui mériterait d'être conservé dans le
   contexte équipe, suivre la section « Proposer un ajout de contexte » de
   `COACH_PROMPT.md` (proposer, attendre confirmation, jamais écrire en
   silence). Valider puis écrire la synthèse avec :
   ```bash
   python scripts/check_coaching.py <coaching_utf8.json>
   python scripts/set_coaching.py $1 <coaching_utf8.json>
   ```
   `check_coaching.py` vérifie les plafonds/cardinalités (voir COACH_PROMPT.md,
   « Contraintes de rendu ») avant d'écrire quoi que ce soit — une erreur bloquante
   veut dire raccourcir le texte, pas forcer l'injection ; `set_coaching.py`
   applique de toute façon la même validation en interne juste avant d'injecter.

Ne pas lancer `build_ppt.py` — cette commande rafraîchit `projects/$1/output/data.json`
(données + synthèse), rien d'autre. Pour générer le PPT à partir de ce JSON déjà
enrichi, utiliser `/coach-ppt $1`.
