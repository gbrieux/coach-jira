---
description: Rafraîchit les données JIRA d'un projet et réécrit la synthèse coach à partir des données fraîches, sans régénérer le PPT
argument-hint: <project_key>
---

Racine effective : `skills/jira-report/`. `projects/`, `contexte/`, `templates/`
et `.env` ci-dessous sont dans le répertoire de données, pas dans ce dossier —
voir `SKILL.md`.

**Plusieurs projets ?** Si `$1` est absent ou vaut `--all` : dérouler les étapes
1 à 4 ci-dessous **une clé à la fois**, pour chaque projet de `projects/` (en
remplaçant `$1` par la clé) — jamais `fetch_jira.py --all`, qui réécrirait
tous les `data.json` avant que leur synthèse ait été archivée.

0. **Répertoire de données absent ?** Si un script échoue avec
   `DataDirNotConfigured` : suivre `SKILL.md`, section « Première utilisation
   (bootstrap) », puis reprendre à l'étape 1.

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

3. **Résoudre le contexte.**
   ```bash
   python scripts/resolve_context.py $1
   ```
   En cas d'échec (team_id absent de `projects/$1/project.yaml`, ou
   `contexte/<team_id>.md` / `contexte/organisation.md` introuvable) : afficher
   l'erreur telle quelle et **s'arrêter là** — les données JIRA restent
   rafraîchies, mais pas de synthèse écrite sans contexte résolu.

4. **Synthèse coach.** Rédiger la clé `coaching` en suivant `COACH_PROMPT.md`, à
   partir des données JIRA fraîches, du contexte résolu à l'étape 3, et de la
   dernière synthèse archivée pour le `delta` :
   ```bash
   python scripts/coaching_history.py last $1
   ```
   (rien s'il n'y a pas encore d'historique — dans ce cas, pas de champ `delta`).
   Valider puis injecter selon `COACH_PROMPT.md`, section « Écriture du JSON »
   (`check_coaching.py` puis `set_coaching.py $1 …` — l'archivage y est déjà
   fait à l'étape 1). Montrer un résumé avant écriture n'est pas nécessaire ici ;
   en revanche tout fait à conserver dans le contexte équipe suit « Proposer un
   ajout de contexte » de `COACH_PROMPT.md` (proposer, attendre confirmation,
   jamais écrire en silence).

Ne pas lancer `build_ppt.py` — cette commande rafraîchit `projects/$1/output/data.json`
(données + synthèse), rien d'autre. Pour générer le PPT à partir de ce JSON déjà
enrichi, utiliser `/coach-ppt $1`.
