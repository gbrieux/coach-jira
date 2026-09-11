---
name: jira-report
description: "Génère un PowerPoint d'indicateurs projet (burndown, burnup, vélocité, répartition des statuts, délais de résolution) à partir des données JIRA, enrichi d'une synthèse coach qui croise ces données avec du contexte qualitatif équipe. Utiliser dès qu'on demande un reporting projet, un PPT d'indicateurs, un point d'avancement projet, ou un export d'indicateurs JIRA vers slides. Chaque projet est défini par un JQL dans projects/<clé>/project.yaml et produit un PPT rempli à partir d'un template annoté de placeholders."
---

# JIRA Report — PPT d'indicateurs + synthèse coach

Génère un ou plusieurs `.pptx` d'indicateurs projet à partir de JIRA, en remplissant
les placeholders d'un template PowerPoint. Un projet = un dossier dans `projects/` =
un JQL = un PPT.

## Points d'entrée recommandés

Préférer les slash commands (`.claude/commands/`) à une formulation libre —
comportement identique pour tous, peu importe comment la demande est tournée :

- **`/coach-refresh <projet>`** — rafraîchit les données JIRA et réécrit la
  synthèse coach à partir des données fraîches (pas de PPT).
- **`/coach-ppt <projet>`** — génère le PPT à partir des données + de la synthèse
  déjà en place (les rédige seulement si elles manquent encore).
- **`/coach-ask <projet|équipe> <question>`** — répond à une question précise à
  partir des données + du contexte, sans générer de PPT.

Voir `CLAUDE.md` (racine de l'espace de travail) pour la structure `contexte/` et
la règle d'écriture. Le reste de ce document décrit le fonctionnement interne —
utile pour comprendre ou dépanner, pas nécessaire pour l'usage courant.

## Répertoire de données (privé, hors du repo skill)

Ce dossier (`skills/jira-report/`) est du **code distribuable** — aucune donnée
réelle n'y vit, aucune référence à une organisation précise. Les données privées
(`.env`, `projects/<clé>/project.yaml`, `contexte/*.md`, `templates/template.pptx`,
les JSON/PPT générés) vivent dans un **répertoire de données** séparé, choisi une
fois par l'utilisateur et jamais versionné avec le skill.

Résolution (`scripts/workspace.py`), dans l'ordre :
1. Variable d'environnement `REPORT_DATA_HOME`, si définie.
2. Pointeur local `.data-dir-path` (à côté de ce fichier, gitignoré), écrit par
   `scripts/bootstrap.py` lors du premier lancement.
3. Ni l'un ni l'autre : erreur claire — voir « Première utilisation » plus bas.

Le reste de ce document utilise `projects/...`, `contexte/...`, `templates/...`
et `.env` comme raccourcis pour ces chemins **relatifs au répertoire de données**,
jamais au repo skill.

## Première utilisation (bootstrap)

Si aucun répertoire de données n'est configuré (`scripts/workspace.py` lève
`DataDirNotConfigured`), ne jamais deviner un emplacement : demander à
l'utilisateur où le créer (typiquement un dossier sibling du skill dans son
espace de travail, ex. à côté de `skills/` — mais c'est son choix), puis lancer
une seule fois :
```bash
python scripts/bootstrap.py <chemin_choisi>
```
Ceci crée `projects/`, `contexte/organisation.md` (squelette commenté vide),
`templates/template.pptx` (neutre, à remplacer par sa propre charte) et `.env`
(à partir de `.env.example`), et mémorise le chemin dans `.data-dir-path` — les
lancements suivants n'ont plus besoin de le redemander. Idempotent : si un
répertoire est déjà configuré, `bootstrap.py` refuse d'écraser plutôt que de
re-bootstraper dessus.

Ensuite, demander à l'utilisateur ses identifiants JIRA (`.env`) et son premier
projet (`projects/<clé>/project.yaml`, voir `scaffold/project.example.yaml` pour
le détail des champs) — ne jamais inventer de token, de JQL ou de board_id.

## Workflow (dans l'ordre)

1. **Vérifier la config.** Un dossier `projects/<clé>/` avec un `project.yaml`
   doit exister pour la clé demandée, et `.env` doit contenir les identifiants
   JIRA. Si l'un des deux manque, voir « Première utilisation » — ne pas
   inventer d'identifiants.
2. **Extraire les données JIRA.** `python scripts/fetch_jira.py <clé>` (ou `--all`)
   → écrit `projects/<clé>/output/data.json`. Le script gère la pagination et
   calcule déjà les séries (burndown, burnup, vélocité, statuts, délais).
3. **Résoudre le contexte équipe.** `python scripts/resolve_context.py <clé>`
   → renvoie `organisation.md` + `contexte/<team_id>.md` (team_id résolu depuis
   `projects/<clé>/project.yaml`). Échec propre et explicite si le team_id ou le
   fichier de contexte manque — dans ce cas, s'arrêter et remonter l'erreur, ne
   pas inventer.
4. **Textes narratifs (recommandée, jamais bloquante).** Lire
   `projects/<clé>/output/data.json` **et** le contexte résolu à l'étape 3,
   rédiger les textes en suivant `COACH_PROMPT.md`, puis les écrire dans le JSON
   sous la clé `coaching` (objet structuré — pas une chaîne, voir le prompt).
   **C'est Claude qui rédige en session — pas de script.** Alimente la slide
   « Lecture du coach », la slide « Décisions & questions » (`delta`/`questions`,
   voir plus bas), et les courtes légendes de graphique (dont `epics_lecture`).
   Si sautée, `build_ppt.py` s'exécute quand même : les cartes/légendes/slides
   concernées sont simplement absentes du rendu, rien ne casse. Sous
   Windows/Codex, écrire l'objet dans un fichier JSON UTF-8, le valider avec
   `python scripts/check_coaching.py <coaching_utf8.json>` (plafonds/cardinalités —
   voir COACH_PROMPT.md, « Contraintes de rendu », seule source de vérité de ces
   plafonds), puis l'injecter avec `python scripts/set_coaching.py <clé>
   <coaching_utf8.json>` (qui applique de toute façon la même validation en
   interne juste avant d'écrire) ; ne jamais transmettre un texte accentué avec
   `@'…'@ | python -`.

   `data.json` étant réécrit en entier à chaque `fetch_jira.py`, la synthèse
   précédente est perdue au refresh suivant si elle n'est pas archivée d'abord —
   d'où `python scripts/coaching_history.py archive <clé>` **avant** l'étape 2, et
   `python scripts/coaching_history.py last <clé>` pour retrouver la dernière
   synthèse archivée (sert de base au champ `delta`). Voir
   `scripts/coaching_history.py` (module) et COACH_PROMPT.md, étape 3.

   Les étapes 1 à 4 (archive + données + contexte + synthèse) sont regroupées dans
   `/coach-refresh` : la synthèse est réécrite à chaque refresh, à partir des
   données qui viennent d'être rafraîchies, pas au moment du build.
5. **Générer le PPT.** `python scripts/build_ppt.py <clé>` (ou `--all`) → lit le
   JSON + `templates/template.pptx`, génère chaque slide dans le design agile
   (voir `scripts/style.py`/`scripts/render_agile.py`), écrit
   `projects/<clé>/output/indicateurs.pptx`. C'est l'étape que fait `/coach-ppt` :
   elle ne réécrit la synthèse (étape 4) que si elle est encore absente du JSON.
6. **QA (obligatoire).** Valider et inspecter visuellement — voir « QA ».

Pour tout traiter d'un coup : `python scripts/fetch_jira.py --all && python scripts/build_ppt.py --all`
(sans synthèse coach dans ce cas — repasser par `/coach-refresh` projet par projet
pour l'obtenir, la rédaction restant un acte de session, pas scriptable en `--all`).

## Ajouter un projet

Créer `projects/<clé>/project.yaml` à partir de `scaffold/project.example.yaml`
(champs commentés). Demander à l'utilisateur le JQL, le `board_id` et le
`team_id` — ne jamais les deviner. Si le `team_id` est nouveau, `contexte/<team_id>.md`
sera créé au premier ajout de contexte (voir « Proposer un ajout de contexte »
dans `COACH_PROMPT.md`), jamais avant, jamais avec du contenu inventé.

## Configuration

### `.env` (secrets — jamais commité, jamais dans le repo skill)

```
JIRA_BASE_URL=https://votre-organisation.atlassian.net
JIRA_EMAIL=votre.email@exemple.com
JIRA_API_TOKEN=xxxxxxxx
```

Le token est un **API token Atlassian** (https://id.atlassian.com/manage-profile/security/api-tokens),
utilisé en Basic Auth avec l'email.

Optionnel — `TEMPO_NAME`/`TEMPO_API_TOKEN`, seulement pour `{{chart:tempo_conso}}`
(voir table des indicateurs). Token Tempo dédié (Jira > Tempo > Settings >
API Integration > API Tokens), distinct de `JIRA_API_TOKEN`. Absent = l'app
Tempo n'étant pas installée sur tous les projets, l'indicateur affiche un
message plutôt qu'un graphique — rien d'autre n'est affecté.

### `projects/<clé>/project.yaml` (un fichier par projet)

Voir `scaffold/project.example.yaml` pour la liste complète des champs
(obligatoires : `name`, `team_id`, `jql` ; le reste a des valeurs par défaut).
`<clé>` (le nom du dossier) est l'identifiant utilisé partout : `fetch_jira.py <clé>`,
`build_ppt.py <clé>`, `/coach-refresh <clé>`, etc.

### `contexte/` (contexte qualitatif équipe)

- `contexte/organisation.md` — contexte transverse, toujours lu.
- `contexte/<team_id>.md` — un fichier par équipe (une équipe peut porter plusieurs
  projets, ex. `NOS_R1` et `NOS_R2` peuvent partager `team_id: "NOS"`).

`team_id` est la valeur exacte du champ dans `projects/<clé>/project.yaml` —
sensible à la casse, jamais devinée à partir du nom du projet. Résolution et
lecture : voir `scripts/resolve_context.py`. Écriture (ajout de contexte) : voir
`scripts/append_context.py` et la section « Proposer un ajout de contexte » de
`COACH_PROMPT.md`.

## Indicateurs produits

Tous les indicateurs US-scopés (burnup, burndown, vélocité, statuts, cycle time)
ne comptent que les tickets de type `User Story`/`Story` (`us_types` en config) —
pas les tâches techniques, sous-tâches, anomalies, etc.

| Indicateur | Placeholder chart | Source |
|---|---|---|
| Burnup release (US) | `{{chart:burnup}}` | terminé cumulé vs périmètre cumulé US par sprint, + 3 courbes de tendance (pessimiste/médiane/optimiste) projetées depuis la fin du sprint en cours. Périmètre/terminé cumulés en Story Points en axe secondaire (droite) — pas de tendance SP. |
| Burndown sprint en cours (US) | `{{chart:burndown}}` | reste à faire jour par jour dans le sprint actif uniquement, vs droite idéale ; périmètre = US actuellement dans ce sprint (reports inclus). Reste à faire + droite idéale en Story Points en axe secondaire. |
| Vélocité / Engagement (US) | `{{chart:velocity}}` | engagé vs terminé par sprint (champ Sprint JIRA), + ligne médiane (sprints à 0 terminé exclus). Engagé/terminé en Story Points en axe secondaire (lignes, vs barres US). |
| Répartition statuts (US) | `{{chart:status}}` | count par statut — dégradé clair -> foncé dans l'ordre du `workflow`, statuts `done_statuses` en vert, statuts "en attente" en orange (même couleurs dans la barre et les cartes). Un statut avec un segment trop étroit pour son libellé reçoit une étiquette externe au-dessus/en dessous de la barre (deux statuts étroits consécutifs alternent de côté). |
| Cumulative Flow Diagram (US) | `{{chart:cumulative_flow_diagram}}` | bandes empilées, jour par jour, du nb d'US ayant atteint chaque statut du `workflow` configuré (ou un statut suivant) — nécessite `workflow` non vide dans `project.yaml` (contrairement à `{{chart:status}}`, pas de repli par fréquence : l'ordre doit refléter la vraie progression). Reconstruit à partir de l'historique des statuts (`changelog`, voir « Champs JIRA récupérés »). Regroupement des statuts et bornes de dates configurables via le bloc optionnel `cfd:` de `project.yaml` (voir `scaffold/project.example.yaml`) — utile quand `workflow` compte beaucoup d'étapes (bandes trop nombreuses pour rester lisibles). |
| Types de tickets (nb) | `{{chart:types}}` | count par type (tous types) |
| Types de tickets (conso) | `{{chart:types_conso}}` | timespent en jh par type (tous types) |
| Charge corrective (conso) | `{{chart:conso_corrective}}` | 100% empilé, jh consommés par mois (mois de `resolutiondate`) sur tickets terminés, ventilés en 4 catégories anomalie / incident / Us / US tech — mapping par type de ticket exact via `anomaly_types`/`incident_types`/`tech_types`/`us_types` (config). Ticket terminé dont le type n'est dans aucune des 4 listes : exclu du graphique (pas de 5e bucket "Autre"). |
| Conso Tempo vs US terminées | `{{chart:tempo_conso}}` | barres : conso Tempo (jh, worklogs agrégés par sprint via leur date de log) ; ligne (axe secondaire) : nb d'US terminées par sprint. Nécessite Tempo installé sur le projet **et** `TEMPO_API_TOKEN`/`TEMPO_NAME` dans `.env` (voir « Configuration ») — absent des deux : message "Données Tempo JIRA non disponibles" à la place du graphique, jamais de graphique vide. |
| Temps Tempo par type de ticket (conso) | `{{chart:tempo_types}}` | barres empilées en volume absolu (jh), worklogs Tempo agrégés par mois du log — une série par type de ticket JIRA exact rencontré (tous types, pas de regroupement), triées par jh décroissant. Même dépendance Tempo que `{{chart:tempo_conso}}` (même message si absent). |
| Cycle time (US) | `{{chart:cycle_time}}` | P15 / médiane / moyenne / P85 |
| Répartition par nombre de sprints (US) | `{{chart:sprint_spread}}` | US terminées, groupées par nombre de sprints distincts traversés (champ Sprint JIRA) — dégradé clair (1 sprint) -> foncé (le plus de sprints). US sans sprint renseigné exclues (rien à mesurer). |
| Tableau des sprints (US) | `{{liste_sprints}}` | table native : ajouts/terminés par sprint, cumuls (nb + jh) |
| Tableau des epics | `{{liste_epics}}` | table native : reste à faire théorique (jh) par epic ; bandeau légende (`coaching.epics_lecture`, optionnel) sous le tableau — tableau à hauteur réduite quand présent, hauteur d'origine sinon (jamais de trou) |
| KPI cycle time | `{{kpi:*}}` | cartes de synthèse cycle time (voir placeholders texte ci-dessous) |
| Synthèse du coach | `{{coach:synthese}}` | texte rédigé par Claude en session, voir `COACH_PROMPT.md` — conditionnel, sauté si absent du template |
| Décisions & questions | `{{coach:decisions}}` | `coaching.delta` (ce qui a bougé depuis la synthèse précédente) et `coaching.questions` (2-3 questions de coach affichées sur la slide, distinctes des questions de session) — slide entièrement retirée du PPT si les deux sont absents, voir COACH_PROMPT.md |

Placeholders texte : `{{project_name}}`, `{{project_key}}`, `{{date}}`, `{{jql}}`,
`{{total_issues}}`, `{{total_story_points}}`, `{{avg_velocity}}`, `{{nb_sprints}}`,
`{{kpi:cycle_median}}`, `{{kpi:cycle_mean}}`, `{{kpi:cycle_p15}}`, `{{kpi:cycle_p85}}`,
`{{kpi:cycle_count}}`.

Chaque indicateur ci-dessus est un module indépendant dans `scripts/indicators/`
(`burnup.py`, `burndown.py`, `velocity.py`, `cycle_time.py`, `status_flow.py`,
`types.py`, `sprint_spread.py`) — voir `scripts/indicators/__init__.py` pour le
contrat exact.
**Ajouter un indicateur = ajouter un fichier dans `indicators/`, sans toucher
aux autres `.py`** : `fetch_jira.py` et `build_ppt.py` découvrent
automatiquement tout module qui expose `compute(issues, sprints, conf) -> dict`
(fusionné dans `metrics`) et/ou `RENDERERS: dict[str, callable]` (dispatch des
placeholders `{{chart:...}}`). Les deux sont indépendants et optionnels — un
module peut n'avoir que l'un des deux. `indicators/common.py` porte les helpers
partagés (parsing de date, percentiles...), exclu de la découverte automatique.
Les rendus « design agile » existants (`render_agile.py`) restent la
bibliothèque de dessin partagée, réutilisable depuis un nouveau module sans la
dupliquer ; `{{liste_sprints}}`, `{{liste_epics}}`, `{{kpi:*}}` et
`{{coach:synthese}}` restent gérés directement par `build_ppt.py`/`render_agile.py`
(sections de rapport, pas des indicateurs par graphique).

## Champs JIRA récupérés

Le script demande à la Search API : `issuetype`, `status`, `created`, `resolutiondate`,
`timespent`, `timeoriginalestimate`, `fixVersions`, `components`, `parent`, le champ
Story Points et le champ Sprint, plus l'historique des statuts (`expand=changelog`,
consommé uniquement par `{{chart:cumulative_flow_diagram}}` — non persisté dans
`data.json`, seules les métriques calculées le sont). `/search/jql` tronque cet
historique à une seule page par ticket (~40 entrées) ; `fetch_jira.py` récupère
le reste via un appel dédié (`/issue/{key}/changelog`, paginé) pour chaque
ticket tronqué — un peu plus lent sur un projet à tickets très remaniés, mais
nécessaire pour ne pas fausser le statut reconstruit. Les jours-homme (Conso), les cumuls burnup, la vélocité
et les percentiles de cycle time sont **calculés par le script** — pas récupérés.

Les sprints (nom, numéro, dates début/fin, état actif/clos/futur) viennent de l'**Agile
API** (`/rest/agile/1.0/board/{board_id}/sprint`). Sans `board_id`, le burnup et la
vélocité restent possibles mais sans dates de sprint.

## Template

Placer le template dans `templates/template.pptx` (créé neutre par le bootstrap
à partir de `scaffold/template.pptx` — à remplacer par sa propre charte). Le
skill **remplit les slides existantes** — il ne recrée pas la charte. Pour que le
remplissage fonctionne, chaque zone cible du template doit contenir un
placeholder texte `{{...}}` (voir table ci-dessus).

Aucun logo n'est requis : la slide de couverture réutilise telle quelle
l'image de fond déjà en place (si elle existe) sans rien exiger de plus, et
les en-têtes des slides de contenu (`shapes.add_header`, `render_agile._dark_header`)
se dessinent sans logo tant qu'aucun n'est fourni. Un logo reste possible —
`add_header`/`_dark_header` acceptent un `logo_media` (nom du fichier dans
`ppt/media/` de `template.pptx`, ex. `"image3.png"`) et l'insèrent
dynamiquement s'il existe, sans rien dessiner si le fichier est absent —
mais rien dans le pipeline n'en dépend par défaut.

`scripts/inspect_template.py` liste tous les placeholders détectés et les
emplacements de graphiques attendus — le lancer une fois pour vérifier que le
template est bien annoté.

## QA

`projects/<clé>/output/indicateurs.pptx` ci-dessous est dans le répertoire de
données (voir « Répertoire de données » plus haut), pas dans le repo skill.

**Environnement cloud (sandbox Linux, skill `pptx` public disponible) :**

Fichier :
```bash
python /mnt/skills/public/pptx/scripts/office/validate.py "<data>/projects/<clé>/output/indicateurs.pptx" --original "<data>/templates/template.pptx"
```

Placeholders restants (aucun ne doit subsister) :
```bash
markitdown "<data>/projects/<clé>/output/indicateurs.pptx" | grep -oE "\{\{[^}]+\}\}" && echo "PLACEHOLDERS RESTANTS" || echo "OK"
```

Visuel : convertir en images et inspecter (overflow, charts vides, alignement) :
```bash
python /mnt/skills/public/pptx/scripts/office/soffice.py --headless --convert-to pdf "<data>/projects/<clé>/output/indicateurs.pptx"
pdftoppm -jpeg -r 150 "<data>/projects/<clé>/output/indicateurs.pdf" slide && ls -1 "$PWD"/slide-*.jpg
```

**Poste local Windows (pas de `soffice`/`pdftoppm`/`markitdown`) :**

Placeholders restants — via `python-pptx`, en lisant chaque zone de texte et
cellule de tableau plutôt que la sortie `markitdown` (indisponible) :
```bash
python -c "
from pptx import Presentation
import re
pat = re.compile(r'\{\{[^}]+\}\}')
prs = Presentation('<data>/projects/<clé>/output/indicateurs.pptx')
found = []
for i, slide in enumerate(prs.slides, 1):
    for shape in slide.shapes:
        if shape.has_text_frame:
            found += [(i, m) for m in pat.findall(shape.text_frame.text)]
        if shape.has_table:
            for row in shape.table.rows:
                for cell in row.cells:
                    found += [(i, m) for m in pat.findall(cell.text)]
print('PLACEHOLDERS RESTANTS' if found else 'OK', found)
"
```

Visuel — via automation PowerPoint (`pywin32`, PowerPoint installé requis) :
```bash
python scripts/render_slides_windows.py <clé>
```
Exporte chaque slide en JPEG dans `projects/<clé>/output/slides/` (dossier
recréé à chaque appel) ; inspecter ensuite ces images (overflow, charts vides,
alignement). Éviter les chemins avec un segment de nom court Windows (`~1`) ou
très profondément imbriqués — l'automation PowerPoint échoue dessus.

## Dépendances

`requests`, `pyyaml`, `python-dotenv`, `python-pptx`, `pytest` (pip). Charts natifs
via python-pptx ; QA via les scripts du skill `pptx` public (environnement cloud)
ou, sur poste Windows local, `pywin32` + `scripts/render_slides_windows.py` (voir
« QA »). Tests unitaires des modules `indicators/` : `pytest tests/` depuis la
racine du skill.

## Historique / suivi

- `COACH_PROMPT.md` v2 : trois nouveaux champs `coaching` — `delta` (ce qui a
  bougé depuis la synthèse précédente), `questions` (0-3 questions de coach
  affichées sur une slide, distinctes des questions de session posées dans le
  chat) et `epics_lecture` (légende de `{{liste_epics}}`, qui n'en avait
  aucune). Nouveau script `scripts/coaching_history.py` (`archive`/`last`/
  `list`) : `data.json` étant réécrit en entier à chaque `fetch_jira.py`, la
  synthèse précédente doit être archivée à part (`projects/<clé>/output/
  coaching_history.json`, jamais touché par `fetch_jira.py`) pour que `delta`
  soit calculable — `archive` idempotent, purge au-delà de 12 entrées, tolère
  un fichier d'historique corrompu (repart d'un historique vide plutôt que de
  planter). Nouveau script `scripts/check_coaching.py` : valide les plafonds
  de longueur et cardinalités d'un coaching avant injection (seule source de
  vérité de ces plafonds : COACH_PROMPT.md, « Contraintes de rendu » — jamais
  recopiés ailleurs), distingue erreurs bloquantes et avertissements,
  importable (`validate_coaching`) et branché dans `set_coaching.py` juste
  avant l'injection atomique — une synthèse qui casserait le rendu à
  positions fixes est refusée à la source. Nouvelle slide « Décisions &
  questions » (`{{coach:decisions}}`, `render_agile.render_coach_decisions`) :
  rendue en deux colonnes (delta + questions) si `delta` est présent, en une
  colonne (questions seules, géométrie des cartes de recommandation
  réutilisée) sinon ; **retirée entièrement du PPT** (nouveau helper
  `build_ppt._remove_slide`, pas d'API dédiée en python-pptx) si `delta` et
  `questions` sont tous les deux absents — contrairement aux autres
  indicateurs, qui affichent un message de repli plutôt que de disparaître.
  Slide dupliquée dans les deux `template.pptx` (charte réelle + scaffold)
  depuis la slide `{{coach:synthese}}` via `scripts/duplicate_slide.py`.
  `/coach-refresh` archive désormais la synthèse en tout premier (avant le
  `fetch_jira.py` qui écraserait `data.json`) et valide avec
  `check_coaching.py` avant d'injecter.
- `{{chart:tempo_conso}}` ajouté (`indicators/tempo_conso.py`,
  `render_agile.render_tempo_conso`, `fetch_jira.py:fetch_tempo_worklogs`) :
  barres = conso Tempo (jh) par sprint, ligne (axe secondaire) = nb d'US
  terminées par sprint (rollup réutilisé tel quel depuis
  `indicators.burnup._build_rollup`, pas recalculé). API Tempo Cloud
  (`api.tempo.io/4/worklogs`, token dédié `TEMPO_API_TOKEN`/`TEMPO_NAME` dans
  `.env`) séparée de l'API Jira — pas d'endpoint « worklogs d'une liste
  d'issues » côté Tempo, donc `fetch_tempo_worklogs` récupère tous les
  worklogs de la période (bornée par `sprint_start_date`, paginée via
  `metadata.next`) et filtre côté client sur les ids du périmètre JQL.
  `conf["tempo_worklogs"]` (calculé une fois dans `fetch_jira.py:process`,
  pas un champ `project.yaml`) vaut `None` si le token est absent ou l'appel
  échoue (Tempo non installée sur ce projet) — dans ce cas l'indicateur
  affiche un message plutôt qu'un graphique vide, comme le CFD sans
  `workflow`. Piège rencontré : `startDate` d'un worklog Tempo est une date
  sans heure/fuseau ("YYYY-MM-DD") — comparée telle quelle aux dates JIRA
  (toujours "aware", suffixe `Z`) via `sprint_date_bucket`, ça lève
  `TypeError: can't compare offset-naive and offset-aware datetimes` ; fixé
  en complétant `T00:00:00Z` avant `parse_dt`.
- Le logo d'en-tête (`shapes.add_header`/`render_agile._dark_header`) est
  devenu **entièrement optionnel** : `logo_media` (nom du fichier dans
  `ppt/media/` de `template.pptx`) vaut `None` par défaut sur tous les
  appels du skill — aucun logo n'est requis dans `template.pptx`. Avant ce
  changement, un nom de média hardcodé (`"image3.png"`) était systématiquement
  recherché et son absence faisait planter tout `build_ppt.py` (`KeyError`
  dans `shapes.template_image_bytes`) ; `template_image_bytes` renvoie
  désormais `None` si le média manque, plutôt que de lever une exception.
- `{{chart:conso_corrective}}` ajouté (`indicators/conso_corrective.py`,
  `render_agile.render_conso_corrective`) : 100% empilé, jh consommés par mois
  (mois de `resolutiondate`) sur tickets terminés, en 4 catégories anomalie /
  incident / Us / US tech. Nouveaux champs `project.yaml` : `anomaly_types`,
  `incident_types`, `tech_types` (listes de noms de type JIRA exacts,
  `us_types` déjà existant réutilisé pour la catégorie "Us") — vides par
  défaut, donc l'indicateur est présent mais toujours à 0% tant qu'ils ne sont
  pas renseignés. Périmètre volontairement limité à ces 4 catégories (comme
  les indicateurs US-scopés qui ignorent déjà tout type hors `us_types`) :
  un ticket terminé dont le type n'apparaît dans aucune des 4 listes est
  exclu du graphique, pas de 5e bucket "Autre". Bornes de mois affichées :
  du mois de `sprint_start_date` (repris tel quel, pas de nouveau champ dédié)
  jusqu'au mois courant, tous les mois intermédiaires inclus même vides.
  Nouveau script réutilisable `scripts/duplicate_slide.py` (duplique une
  slide de template.pptx à partir de son placeholder, renumérote les pages)
  — voir CLAUDE.md, section « Ajouter un indicateur », pour la procédure
  complète désormais suivie à chaque nouvel indicateur.
- `{{chart:status}}` (`render_agile.render_status`) recoloré : dégradé clair
  -> foncé (au lieu d'une palette à 5 couleurs cycliques, qui pouvait donner
  la même couleur à deux statuts différents dès 6 statuts non-"attente" — cas
  réel sur le workflow à 8 statuts des projets du dépôt) ; statuts
  `done_statuses` (nouveau champ `done_statuses_us` calculé par
  `status_flow.compute()`, jamais deviné par le libellé) en vert. Même
  couleur dans la barre empilée et les cartes. Les statuts dont le segment
  est trop étroit pour leur libellé reçoivent désormais une étiquette externe
  au-dessus/en dessous de la barre (avec amorce), alternant de côté pour deux
  statuts étroits consécutifs — plus aucun statut ne reste sans étiquette
  visible.
- `{{chart:cumulative_flow_diagram}}` ajouté (`indicators/cumulative_flow_diagram.py`) :
  bandes empilées jour par jour à partir de l'historique des statuts
  (`expand=changelog` sur la Search API, complété si tronqué — voir « Champs
  JIRA récupérés »). Nécessite `workflow` configuré dans `project.yaml` (même
  champ que `{{chart:status}}`, mais ici pas de repli par fréquence si vide —
  l'indicateur est simplement absent). Les projets déjà fetchés avant ce
  changement doivent relancer `fetch_jira.py`/`/coach-refresh` pour obtenir le
  changelog nécessaire. Note d'implémentation : `expand` doit être une chaîne
  délimitée par des virgules sur `/search/jql` — une liste JSON (accepté sur
  l'ancien `/search`) y est rejetée en 400.
- Bloc `cfd:` (project.yaml, optionnel) ajouté pour le seul CFD : `groups`
  regroupe plusieurs statuts de `workflow` en une bande (lisibilité — un
  `workflow` à 8 statuts donne 8 bandes empilées, peu lisible), `start_date`/
  `end_date` bornent la fenêtre affichée. `{{chart:status}}` n'est pas
  affecté (garde le détail complet de `workflow`). Absent = comportement
  historique (une bande par statut, première US créée -> aujourd'hui). Les 4
  projets du dépôt utilisent désormais ce regroupement (3 bandes : À faire /
  En cours / Terminé) — voir leurs `project.yaml`.
- Les 3 skills relais historiques (`jira-fetch-data`, `jira-build-ppt`,
  `jira-project-report`) ont été retirés au profit des 3 commandes
  `/coach-refresh`, `/coach-ppt`, `/coach-ask` — seul point d'entrée désormais,
  aussi bien pour Claude Code que pour Codex (voir `scripts/sync_agents.py`).
- Calculs d'indicateurs extraits en modules indépendants dans `scripts/indicators/`
  (un fichier par indicateur, découverte automatique — voir « Indicateurs
  produits » plus haut). `scripts/fetch_jira.py` ne porte plus que
  l'extraction JIRA, l'assemblage de `metrics` et `build_epics` (table de
  rapport, pas un indicateur par graphique).
- Séries Story Points ajoutées sur `{{chart:burnup}}`, `{{chart:burndown}}`,
  `{{chart:velocity}}` — axe secondaire (droite), sans nouveau placeholder ni
  nouvelle slide. Champs ajoutés dans `metrics` : `added_sp`/`scope_cumul_sp`/
  `done_sp`/`done_cumul_sp` (burnup + tableau des sprints), `scope_sp`/
  `ideal_sp`/`real_sp` (burndown), `sp_engaged`/`sp_done` par sprint +
  `median_velocity_sp` (vélocité). Pas de projection de tendance SP pour le
  burnup (seulement les courbes cumulées). Rendu via un nouvel helper
  `render_agile._add_secondary_axis` (axId dédiés, distinct de
  `_add_combo_line`/`_add_combo_area` qui réutilisent l'axe primaire).
  Premier filet de tests du skill : `tests/` (pytest), sur les modules
  `indicators/burnup.py`, `burndown.py`, `velocity.py`.
- `{{chart:sprint_spread}}` ajouté (`indicators/sprint_spread.py`,
  `render_agile.render_sprint_spread`) : répartition des US terminées par
  nombre de sprints distincts traversés (champ Sprint JIRA, via
  `indicators/common.sprint_names`) — même construction visuelle que
  `{{chart:status}}` (barre empilée + cartes, dégradé clair -> foncé), pour
  repérer les US qui débordent sur plusieurs sprints.
- `{{chart:tempo_types}}` ajouté (`indicators/tempo_types.py`,
  `render_agile.render_tempo_types`) : barres empilées en volume absolu (jh),
  worklogs Tempo agrégés par mois du log (même bornes de mois que
  `{{chart:conso_corrective}}`), une série par type de ticket JIRA exact
  rencontré dans le périmètre — pas de regroupement en catégories fixes,
  contrairement à `{{chart:conso_corrective}}`. Chaque worklog Tempo porte
  désormais `issue_id` (`fetch_jira.py:fetch_tempo_worklogs`, en plus de
  `date`/`seconds`, déjà présents pour `{{chart:tempo_conso}}`) — nécessaire
  pour retrouver le type du ticket loggé via `issues`, un worklog sans
  correspondance étant classé "Inconnu" plutôt qu'ignoré. Nouvelle palette
  cyclique `style.TEMPO_TYPES_PALETTE` (nombre de types variable d'un projet
  à l'autre, pas de liste fixe de couleurs comme `CORRECTIVE_*`). Même
  dépendance Tempo que `{{chart:tempo_conso}}` (message de repli identique si
  `TEMPO_API_TOKEN` absent ou app Tempo indisponible).
