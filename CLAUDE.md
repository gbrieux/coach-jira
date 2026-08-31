# Reporting JIRA & contexte coach agile

## Structure

- `skills/jira-report/` — le skill (code seul, générique, distribuable :
  scripts, scaffold). Aucune donnée réelle —  voir `skills/jira-report/SKILL.md`.
- Reste de ce dépôt (répertoire de données du skill, jamais versionné *avec le
  skill* mais bien avec ce dépôt — voir `skills/jira-report/SKILL.md`, section
  « Répertoire de données ») — données privées de l'équipe/de l'organisation :
  - `projects/<clé>/project.yaml` — un dossier par projet (JQL, board Jira,
    `team_id`), sortie générée dans `projects/<clé>/output/`.
  - `contexte/` — contexte qualitatif équipe :
    - `organisation.md` — contexte transverse, toujours lu.
    - `<team_id>.md` — un fichier par équipe (`team_id` = valeur exacte du champ
      dans `project.yaml`, sensible à la casse, jamais deviné à partir du nom du
      projet). Une équipe peut porter plusieurs projets.
  - `templates/template.pptx` — charte graphique de la societe.
  - `.env` — identifiants JIRA (jamais commité).

## Commandes

- `/coach-refresh <projet>` — rafraîchit les données JIRA et réécrit la synthèse
  coach à partir des données fraîches (pas de PPT).
- `/coach-ppt <projet>` — génère le PPT à partir des données + de la synthèse déjà
  en place (les rédige seulement si elles manquent encore).
- `/coach-ask <projet|équipe> <question>` — répond à une question précise à partir
  des données et du contexte, sans générer de PPT.

Équivalents Codex (skills, pas de slash commands) : `coach-refresh`, `coach-ppt`,
`coach-ask` dans `.agents/skills/` — régénéré depuis `.claude/commands/` par
`python scripts/sync_agents.py`, jamais édité à la main.

## Règle d'écriture du contexte

Tout ajout dans `contexte/*.md` — que ce soit à la demande explicite, ou proposé en
cours d'analyse parce qu'un fait mérite d'être conservé :

1. Montrer le texte exact avant d'écrire quoi que ce soit.
2. Attendre une confirmation explicite de l'utilisateur.
3. Horodater (`## AAAA-MM-JJ — sujet`) et ajouter en fin de fichier — jamais
   réécrire ou supprimer l'existant.

Jamais d'écriture silencieuse, dans un sens comme dans l'autre. Le squelette vide
(commenté, sans contenu) que `scripts/bootstrap.py` dépose dans un tout nouveau
`contexte/organisation.md` n'est pas concerné par cette règle — elle s'applique
au premier vrai *contenu*, pas à la structure de départ.

Le reste (résolution d'équipe, calculs d'indicateurs, rendu du PPT, prompt de
synthèse) vit dans le skill — voir `skills/jira-report/SKILL.md` et
`skills/jira-report/COACH_PROMPT.md`.
