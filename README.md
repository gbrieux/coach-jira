#  Reporting JIRA & coaching agile

Outil interne pour l'équipe de coachs agiles  : génère des PPT d'indicateurs
projet à partir de JIRA, avec une synthèse rédigée par Claude qui s'appuie à la
fois sur les données JIRA **et** sur du contexte qualitatif équipe (composition,
priorités, points de blocage...) partagé entre tous les coachs.

Ce dépôt contient deux choses bien séparées (voir `CLAUDE.md`) :
- `skills/jira-report/` — le **code du skill**, générique et distribuable tel
  quel  ;
- tout le reste à la racine (`projects/`, `contexte/`, `templates/`, `.env`) —
  les **données privées**  : projets Jira, contexte qualitatif équipe,
  charte graphique, PPT générés. Ce dépôt dans son ensemble reste interne,
  jamais publié — seul `skills/jira-report/` est conçu pour l'être un jour,
  séparément.

## Installation

1. **Cloner le dépôt.**
   ```bash
   git clone <url-du-repo> societe
   cd societe
   ```

2. **Dépendances Python.**
   ```bash
   pip install -r skills/jira-report/requirements.txt
   ```

3. **Répertoire de données.** Déjà en place dans ce dépôt (`projects/`,
   `contexte/`, `templates/`, `.env`) — le skill le retrouve via
   `skills/jira-report/.data-dir-path` (pointeur local, non versionné). Sur un
   nouveau poste, ce pointeur n'existe pas encore : la première commande
   (`/coach-refresh` par exemple) demande où pointer et lance
   `python skills/jira-report/scripts/bootstrap.py <chemin>` — répondre par la
   racine de ce dépôt (là où vivent déjà `projects/`, `contexte/`, etc.), pas
   un nouvel emplacement vide. Voir `skills/jira-report/SKILL.md`, section
   « Première utilisation », pour le détail (et pour un tout premier
   déploiement du skill ailleurs que sur ce dépôt).

4. **Identifiants JIRA** dans `.env` (déjà présent, à vérifier/compléter) :
   ```
   JIRA_BASE_URL=https://societe.atlassian.net
   JIRA_EMAIL=votre.email@email.pro
   JIRA_API_TOKEN=xxxxxxxx
   ```
   Le token est un **API token Atlassian** personnel
   (https://id.atlassian.com/manage-profile/security/api-tokens), en Basic Auth
   avec l'email. Ne jamais le committer.

5. **Vos projets** dans `projects/<clé>/project.yaml` — un dossier par projet :
   ```yaml
   name: "Mon projet"
   team_id: "MON_EQUIPE"        # voir convention team_id ci-dessous
   jql: 'project = XXX AND ...'
   board_id: 123                # ID du board Agile (URL du board Jira)
   ```
   Détail complet des champs (sprint_field, us_types, done_statuses...) : voir
   `skills/jira-report/scaffold/project.example.yaml` et
   `skills/jira-report/SKILL.md`.

6. **Template PowerPoint** : `templates/template.pptx` doit déjà être en place
   (charte , placeholders `{{...}}`) — celui-ci reste dans ce dépôt (asset
   privé, pas dans le skill). Vérifier avec :
   ```bash
   cd skills/jira-report
   python scripts/inspect_template.py
   ```

## Convention `team_id`

Chaque projet dans `projects/<clé>/project.yaml` porte un champ `team_id` — la
valeur exacte (sensible à la casse, jamais devinée) qui pointe vers
`contexte/<team_id>.md`, le fichier de contexte qualitatif de l'équipe. Une
équipe peut porter plusieurs projets (même `team_id` sur plusieurs projets).

- `contexte/organisation.md` — contexte transverse à toute l'organisation
  (conventions, DoR/DoD communes...), toujours lu.
- `contexte/<team_id>.md` — un fichier par équipe. S'il n'existe pas encore pour
  une nouvelle équipe, le premier ajout de contexte le crée automatiquement (voir
  la règle d'écriture dans `CLAUDE.md`).

Si `team_id` est absent d'un projet, ou si son fichier de contexte n'existe pas,
les commandes `/coach-ppt` et `/coach-ask` échouent proprement avec un message
explicite plutôt que de générer une analyse sans contexte.

## Utilisation

Dans Claude Code, à la racine du dépôt :

- `/coach-refresh <projet>` — rafraîchit les données JIRA et réécrit la synthèse
  coach à partir des données fraîches (pas de PPT).
- `/coach-ppt <projet>` — génère le PPT à partir des données + de la synthèse
  déjà en place (ne les rédige que si elles manquent encore).
- `/coach-ask <projet|équipe> <question>` — répond à une question précise sans
  générer de PPT.

Dans Codex, les mêmes commandes existent comme skills (`coach-refresh`,
`coach-ppt`, `coach-ask` — voir `.agents/skills/`, régénéré depuis
`.claude/commands/` par `python scripts/sync_agents.py`).
