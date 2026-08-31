# Reporting JIRA & contexte coach agile (Codex)

Règles, structure de `contexte/` et commandes : voir [`CLAUDE.md`](CLAUDE.md) à la
racine du dépôt — source unique, valable pour Claude Code et Codex. Ne rien
dupliquer ici : ce fichier ne fait que pointer vers les bons points d'entrée côté
Codex.

## Points d'entrée Codex

Codex n'a pas de slash commands ; les mêmes commandes sont exposées comme skills
dans `.agents/skills/` (régénéré depuis `.claude/commands/*.md` par
`python scripts/sync_agents.py` — ne jamais éditer `.agents/skills/` à la main,
`.claude/commands/` reste la source unique) :

- `coach-refresh` — données JIRA + synthèse coach (pas de PPT), équivalent de
  `/coach-refresh <projet>`.
- `coach-ppt` — PPT depuis les données (+ synthèse) déjà en place, équivalent de
  `/coach-ppt <projet>`.
- `coach-ask` — répond à une question précise sans générer de PPT, équivalent de
  `/coach-ask <projet|équipe> <question>`.

Toutes pointent sur `skills/jira-report/`, racine effective du code. La
rédaction de la synthèse coach (`COACH_PROMPT.md`) se fait au moment du refresh
(`coach-refresh`), pas au moment du build — sauf absence encore constatée à ce
stade, auquel cas `coach-ppt` la rédige en repli, jamais bloquant. Elle se
rédige en session (par l'agent, Claude ou Codex) — jamais par script.

## Règle d'écriture du contexte

Identique à `CLAUDE.md` : tout ajout dans `contexte/*.md` se montre avant écriture,
attend une confirmation explicite, est horodaté (`## AAAA-MM-JJ — sujet`) et ajouté
en fin de fichier — jamais d'écriture silencieuse ni de réécriture de l'existant.
