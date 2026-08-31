# Prompt — Synthèse du coach agile

Instructions pour rédiger les textes narratifs du PPT « design agile ». Cette
étape est effectuée par **Claude en session, pas par un script** : lire
`projects/<clé>/output/data.json`, rédiger les textes ci-dessous en suivant ce
prompt, puis les écrire dans le JSON sous la clé `coaching` — un **objet**
(pas une chaîne), avec la structure exacte suivante :

```json
"coaching": {
  "vue_ensemble": "…",
  "risque_principal": "…",
  "lecture": {
    "Vélocité": "…",
    "Cycle time": "…",
    "Périmètre": "…",
    "Flux": "…",
    "Sprint NN": "…"
  },
  "recommandations": ["…", "…", "…"],
  "burndown_lecture": "…",
  "velocity_lecture": "…",
  "types_lecture": "…",
  "cycle_time_lecture": "…",
  "conso_corrective_lecture": "…"
}
```

Tous les champs sont optionnels — un champ absent fait disparaître proprement
la carte/texte correspondant sur la slide (aucune ne bloque le rendu). Ne pas
inventer de contenu pour un champ si les données ne le justifient pas.

## Étape 0 — Résoudre le contexte (avant toute rédaction)

```bash
python scripts/resolve_context.py <project_key>
```

Ce script résout de façon déterministe le `team_id` du projet (`projects/<clé>/project.yaml`)
et renvoie `organisation.md` (contexte transverse, toujours applicable) + le
`contexte/<team_id>.md` de l'équipe concernée. **Si la commande échoue** (team_id
absent, fichier de contexte introuvable), afficher l'erreur telle quelle à
l'utilisateur et s'arrêter — ne jamais inventer de contexte équipe ni continuer
sans lui pour compenser.

Utiliser ce contexte, en plus des données JIRA, pour rédiger les champs ci-dessous —
mais seulement quand il éclaire réellement un chiffre (voir « Mélanger données et
contexte » plus bas). Ne pas mentionner de nom de fichier ou l'existence même du
fichier de contexte dans le texte final — l'information doit être intégrée
naturellement, sourcée par le fond, pas par sa provenance.

## Mélanger données et contexte

S'applique à tous les champs (slide 11 et les 4 `*_lecture`) :

- Le contexte **explique**, il ne **remplace** jamais un chiffre. Un chiffre reste
  d'abord interprété à partir des données ; le contexte n'intervient que pour
  éclairer *pourquoi* ce chiffre est ce qu'il est, quand c'est manifeste.
- Exemple légitime : une vélocité en forte baisse ce trimestre + `NOS.md` mentionne
  que l'effectif de l'équipe a été réduit → le dire explicitement plutôt que de
  laisser la baisse sans explication.
- Ne jamais forcer un lien qui n'existe pas : si rien dans le contexte n'éclaire un
  chiffre donné, se limiter aux données, comme avant.
- Ne jamais laisser le contexte contredire silencieusement les données (ex. le
  contexte dit « projet presque fini » mais `burnup_release` montre 20 %
  d'avancement) — dans ce cas, signaler l'écart plutôt que de trancher pour l'un
  ou l'autre.

## Écriture UTF-8 obligatoire (Codex sous Windows)

Sous Windows PowerShell 5.1, ne jamais envoyer un here-string contenant des
accents avec `@'…'@ | python -` : `$OutputEncoding` vaut `us-ascii` par défaut
et remplace les caractères accentués par `?` avant leur arrivée dans Python.

Écrire l'objet coaching dans un fichier JSON réellement UTF-8, puis utiliser :

```powershell
python scripts/set_coaching.py <project_key> <coaching_utf8.json>
```

Le helper valide l'encodage et injecte l'objet de manière atomique. Le builder
refuse également tout coaching manifestement corrompu au lieu de produire un
PPT irréparable.

## Slide 11 — « Lecture du coach » (les 5 premiers champs)

### `vue_ensemble` (3 à 5 phrases, prose continue, pas de puces)

Orienté sponsors/direction. Répondre à :
- Où en est-on ? (`total_issues`, `total_story_points`, périmètre US actuel via
  `burnup_release.scope_cumul_us` / `done_cumul_us` — % d'avancement)
- Tient-on la date/l'objectif ? (`burnup_release.trend_pessimist` /
  `trend_median` / `trend_optimist` — combien de sprints séparent chaque
  scénario de l'atteinte du périmètre actuel ; si absents, le dire)
- Quel est le principal risque à date ? (un seul, le plus significatif)

Ton factuel, pas de jargon agile non expliqué, pas de recommandation ici.

### `risque_principal` (2-3 phrases)

Développe le risque déjà évoqué dans `vue_ensemble` — affiché seul dans une
carte orange à côté.

### `lecture` (dict ordonné, clé = libellé court affiché en accent, valeur = 1-2 phrases)

Un sujet par entrée, dans cet ordre si les données le permettent : Vélocité,
Cycle time, Périmètre, Flux, Sprint NN (le sprint en cours). Ne commenter que
ce qui ressort réellement des chiffres :
- **Vélocité** : `velocity` (engaged/done par sprint), `avg_velocity`,
  `median_velocity_us` — une vélocité erratique (grands écarts d'un sprint à
  l'autre) est un signal à creuser.
- **Cycle time** : `cycle_time` (p15/médiane/moyenne/p85/count) — écart
  médiane/moyenne important = tickets qui traînent.
- **Périmètre** : `sprint_table`/`burnup_release` — le périmètre grossit-il
  plus vite qu'il ne se termine ?
- **Flux** : `status_counts_us` — accumulation anormale sur un statut
  intermédiaire = goulot d'étranglement.
- **Sprint NN** : `burndown_sprint` (ideal vs real) — écart à la cible.

### `recommandations` (liste de 1 à 3 items courts, actionnables)

Chacune reliée explicitement à une observation ci-dessus — jamais de généralité
du type "améliorer la communication" sans lien avec un chiffre du JSON.
Pour faire le recommandation , appuie toi sur les fichiers  de contexte du projet  `<team_id>.md` et organisation.md
Elle permette d'avoir une vision plus fine du contexte avant de donner des reco.
Fini ta reco pas une simple question de coach agile si pertinent.

## Autres slides (les 5 derniers champs — 1 à 2 phrases chacun)

- `burndown_lecture` (slide 3) : la courbe réelle décroche-t-elle de l'idéale,
  dans quel sens ?
- `velocity_lecture` (slide 5) : régularité de la vélocité sprint à sprint.
- `types_lecture` (slide 7) : lecture sur la répartition des types de tickets.
- `cycle_time_lecture` (slide 9) : lecture sur l'écart moyenne/médiane.
- `conso_corrective_lecture` (`{{chart:conso_corrective}}`) : la part
  anomalie/incident augmente-t-elle ou diminue-t-elle sur les derniers mois ?
  Ne pas commenter si `anomaly_types`/`incident_types` sont vides dans
  `project.yaml` (charge corrective alors toujours à 0%, rien à interpréter).

## Proposer un ajout de contexte

En rédigeant l'analyse (ou en répondant à une question via `/coach-ask`), un fait
peut mériter d'être conservé pour les prochaines analyses de cette équipe (ex. un
changement d'effectif, une décision d'organisation, un point de blocage récurrent
mentionné par l'utilisateur mais absent de `<team_id>.md`). Dans ce cas :

1. **Proposer**, ne jamais écrire directement : montrer à l'utilisateur le bloc
   exact tel qu'il serait ajouté, au format
   ```markdown
   ## AAAA-MM-JJ — [sujet court]
   Contenu…
   ```
   avec la date du jour (jamais devinée ni approximative).
2. **Attendre une confirmation explicite** avant d'écrire quoi que ce soit.
3. Une fois confirmé, écrire le bloc proposé dans un fichier temporaire UTF-8 puis
   l'ajouter avec :
   ```bash
   python scripts/append_context.py <team_id> <bloc_utf8.md>
   ```
   Le script ajoute toujours en fin de fichier (jamais de réécriture de
   l'existant) et crée `contexte/<team_id>.md` s'il n'existe pas encore.

Cette règle s'applique aussi bien quand l'utilisateur demande explicitement un
ajout que quand c'est vous qui en repérez un pertinent en cours d'analyse — dans
les deux cas, montrer puis attendre, jamais écrire en silence.

## Contraintes

- Français, ton professionnel et direct — pas de flatterie ni d'alarmisme.
- Ne jamais inventer un chiffre : si une donnée manque, est à 0 ou vide (ex. pas
  de sprint actif → `burndown_sprint` est `null`), le dire explicitement plutôt
  que de l'ignorer ou de l'extrapoler.
- Longueur cible pour la slide coach (5 premiers champs) : 200 à 350 mots au
  total. Au-delà d'environ 2000 caractères cumulés, le rendu scinde
  automatiquement en 2 slides (« Synthèse — 1/2 » / « — 2/2 ») — ne jamais
  chercher à raccourcir en réduisant la police en dessous de 12 pt.
- Les 4 champs `*_lecture` restent courts (1-2 phrases) : ce sont des légendes,
  pas des synthèses.
- Ne pas répéter les chiffres bruts déjà visibles sur la slide correspondante
  (ils sont dans les cartes/graphiques) — les interpréter, pas les recopier.
