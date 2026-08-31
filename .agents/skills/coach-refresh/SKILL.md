---
name: coach-refresh
description: "Rafraîchit les données JIRA d'un projet et réécrit la synthèse coach à partir des données fraîches, sans régénérer le PPT"
---

# Coach refresh (Codex — relais vers la commande Claude Code)

Contenu source, identique pour Claude Code et Codex : voir
`.claude/commands/coach-refresh.md`. `$1`/`$2` y désignent les arguments fournis par
l'utilisateur dans sa demande (ex. la clé de projet, la question). Ne pas
dupliquer cette logique ici — la lire et l'appliquer directement depuis ce
fichier source.

Régénéré automatiquement par `scripts/sync_agents.py` à partir de
`.claude/commands/coach-refresh.md` — ne pas éditer à la main.
