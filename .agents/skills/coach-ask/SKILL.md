---
name: coach-ask
description: "Répond à une question précise sur un projet ou une équipe, à partir des données JIRA et du contexte — sans générer de PPT"
---

# Coach ask (Codex — relais vers la commande Claude Code)

Contenu source, identique pour Claude Code et Codex : voir
`.claude/commands/coach-ask.md`. `$1`/`$2` y désignent les arguments fournis par
l'utilisateur dans sa demande (ex. la clé de projet, la question). Ne pas
dupliquer cette logique ici — la lire et l'appliquer directement depuis ce
fichier source.

Régénéré automatiquement par `scripts/sync_agents.py` à partir de
`.claude/commands/coach-ask.md` — ne pas éditer à la main.
