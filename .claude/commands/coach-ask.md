---
description: Répond à une question précise sur un projet ou une équipe, à partir des données JIRA et du contexte — sans générer de PPT
argument-hint: <project_key|team_id> <question>
---

La question porte sur **$1** : "$2" (et le reste des arguments après le premier).
Racine effective : `skills/jira-report/`. `projects/`, `contexte/`, `templates/`
et `.env` ci-dessous sont dans le répertoire de données, pas dans ce dossier —
voir `SKILL.md`.

0. **Répertoire de données absent ?** Si `resolve_context.py` échoue avec
   `DataDirNotConfigured` : demander à l'utilisateur où le créer, lancer
   `python scripts/bootstrap.py <chemin_choisi>`, puis reprendre à l'étape 1.

1. **Résoudre le contexte.**
   ```bash
   python scripts/resolve_context.py $1
   ```
   `$1` peut être une clé de projet (résout son `team_id` depuis
   `projects/$1/project.yaml`) ou directement un `team_id` (ex. une question sur
   toute l'équipe, pas un projet précis). Si la commande échoue, afficher
   l'erreur telle quelle et s'arrêter — ne pas répondre à partir d'un contexte
   deviné.

2. **Données JIRA (si pertinent).** Si `$1` est résolu comme un projet
   (`resolved_as: "project"`) et que `projects/$1/output/data.json` existe, le
   lire pour les chiffres. S'il n'existe pas, répondre à partir du contexte seul
   et le signaler (ne pas lancer `fetch_jira.py` automatiquement — utiliser
   `/coach-refresh $1` d'abord si des chiffres à jour sont nécessaires).

3. **Répondre** directement dans la conversation, en s'appuyant explicitement sur
   les données et/ou le contexte résolus à l'étape 1. Ne jamais inventer un fait ou
   un chiffre absent des deux sources — dire explicitement ce qui manque plutôt que
   de l'extrapoler.

4. **Si la réponse fait ressortir un fait qui mériterait d'être conservé** pour les
   prochaines analyses de cette équipe, suivre la section « Proposer un ajout de
   contexte » de `COACH_PROMPT.md` : proposer le bloc exact, attendre une
   confirmation explicite, puis seulement `python scripts/append_context.py
   <team_id> <bloc_utf8.md>`. Jamais d'écriture sans confirmation.
