---
description: Génère le PPT d'indicateurs enrichi (données JIRA + contexte équipe) pour un projet
argument-hint: <project_key>
---

Génère le PPT d'indicateurs pour le projet **$1**, enrichi du contexte équipe.
Racine effective de toutes les commandes ci-dessous : `skills/jira-report/`.
`projects/`, `contexte/`, `templates/` et `.env` ci-dessous sont dans le
répertoire de données, pas dans ce dossier — voir `SKILL.md`.

0. **Répertoire de données absent ?** Si les scripts échouent avec
   `DataDirNotConfigured` : demander à l'utilisateur où le créer, lancer
   `python scripts/bootstrap.py <chemin_choisi>`, puis reprendre à l'étape 1 —
   voir `SKILL.md`, section « Première utilisation ».

1. **Résoudre le contexte.**
   ```bash
   python scripts/resolve_context.py $1
   ```
   Si la commande échoue (team_id absent de `projects/$1/project.yaml`, ou fichier
   `contexte/<team_id>.md` / `contexte/organisation.md` introuvable) : afficher
   l'erreur telle quelle à l'utilisateur et **s'arrêter là** — ne pas générer de PPT
   sans contexte résolu, ne rien inventer à la place.

2. **Données JIRA.** Si `projects/$1/output/data.json` n'existe pas encore, l'extraire :
   ```bash
   python scripts/fetch_jira.py $1
   ```
   S'il existe déjà, le réutiliser tel quel (pour des données fraîches, lancer
   `/coach-refresh $1` avant cette commande — c'est aussi `/coach-refresh` qui
   écrit ou met à jour la synthèse coach).

3. **Synthèse coach (uniquement si absente).** Vérifier si `projects/$1/output/data.json`
   contient déjà une clé `coaching` (normalement écrite par `/coach-refresh $1`).
   - Si elle est déjà présente : ne pas la réécrire, passer à l'étape 4.
   - Si elle est absente (ex. premier build sans être passé par
     `/coach-refresh`) : la rédiger en suivant `COACH_PROMPT.md`, à partir des
     données JIRA **et** du contexte résolu à l'étape 1, puis la valider et
     l'écrire avec :
     ```bash
     python scripts/check_coaching.py <coaching_utf8.json>
     python scripts/set_coaching.py $1 <coaching_utf8.json>
     ```
     Si la rédaction fait ressortir un fait qui mériterait d'être conservé dans
     le contexte équipe, suivre la section « Proposer un ajout de contexte » de
     `COACH_PROMPT.md` (proposer, attendre confirmation, jamais écrire en
     silence).

4. **Générer le PPT.**
   ```bash
   python scripts/build_ppt.py $1
   ```

5. **QA.** Vérifier qu'aucun placeholder `{{...}}` ne subsiste dans le fichier
   généré (voir section QA de `SKILL.md`).
