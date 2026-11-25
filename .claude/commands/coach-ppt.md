---
description: Génère le PPT d'indicateurs enrichi (données JIRA + contexte équipe) pour un projet
argument-hint: <project_key>
---

Génère le PPT d'indicateurs pour le projet **$1**, enrichi du contexte équipe.
Racine effective de toutes les commandes ci-dessous : `skills/jira-report/`.
`projects/`, `contexte/`, `templates/` et `.env` ci-dessous sont dans le
répertoire de données, pas dans ce dossier — voir `SKILL.md`.

0. **Répertoire de données absent ?** Si un script échoue avec
   `DataDirNotConfigured` : suivre `SKILL.md`, section « Première utilisation
   (bootstrap) », puis reprendre à l'étape 1.

1. **Résoudre le contexte.**
   ```bash
   python scripts/resolve_context.py $1
   ```
   En cas d'échec (team_id absent de `projects/$1/project.yaml`, ou
   `contexte/<team_id>.md` / `contexte/organisation.md` introuvable) : afficher
   l'erreur telle quelle et **s'arrêter là** — ne pas générer de PPT sans
   contexte résolu, ne rien inventer à la place.

2. **Données JIRA.** Si `projects/$1/output/data.json` n'existe pas encore, l'extraire :
   ```bash
   python scripts/fetch_jira.py $1
   ```
   S'il existe déjà, le réutiliser tel quel (pour des données fraîches, lancer
   `/coach-refresh $1` avant cette commande — c'est aussi `/coach-refresh` qui
   écrit ou met à jour la synthèse coach).

3. **Synthèse coach (uniquement si absente).** Vérifier si `projects/$1/output/data.json`
   contient déjà une clé `coaching` (normalement écrite par `/coach-refresh $1`).
   - Présente : ne pas la réécrire, passer à l'étape 4.
   - Absente (ex. premier build sans `/coach-refresh`) : la rédiger en suivant
     `COACH_PROMPT.md`, à partir des données JIRA **et** du contexte résolu à
     l'étape 1, puis la valider et l'injecter selon `COACH_PROMPT.md`, section
     « Écriture du JSON ». Tout fait à conserver dans le contexte équipe suit
     « Proposer un ajout de contexte » du même fichier (proposer, attendre
     confirmation, jamais écrire en silence).

4. **Générer le PPT.**
   ```bash
   python scripts/build_ppt.py $1
   ```

5. **QA.** Aucun placeholder `{{...}}` ne doit subsister :
   ```bash
   python scripts/qa_placeholders.py $1
   ```
   (voir aussi la section « QA » de `SKILL.md` pour le contrôle visuel).
