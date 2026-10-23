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
   `projects/<clé>/output/<AAAAMMJJ>-<clé>-indicateurs.pptx` — préfixe daté (format
   américain trié) sur la date de `generated_at` (date des données, pas du
   build : rebuilder sans refetch écrase le même fichier). C'est l'étape que
   fait `/coach-ppt` : elle ne réécrit la synthèse (étape 4) que si elle est
   encore absente du JSON.
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

**Filtre par indicateur (`ticket_filter`, project.yaml)** — chaque indicateur
peut surcharger la liste des types de tickets qu'il retient :
`ticket_filter: {<placeholder>: [types JIRA exacts]}` (clé = nom du
placeholder `{{chart:<clé>}}`, une clé couvre ses variantes `_NB`/`_SP`, et
`types` couvre aussi `types_conso`). Filtre en mémoire, après l'unique requête
`jql` — pas de requête JIRA supplémentaire. Liste vide = tous les tickets ;
clé absente = filtre historique de l'indicateur (`us_types` pour les
indicateurs US, tous les tickets pour les autres). Pour `conso_corrective` et
`defauts_*`, le filtre ne fait que restreindre les tickets en entrée — le
classement reste sur `anomaly_types`/`incident_types`/… Point d'entrée unique :
`indicators.common.ticket_types`/`filter_issues`. `{{liste_sprints}}` suit
`ticket_filter.burnup` (même rollup) ; `{{liste_epics}}` n'est pas concerné.

**Code couleur par type de ticket** — uniforme sur tous les indicateurs qui
distinguent les types (`{{chart:types}}`, `{{chart:types_conso}}`,
`{{chart:conso_corrective}}`, `{{chart:tempo_types}}`) : voir
`style.TICKET_TYPE_COLORS`/`style.type_color()` (US vert, US tech jaune,
Sous-tâche bleu clair, Epic bleu foncé, Anomalie orange, Travaux bleu marine,
Incident rouge ; type non reconnu -> gris neutre `TYPE_OTHER`). Les 3
indicateurs `{{chart:defauts_*}}` (« Anomalies & incidents ») ci-dessous
réutilisent les mêmes couleurs Anomalie/Incident, et les mêmes listes
`anomaly_types`/`incident_types` que `{{chart:conso_corrective}}` — mais un
calcul indépendant (`indicators/defauts_kpi.py`, `defauts_tendance.py`,
`defauts_delai_origine.py`, catégorisation partagée via
`indicators.common.defect_category`), jamais celui de `conso_corrective.py`
(4 catégories, périmètre différent — voir CLAUDE.md, « Ajouter un
indicateur »).

| Indicateur | Placeholder chart | Source |
|---|---|---|
| Burnup release (US) | `{{chart:burnup}}` | terminé cumulé vs périmètre cumulé US par sprint, + 3 courbes de tendance (pessimiste/médiane/optimiste) projetées depuis la fin du sprint en cours. Périmètre/terminé cumulés en Story Points en axe secondaire (droite) — pas de tendance SP. |
| Burndown sprint en cours (US) | `{{chart:burndown}}` | reste à faire jour par jour dans le sprint actif uniquement, vs droite idéale ; périmètre = US actuellement dans ce sprint (reports inclus). Reste à faire + droite idéale en Story Points en axe secondaire. |
| Vélocité / Engagement (US) | `{{chart:velocity}}` | engagé vs terminé par sprint (champ Sprint JIRA), + ligne médiane (sprints à 0 terminé exclus). Engagé/terminé en Story Points en axe secondaire (lignes, vs barres US). |
| Répartition statuts (US) | `{{chart:status}}` | count par statut — dégradé clair -> foncé dans l'ordre du `workflow`, statuts `done_statuses` en vert, statuts "en attente" en orange (même couleurs dans la barre et les cartes). Un statut avec un segment trop étroit pour son libellé reçoit une étiquette externe au-dessus/en dessous de la barre (deux statuts étroits consécutifs alternent de côté). |
| Cumulative Flow Diagram (US) | `{{chart:cumulative_flow_diagram}}` | bandes empilées, jour par jour, du nb d'US ayant atteint chaque statut du `workflow` configuré (ou un statut suivant) — nécessite `workflow` non vide dans `project.yaml` (contrairement à `{{chart:status}}`, pas de repli par fréquence : l'ordre doit refléter la vraie progression). Reconstruit à partir de l'historique des statuts (`changelog`, voir « Champs JIRA récupérés »). Regroupement des statuts et bornes de dates configurables via le bloc optionnel `cfd:` de `project.yaml` (voir `scaffold/project.example.yaml`) — utile quand `workflow` compte beaucoup d'étapes (bandes trop nombreuses pour rester lisibles). 4 encarts (Périmètre suivi, À faire, En cours, Terminé) — `todo`/`in_progress` distinguent la 1re étape du `workflow` (bloqué en amont) des étapes intermédiaires (réellement en cours), % du périmètre sous chaque compte. |
| Estimation vs consommé cumulés | `{{chart:cumul_estimation_conso}}` | 3 courbes cumulées jour par jour, du 1er ticket créé du périmètre à aujourd'hui : estimé (tous types hors Epic, `timeoriginalestimate`) et consommé (`timespent`) ajoutés à la date de **création** du ticket (pas sa résolution — choix délibéré pour rester comparable sur le même axe, voir Historique) ; estimation EPIC initiale = `timeoriginalestimate` porté par le ticket Epic lui-même (pas le rollup de ses enfants), ajouté à sa date de création — repère macro face au détail. Libellés : « Estimation des tickets », « Consommé des tickets », « Estimation EPIC initiale ». 4 encarts (Estimation des tickets, Consommé des tickets avec écart, Estimation EPIC initiale, Écart EPIC initiale/tickets). Totaux identiques à ceux de `{{liste_epics}}`. « Epic » est un type fixe, jamais paramétrable (même convention que `{{liste_epics}}`). |
| Types de tickets (nb) | `{{chart:types}}` | count par type (tous types), barres colorées par type (voir « Code couleur » ci-dessus) |
| Types de tickets (conso) | `{{chart:types_conso}}` | timespent en jh par type (tous types), % du total entre parenthèses après la valeur, barres colorées par type |
| Charge corrective (conso) | `{{chart:conso_corrective}}` | 100% empilé, jh consommés par mois (mois de `resolutiondate`) sur tickets terminés, ventilés en 6 catégories anomalie / incident / Us / US tech / Sous-tâche / Travaux (couleurs du code uniforme ci-dessus) — mapping par type de ticket exact via `anomaly_types`/`incident_types`/`tech_types`/`us_types`/`subtask_types`/`work_types` (config). Ticket terminé dont le type n'est dans aucune des 6 listes : exclu du graphique (pas de 7e bucket "Autre"). |
| Indicateurs clés · Qualité (anomalies/incidents) | `{{chart:defauts_kpi}}` | 8 cartes (créées, charge consommée, taux de défaut, backlog ouvert à date — × anomalie/incident), fenêtre = mois de `sprint_start_date` -> mois courant. Taux de défaut = jh de la catégorie ÷ jh total (tous types de tickets terminés sur la fenêtre, pas seulement anomalie/incident/Us/US tech comme `conso_corrective`). Créées/résolues (flux) et backlog ouvert (stock, sans limite d'ancienneté) ne sont pas additifs — voir `coaching.defauts_kpi_lecture`. |
| Anomalies & incidents · Tendance | `{{chart:defauts_tendance}}` | Par catégorie : créées/résolues par mois (barres, catégories `MM/AA`) + stock ouvert en fin de mois (ligne, axe secondaire) — approximation par `created`/`resolutiondate` seuls, pas de reconstruction par changelog. Graphique tronqué au premier mois avec activité (anomalie et incident peuvent démarrer à des mois différents) — la fenêtre complète reste dans `defauts_tendance`, seul l'affichage est raccourci. Sous les deux graphiques, ancienneté du backlog actuellement ouvert (tranches configurables via `defect_age_buckets`, project.yaml, défaut `[1, 7, 15, 30]` = 0-1j/2-7j/8-15j/16-30j/+30j). |
| Anomalies & incidents · Délai & origine | `{{chart:defauts_delai_origine}}` | À gauche : délai création -> résolution (jours calendaires, P15/médiane/moyenne/P85) comparé entre Incidents, Anomalies et Travaux (`work_types`, ligne affichée seulement si non vide — pas de 4e catégorie US, échelles trop différentes, cf. Historique). À droite : origine par **ticket parent** (champ JIRA `parent`, tel que fourni par l'API — pas de résolution du parent dans le périmètre JQL), tickets créés sur la fenêtre, top 6 + "Autres" (au-delà du top) + "Sans parent" (si non nuls). |
| Conso Tempo vs US terminées | `{{chart:tempo_conso}}` | barres : conso Tempo (jh, worklogs agrégés par sprint via leur date de log) ; ligne (axe secondaire) : nb d'US terminées par sprint. Nécessite Tempo installé sur le projet **et** `TEMPO_API_TOKEN`/`TEMPO_NAME` dans `.env` (voir « Configuration ») — absent des deux : message "Données Tempo JIRA non disponibles" à la place du graphique, jamais de graphique vide. |
| Temps Tempo par type de ticket (conso) | `{{chart:tempo_types}}` | barres empilées en volume absolu (jh), worklogs Tempo agrégés par mois du log — une série par type de ticket JIRA exact rencontré (tous types, pas de regroupement), triées par jh décroissant, couleurs du code uniforme ci-dessus. Même dépendance Tempo que `{{chart:tempo_conso}}` (même message si absent). |
| Lead time (US) | `{{chart:cycle_time}}` | P15 / médiane / moyenne / P85 — affiché « Lead time » (création -> résolution), pas « Cycle time » : voir Historique. Champ/placeholder JSON inchangés (`cycle_time`, `{{kpi:cycle_*}}`). |
| Répartition par nombre de sprints (US) | `{{chart:sprint_spread}}` | US terminées, groupées par nombre de sprints distincts traversés (champ Sprint JIRA) — dégradé clair (1 sprint) -> foncé (le plus de sprints). US sans sprint renseigné exclues (rien à mesurer). Encart rose « Temps de cycle d'un ticket » (`sprint_cycle_time`) : médiane + P15/P85 (jours calendaires) de l'entrée en sprint (plus tardif de : 1re affectation à un sprint, début du 1er sprint) au 1er passage dans un `done_statuses`, US terminées seulement. |
| Évolution du temps de cycle par sprint (US) | `{{chart:sprint_cycle_trend}}` | P15 / médiane / P85 du temps de cycle (même mesure que l'encart de `{{chart:sprint_spread}}` : entrée en sprint -> 1er `done_statuses`) par **sprint d'entrée**. Point orange = sprint avec des US entrées pas encore terminées (valeur biaisée vers le bas). Légende coach `sprint_cycle_trend_lecture`. |
| Dispersion par étape (US) | `{{chart:dispersion_etapes}}` | Boîtes à moustaches (p10/p25/médiane/p75/p90, en jours) du temps passé par statut du `workflow` configuré — reconstruit via changelog (`indicators.common.status_timeline`, partagé avec `{{chart:cumulative_flow_diagram}}`). Seuls les intervalles clos (statut réellement quitté) sont mesurés, et seulement ceux d'au moins `dispersion_etapes.min_transition_seconds` (project.yaml, défaut 300s = 5 min) — filtre les transitions quasi instantanées (automatisation JIRA à la création, pas un vrai temps passé, voir Historique). Les statuts terminaux (`done_statuses`, même champ que `{{chart:cycle_time}}`) sont **toujours exclus**, même s'ils ont des échantillons (ticket réouvert puis re-sorti) — le temps passé dans un statut terminal n'a pas de lecture agile utile. Couleur par statut = couleur de **groupe** `cfd.groups` (même config, mêmes couleurs que le CFD — `render_agile._cfd_palette`), jamais une palette propre à cette slide ; `cfd.groups` absent -> repli un groupe par statut (dégradé, comme le CFD sans regroupement). Échelle de l'axe dérivée du **p75 maximum** (pas du p90) — la boîte p25-p75 tient donc toujours entière ; une moustache p90 qui dépasse est coupée au bord (flèche + valeur réelle affichée juste après, sur la même ligne), plutôt que d'étirer l'axe entier sur un seul outlier (voir Historique). Valeur médiane affichée sous la boîte, centrée sur le trait médian. Nécessite `workflow` non vide (sinon absent, comme le CFD). |
| Où passe le temps, étape par étape (US) | `{{chart:temps_par_etape}}` | Même mesure de base que `{{chart:dispersion_etapes}}` (intervalles clos, seuil `min_transition_seconds`, statuts terminaux exclus — calcul partagé via `indicators.common.status_durations`) mais réduite à la **médiane** par statut, cumulée dans l'ordre du `workflow` pour reconstituer un parcours type de la création à la livraison. Deux barres empilées alignées sur le même axe cumulatif : une barre macro par groupe `cfd.groups` (couleurs identiques au CFD) et une barre détaillée par statut (teintes dégradées au sein du groupe). Sous les barres, une carte par statut (numérotée, médiane + « N passages mesurés » — **pas** « N tickets » : un ticket qui repasse par le même statut lors d'un aller-retour dans le workflow y contribue un échantillon par visite, voir Historique) regroupée par section `cfd.groups`. Texte fixe de méthodologie sous le titre (pas une légende coach) et rappel en pied de slide que les médianes ne s'additionnent pas exactement. `cfd.groups` absent -> repli un groupe par statut, comme le CFD. Nécessite `workflow` non vide. |
| Débit par étape (US) | `{{chart:debit_etapes}}` | Sur les `debit_etapes.window_sprints` derniers sprints **clos** (défaut 3, sprint actif exclu ; sans sprint clos : les `window_sprints × sprint_duration_days` derniers jours), par statut du `workflow` : entrées et sorties **par sprint** (colonnes groupées), puis sous chaque colonne le stock en fin de fenêtre, son évolution, la couverture (stock ÷ sorties par sprint = sprints pour le vider) et les **retours** (entrées venant d'un statut plus avancé = retravail). Le statut dont le stock a le plus augmenté est mis en évidence (orange) ; le rail l'annonce avec l'étape **aval** comme goulot probable, plus arrivées -> livrées par sprint. Même reconstruction par changelog et même seuil de bruit que `{{chart:dispersion_etapes}}` (`min_transition_seconds` : une visite plus courte est ignorée, ses voisines fusionnées) ; statuts terminaux exclus des colonnes, comptés en « livrées ». Nécessite `workflow` non vide. |
| Tableau des sprints (US) | `{{liste_sprints}}` | table native : ajouts/terminés par sprint, cumuls (nb + jh) |
| Tableau des epics | `{{liste_epics}}` | table native : par epic, Estim. EPIC initiale (`timeoriginalestimate` de l'Epic lui-même, détail des enfants dans `detail_estimate_jh`), Conso (tickets rattachés, directement ou via leur parent : sous-tâche -> US -> Epic), RAF théo ; ligne « Sans EPIC » toujours affichée. Totaux alignés sur `{{chart:cumul_estimation_conso}}` (même population `ticket_filter.cumul_estimation_conso`) ; avancement/projection sur toutes les US du périmètre ; bandeau légende (`coaching.epics_lecture`, optionnel) sous le tableau — tableau à hauteur réduite quand présent, hauteur d'origine sinon (jamais de trou) |
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

`projects/<clé>/output/<AAAAMMJJ>-<clé>-indicateurs.pptx` ci-dessous est dans le
répertoire de données (voir « Répertoire de données » plus haut), pas dans le
repo skill — nom daté sur `generated_at` (voir « Workflow », étape 5) :
remplacer `<AAAAMMJJ>` par la date affichée par `build_ppt.py` en sortie, ou
prendre le plus récent (`ls -1 <data>/projects/<clé>/output/*-indicateurs.pptx | sort | tail -1`).

**Environnement cloud (sandbox Linux, skill `pptx` public disponible) :**

Fichier :
```bash
python /mnt/skills/public/pptx/scripts/office/validate.py "<data>/projects/<clé>/output/<AAAAMMJJ>-<clé>-indicateurs.pptx" --original "<data>/templates/template.pptx"
```

Placeholders restants (aucun ne doit subsister) :
```bash
markitdown "<data>/projects/<clé>/output/<AAAAMMJJ>-<clé>-indicateurs.pptx" | grep -oE "\{\{[^}]+\}\}" && echo "PLACEHOLDERS RESTANTS" || echo "OK"
```

Visuel : convertir en images et inspecter (overflow, charts vides, alignement) :
```bash
python /mnt/skills/public/pptx/scripts/office/soffice.py --headless --convert-to pdf "<data>/projects/<clé>/output/<AAAAMMJJ>-<clé>-indicateurs.pptx"
pdftoppm -jpeg -r 150 "<data>/projects/<clé>/output/<AAAAMMJJ>-<clé>-indicateurs.pdf" slide && ls -1 "$PWD"/slide-*.jpg
```

**Poste local Windows (pas de `soffice`/`pdftoppm`/`markitdown`) :**

Placeholders restants — via `python-pptx`, en lisant chaque zone de texte et
cellule de tableau plutôt que la sortie `markitdown` (indisponible) :
```bash
python -c "
from pptx import Presentation
import re
pat = re.compile(r'\{\{[^}]+\}\}')
prs = Presentation('<data>/projects/<clé>/output/<AAAAMMJJ>-<clé>-indicateurs.pptx')
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

- 2026-10-23 — Nouvelle slide **`{{chart:debit_etapes}}`** (« Débit par étape »,
  demande explicite : voir le goulot d'étranglement du workflow). Question de
  départ : le CFD ne donne le débit qu'entre 3 groupes, pas statut par statut.
  Calcul (`indicators/debit_etapes.py`) : entrées/sorties par statut sur les
  `debit_etapes.window_sprints` derniers sprints clos (nouveau champ
  `project.yaml`, défaut 3), stock début/fin, couverture (stock ÷ sorties par
  sprint) et **retours** (entrées depuis un statut plus avancé). Choix tranchés
  en session :
  - le statut mis en évidence est la **file qui grossit** (plus forte hausse de
    stock), le goulot annoncé est l'étape **aval** — pas la file elle-même ;
  - même seuil de bruit que `dispersion_etapes` (`min_transition_seconds`) :
    une visite plus courte est retirée et ses voisines identiques fusionnées,
    sinon un aller-retour automatique crée une fausse sortie/réentrée ;
  - sprint actif exclu de la fenêtre (partiel, COACH_PROMPT.md §1.5).
  Rendu (`render_agile.render_debit_etapes`) : colonnes groupées
  entrées/sorties par sprint, rangée stock/évolution/couverture/retours
  alignée sur les colonnes, rail (file qui grossit + étape aval, arrivées ->
  livrées par sprint, lecture coach `debit_etapes_lecture`, 200 car.). Insérée
  juste après `{{chart:temps_par_etape}}` dans les deux `template.pptx`. QA
  réelle sur NOS (S24 -> S26) : « À faire » passe de 13 à 38 US (16 entrées
  pour 7,7 sorties par sprint), et 16 des 40 entrées en « En cours » sont des
  retours. Retour QA intégré : libellé de la carte d'alerte raccourci (« File
  qui grossit ») et carte arrivées/livrées en grand nombre compact, qui
  passaient sur 2 lignes.

- 2026-10-02 — `{{liste_epics}}` aligné sur `{{chart:cumul_estimation_conso}}`
  (demande explicite, NOS : 1 182 jh « estimé Epics » d'un côté, 1 330 jh
  « Estim. » de l'autre, jugé confusant). Choix tranchés en session :
  - **Estim. EPIC initiale** par ligne = estimation portée par l'Epic
    elle-même (plus le rollup de ses enfants, conservé en
    `detail_estimate_jh`) — les Epics créées sans chiffrage macro affichent 0
    et un RAF théo négatif, c'est voulu ;
  - **Consommé** total = celui de `cumul_estimation_conso` (tous les tickets
    non-Epic de la même population) ; ligne « Sans EPIC » (`epics.no_epic`)
    pour que la somme des lignes retombe sur le total. Sous-tâches désormais
    rattachées à l'Epic de leur ticket parent (auparavant ignorées) ;
  - **avancement** et **projection théorique** sur toutes les US du
    périmètre, y compris sans EPIC ; prévisibilité calculée contre
    l'estimation EPIC initiale ;
  - libellés de `cumul_estimation_conso` : « Estimation des tickets »,
    « Consommé des tickets », « Estimation EPIC initiale ».

- 2026-10-02 — `ticket_filter` par indicateur (project.yaml) : remplace les
  filtres de type codés en dur (`us_types` ou aucun) par une liste
  paramétrable par placeholder, filtrée en mémoire (choix explicite : pas une
  requête JQL par indicateur). Clé absente = comportement antérieur à
  l'identique (vérifié sur NOA et NOS : `build_metrics` ancien vs nouveau code,
  même JSON). Liste vide = tous les tickets. Sur `conso_corrective`/`defauts_*`,
  restriction d'entrée seulement, classement inchangé. `tempo_types` avec
  filtre écarte les worklogs des tickets exclus (au lieu de les ranger en
  « Inconnu ») ; `tempo_conso` filtre les worklogs par type, ses « US
  terminées » suivent `ticket_filter.burnup`. `common.status_durations` ne
  prend plus `us_types` (l'appelant passe des tickets déjà filtrés).
- Nom du PPT généré : la clé projet s'insère après la date,
  `<AAAAMMJJ>-<clé>-indicateurs.pptx` (ex. `20260930-NOS_R2.1-indicateurs.pptx`)
  — demande explicite, pour distinguer les fichiers une fois sortis de leur
  dossier `projects/<clé>/output/`. Les anciens `<AAAAMMJJ>-indicateurs.pptx`
  restent en place (jamais renommés) ; `render_slides_windows.py` trie sur le
  préfixe date puis sur la date de modification pour prendre le plus récent
  quel que soit le format.
- Nouvelle slide **`{{chart:cumul_estimation_conso}}`** (« Estimation vs
  consommé cumulés ») — demande explicite : voir 3 courbes cumulées jour par
  jour (estimé/consommé hors Epic, estimé Epics). Choix de conception tranchés
  en session (voir `indicators/cumul_estimation_conso.py`) :
  - granularité **jour par jour**, comme `{{chart:cumulative_flow_diagram}}`,
    plutôt que par sprint (`{{chart:burnup}}`) ou par mois
    (`{{chart:conso_corrective}}`) ;
  - le **consommé** (`timespent`) est ajouté à la date de **création** du
    ticket, pas à sa résolution — même date que la courbe estimé, pour rester
    directement comparables sur le même axe. Conséquence assumée : le
    consommé affiché à une date donnée peut inclure du temps réellement loggé
    plus tard sur un ticket créé plus tôt (contrairement à
    `{{chart:burnup}}`/`{{chart:conso_corrective}}`, dont le consommé suit la
    résolution) — réserve de lecture portée par
    `cumul_estimation_conso_lecture` (COACH_PROMPT.md), pas seulement cette
    note ;
  - périmètre **tous types sauf Epic** (lecture littérale de la demande),
    pas seulement `us_types` — peut compter en double une sous-tâche et son
    US parente si les deux portent une estimation propre ;
  - l'estimé Epics vient du champ `timeoriginalestimate` de l'Epic
    **lui-même**, pas d'un rollup de ses enfants — à l'époque couvert par
    `epics.total_estimate_jh` (`fetch_jira.py:build_epics`) ; depuis le
    2026-10-02, `build_epics` reprend lui aussi l'estimation de l'Epic
    elle-même (voir entrée correspondante).
  Aucun nouveau champ `project.yaml` (réutilise `seconds_per_day`) ; « Epic »
  reste un type fixe, jamais paramétrable, comme dans `build_epics`. Insérée
  juste après `{{chart:cumulative_flow_diagram}}` dans les deux
  `template.pptx`. QA réelle sur NOS : `fetch_jira.py`/`build_ppt.py` OK, 579
  jours affichés (17/02/2025 -> aujourd'hui), écart estimé Epics/détail et
  écart conso/estimé cohérents avec `data.json`.

- **`{{chart:temps_par_etape}}`** — correction de libellé (question utilisateur sur la
  gestion des allers-retours dans le workflow, ex. À faire -> En cours -> Attente
  validation PO -> En cours -> Attente validation PO). Vérifié : l'algorithme
  (`indicators.common.status_durations`) mesure bien **chaque visite séparément** —
  aucune fusion, aucune perte, un ticket qui repasse par un statut y ajoute un
  échantillon par passage. Mais la carte affichait « sur N tickets qui y passent »
  alors que N (`items[].count`) compte des **passages**, pas des tickets distincts —
  diagnostic réel sur NOS : « En cours » comptait 297 passages pour seulement 234
  tickets distincts (63 tickets y étaient repassés au moins une fois, ex. LMO-3009
  deux fois). Corrigé en « N passages mesurés » (`render_agile.render_temps_par_etape`).
  `us_count` (pied de slide), lui, était déjà un vrai compte de tickets distincts —
  resté inchangé. Tests ajoutés dans les deux indicateurs
  (`test_oscillation_counts_each_visit_separately`) prouvant qu'un aller-retour
  produit bien 2 échantillons distincts (médiane de [1j, 4j] = 2,5j), pas 1 seul
  fusionné.

- Nouvelle slide **`{{chart:temps_par_etape}}`** (« Où passe le temps, étape par
  étape ») — pensée « dans le même esprit » que `{{chart:dispersion_etapes}}`
  (demande explicite) : même mesure de base (temps passé par statut,
  intervalles clos, seuil de bruit) mais réduite à la **médiane** et
  **cumulée** dans l'ordre du workflow, pour lire un parcours type plutôt
  qu'une dispersion. Calcul par statut (`indicators/temps_par_etape.py`)
  quasi identique à `dispersion_etapes.py` — l'agrégation commune
  (intervalles clos, seuil `min_transition_seconds`, résolution des noms)
  a été **promue dans `indicators.common.status_durations`**
  (`(durations, contributors)`), `dispersion_etapes.py` retouché pour la
  consommer au lieu de sa boucle privée — comportement inchangé, tests
  existants toujours au vert après coup. Insérée juste après
  `{{chart:dispersion_etapes}}` dans les deux `template.pptx`. Pas de
  nouveau champ `project.yaml` : réutilise `workflow`/`cfd.groups`/
  `done_statuses`/`dispersion_etapes.min_transition_seconds` tels quels (ce
  dernier champ, malgré son nom, est désormais partagé par les deux
  indicateurs — même notion de bruit d'automatisation, pas de raison d'en
  dupliquer un second).
  Rendu (`render_agile.render_temps_par_etape`) : texte de méthodologie
  **fixe** sous le titre (pas une légende coach — décrit comment lire la
  slide, toujours la même quel que soit le projet, contrairement aux autres
  indicateurs qui n'ont pas de texte d'intro fixe) ; deux « brackets »
  (traits + embouts) au-dessus des barres annonçant le total et le sous-total
  « Dont <2e groupe> » (tout ce qui suit le 1er groupe affiché — générique,
  ne suppose jamais que ce groupe s'appelle « En cours ») ; barre macro
  (une bande par groupe `cfd.groups`, couleurs `_cfd_palette` identiques au
  CFD) et barre détail (une bande par statut, teintes `_shade_gradient` —
  clair -> couleur du groupe, nouvelle fonction) empilées sur le **même axe
  cumulatif** (0 -> somme des médianes) pour que les frontières des deux
  barres s'alignent visuellement. Cartes de statut : nouvelle fonction
  compacte `_step_card` (badge, nom, médiane, nb de tickets, filet
  d'accent) — `_card_stat` existant (généreusement dimensionné pour une
  poignée de cartes pleine hauteur) s'est révélé beaucoup trop haut pour 7
  cartes réparties sur 2 rangées, provoquant un chevauchement massif de tout
  le bas de la slide en QA réelle (label/grande valeur/légende superposés
  dans chaque carte) — piège vécu, corrigé par une carte dédiée plutôt que
  de forcer `_card_stat` dans un espace trop petit. Pied de slide : rappel
  fixe que les médianes ne s'additionnent pas exactement (la médiane d'une
  somme n'est pas la somme des médianes), puis `coaching.temps_par_etape_lecture`
  optionnelle en dessous.
  **Piège vécu (budget vertical)** : le premier jet sous-estimait largement
  la hauteur nécessaire aux 2 barres + brackets + axe + 2 sections de cartes
  + pied, dans les 800 px de `CONTENT_H` — chevauchements en cascade
  (libellés de barre détail repliés sur 2 lignes faute de largeur, faisant
  déborder la barre sur l'axe ; brackets trop proches l'un de l'autre et de
  la barre macro ; pied de page chevauchant la légende coach). Corrigé par
  deux changements distincts, pas un seul : (1) une carte compacte dédiée
  (`_step_card`, voir ci-dessus) au lieu de `_card_stat`, et (2) un contrôle
  de largeur réel (`_text_w_px`) avant d'afficher un libellé dans une bande
  de la barre détail — au lieu d'un seuil de largeur fixe arbitraire — avec
  repli sur la valeur seule (alignée à la même hauteur que le cas à 2
  lignes, pour ne pas décrocher visuellement les bandes trop étroites de
  leurs voisines) plutôt qu'aucun texte.
- **`{{chart:dispersion_etapes}}`** — retouche d'affichage (retour QA réel) :
  le libellé de moustache coupée (p90 hors échelle) était décalé en haut à
  droite de la barre, désolidarisé visuellement d'elle ; recentré sur l'axe
  vertical de la barre (`track_y`), juste après la flèche. La valeur
  médiane, jusque-là dans une colonne à droite de toute la ligne, est
  descendue **sous la boîte**, centrée sur le trait médian — cohérent avec
  la maquette de référence (`{{chart:temps_par_etape}}` ci-dessus, pensé
  dans le même esprit visuel).
- Nouvelle slide **`{{chart:dispersion_etapes}}`** (« Dispersion par étape ») :
  boîtes à moustaches du temps passé par statut, insérée juste après
  `{{chart:sprint_spread}}` dans les deux `template.pptx`. Calcul
  (`indicators/dispersion_etapes.py`) réutilise le changelog déjà exploité par
  `{{chart:cumulative_flow_diagram}}` — `status_timeline`/`resolve_status_names`
  (reconstruction de la progression + résolution des statuts renommés via
  leur id) et `status_group_map` (mapping statut -> groupe `cfd.groups`) ont
  été **promus dans `indicators/common.py`**, `cumulative_flow_diagram.py`
  retouché pour les consommer au lieu de dupliquer son ancienne logique
  privée (`_status_timeline`, `_stage_labels_and_map`) — comportement
  inchangé, tests CFD existants toujours au vert après coup. Seuls les
  intervalles **clos** (statut réellement quitté) sont mesurés — un
  intervalle encore ouvert biaiserait la distribution vers le bas, même choix
  que `{{chart:cycle_time}}` qui ne porte que sur les éléments terminés
  (COACH_PROMPT.md §4.5). Les statuts terminaux (`done_statuses`) sont
  **exclus explicitement** de la slide, pas seulement absents faute
  d'échantillon : un ticket réouvert (repasse par un statut terminé puis en
  ressort) produit bien des intervalles clos mesurables, vus en réel sur le
  projet NOS (11 US) — exclus quand même, le temps passé dans un statut
  terminal n'ayant pas de lecture agile utile (retour explicite après la
  1re QA réelle, où « Terminé(e) » apparaissait sur la slide). Couleur par
  statut = couleur de **groupe** `cfd.groups`
  (`render_agile._cfd_palette`, mêmes couleurs que le CFD pour ces mêmes
  groupes — jamais une palette propre à cette slide, demande explicite : ne
  pas reprendre les couleurs de la maquette fournie en référence) ; `cfd.groups`
  absent -> repli un groupe par statut (`status_group_map`), dégradé clair ->
  foncé comme le CFD sans regroupement. Rendu (`render_agile.render_dispersion_etapes`)
  calqué sur le box-plot déjà existant de `render_defauts_delai_origine`
  (`_nice_step` réutilisé tel quel pour l'échelle de l'axe) mais avec de
  vraies moustaches p10/p90 (trait + embouts) en plus de la boîte p25/p75 et
  du trait médian, et en pleine largeur (pas de rail latéral, une ligne par
  statut plutôt que 2-3 catégories). QA réelle faite d'abord avec un
  `data.json` synthétique (percentiles fabriqués, injectés sur un projet réel
  déjà fetché) plutôt qu'un nouveau fetch JIRA — pas de nouveau champ
  `project.yaml` nécessaire (réutilise `workflow`/`cfd.groups`, déjà
  récupérés par le fetch existant), donc rien à re-fetcher pour valider le
  rendu.
  **Piège vécu, corrigé après coup sur de vraies données (projet NOS)** :
  l'échelle de l'axe calée sur `max(p90)` de tous les statuts (comme
  `render_defauts_delai_origine`, qui ne compare que 2-3 catégories) explose
  dès qu'un seul statut a un p90 très étiré — vu en réel, « Bac à sable »
  (statut amont, backlog) avait un p90 = 133 j contre ≤ 70 j pour tous les
  autres statuts, poussant l'axe entier à 150 j et écrasant tous les statuts
  de flux actif (« En cours », attentes...) dans les 20 premiers pixels,
  illisibles. Corrigé : l'axe est calé sur **`max(p75)`**, pas `max(p90)` — la
  boîte p25-p75 (ce qui porte le signal d'instabilité) tient donc toujours
  entière, et seule la moustache p90 d'un statut aberrant est coupée au bord
  du graphique (`xpos()` la plafonne), signalée par une flèche
  (`MSO_SHAPE.ISOSCELES_TRIANGLE` pivotée 90°) et sa vraie valeur affichée en
  petit texte à côté — jamais silencieusement tronquée. Une note globale
  (« → p90 réel au-delà de l'échelle affichée ») apparaît une seule fois,
  en haut à droite du graphique, dès qu'au moins une ligne est coupée,
  plutôt que de répéter « p90 » sur chaque étiquette. Choix (troncature +
  flèche) tranché avec l'utilisateur parmi plusieurs options (exclure le
  backlog du graphique, échelle logarithmique, ne rien changer) — retenu
  pour garder toutes les étapes visibles sur une échelle linéaire lisible,
  sans perdre l'information du p90 réel.
  **2e piège vécu, même QA réelle (NOS)** : une médiane « Bac à sable » à
  0,3 j puis « Affinage métier » à 0 j (exactement) ont semblé suspects à
  l'utilisateur — diagnostic ponctuel en interrogeant JIRA en direct (lecture
  seule, script jetable, `data.json` ne stocke que les métriques agrégées,
  pas les issues brutes) : sur « Affinage métier », **61 % des intervalles
  clos duraient moins de 10 secondes** (ex. entrée 16:25:34, sortie 16:25:38)
  — signature d'une règle d'automatisation JIRA à la création (étalée sur 16
  mois de données, pas une migration ponctuelle), pas un vrai temps de
  travail. Calcul et récupération JIRA corrects, aucun bug — mais ce bruit
  dominait la médiane et masquait le signal réel (traîne à plusieurs mois sur
  une partie des tickets). Fix : nouveau champ optionnel `project.yaml`
  (bloc `dispersion_etapes`) **`min_transition_seconds`** (défaut 300 = 5
  min, choisi après comparaison de plusieurs seuils sur les chiffres réels
  du projet, tranché avec l'utilisateur) — un intervalle clos plus court est
  ignoré, ni compté dans les percentiles ni dans `us_count`. Toujours pas de
  fetch JIRA nécessaire pour ce fix (le seuil s'applique au calcul, pas à la
  récupération) — seul le diagnostic l'a requis, ponctuellement.
- Retours d'usage sur les 3 slides « Anomalies & incidents » (voir entrée
  suivante), pris en compte ensemble :
  - **Palette d'ancienneté du backlog** (`_age_severity_palette`,
    `render_agile.py`) refaite en dégradé **multi-stops** (`ALERT_BG` ->
    `ALERT_BORDER` -> `BRAND_ACCENT` -> `ALERT_TEXT`, rose pâle -> rouge) —
    un dégradé à 2 points sur 5 tranches donnait des tons médians trop
    proches (8-15j quasi indiscernable de 16-30j en retour d'usage).
  - **`{{chart:defauts_delai_origine}}`** : hauteur de ligne plafonnée
    (`ROW_H_MAX`) au lieu d'étirer les 2-3 lignes sur tout l'espace
    disponible — l'axe se retrouvait trop loin sous les lignes, et le
    libellé du délai médian (ancré en haut de ligne) semblait décroché de sa
    propre barre. Le libellé est maintenant ancré à `track_y` (le centre de
    la barre), plus au sommet de la ligne. Nouvelle 3e catégorie **Travaux**
    (`work_types`, project.yaml — champ partagé avec le nouveau bucket
    `travaux` de `{{chart:conso_corrective}}` ci-dessous), affichée
    seulement si elle a des tickets résolus. Origine passée de
    « par composant » à **« par ticket parent »** (`parent.fields.summary`,
    fourni directement par l'API JIRA — abandon de l'approche par
    `components`, qui datait de la première version) ; nom du parent tronqué
    à 42 caractères (un intitulé long faisait déborder sa ligne sur 3 lignes
    dans une grille à hauteur fixe).
  - **`{{chart:defauts_tendance}}`** : légende du graphique en position
    « bottom, hors mise en page » (`include_in_layout=False`) — sur ces
    mini-graphiques (moitié moins hauts qu'un graphique pleine largeur), la
    fraction basse historique (`h_frac` 0.72) ne laissait pas assez de place
    entre les libellés d'axe et la légende, qui se chevauchaient ; réduite à
    0.62.
  - **`{{chart:conso_corrective}}`** — **modifié** (l'indépendance annoncée
    dans l'entrée suivante ne concerne que le calcul des 3 nouveaux
    indicateurs, pas une interdiction absolue) : 2 nouvelles catégories,
    **Sous-tâche** (`subtask_types`, couleur `TYPE_SUBTASK` existante) et
    **Travaux** (`work_types`, voir ci-dessus). `total_jh`/`corrective_pct`
    recalculés automatiquement (génériques sur `CATEGORIES`, aucune
    autre modification nécessaire dans `compute()` au-delà de la liste et de
    `_category()`). `style.TYPE_WORK` changée de violet à **bleu marine**
    (`0x0B2D4A`, distinct de `TYPE_EPIC` 0x1F4E79) — effet de bord assumé sur
    `{{chart:types}}`/`{{chart:types_conso}}`/`{{chart:tempo_types}}`, qui
    partagent le même code couleur uniforme (voir plus haut).
  - **Libellé « Lead time »** (pas « Cycle time ») sur `{{chart:cycle_time}}`
    et la carte correspondante de `{{chart:kpi:*}}` (« Indicateurs clés ») :
    la donnée sous-jacente (`metrics["cycle_time"]`, création ->
    résolution) est un lead time, pas un cycle time (qui mesurerait depuis
    le 1er passage en statut « En cours »). Changement d'intitulé affiché
    uniquement — champs/placeholders JSON (`cycle_time`,
    `{{chart:cycle_time}}`, `{{kpi:cycle_*}}`) inchangés ; un vrai cycle
    time (via changelog) est envisagé comme indicateur séparé plus tard.
- 3 nouvelles slides « Anomalies & incidents » ajoutées :
  `{{chart:defauts_kpi}}` (`indicators/defauts_kpi.py`,
  `render_agile.render_defauts_kpi`), `{{chart:defauts_tendance}}`
  (`indicators/defauts_tendance.py`, `render_defauts_tendance`),
  `{{chart:defauts_delai_origine}}` (`indicators/defauts_delai_origine.py`,
  `render_defauts_delai_origine`) — insérées juste après
  `{{chart:conso_corrective}}` dans les deux `template.pptx`. Catégorisation
  anomalie/incident partagée (`indicators.common.defect_category`,
  `anomaly_types`/`incident_types` de `project.yaml`, réutilisés tels quels)
  mais calcul entièrement indépendant de `conso_corrective.py` (`compute()`
  distinct, aucune dépendance croisée — `conso_corrective.py` a depuis été
  étendu séparément, voir l'entrée ci-dessus, sans lien avec ce choix
  d'indépendance) — voir « Code couleur par type de ticket » plus haut pour le
  détail des définitions (fenêtre, taux de défaut, non-additivité
  créées/résolues/backlog). Nouveau champ `project.yaml` optionnel
  `defect_age_buckets` (défaut `[1, 7, 15, 30]`, 5 tranches d'ancienneté du
  backlog ouvert : 0-1j/2-7j/8-15j/16-30j/+30j). Nouveaux helpers partagés
  dans `indicators/common.py` : `defect_category`, `month_key`/`month_range`
  (repris du pattern de `conso_corrective.py`, promus en commun plutôt que
  dupliqués 3 fois), `age_bucket_labels`/`age_bucket_index`.
  `{{chart:defauts_tendance}}` : catégories au format `MM/AA` (pas
  `JJ/MM/AAAA`) et graphique tronqué au premier mois avec activité par
  catégorie (anomalie et incident peuvent démarrer à des mois différents) —
  QA réelle ayant montré un axe encombré de mois vides en tête. Plot area
  réduite (`h_frac` 0.62 au lieu de 0.72 comme sur les graphiques pleine
  largeur) sur ces mini-graphiques deux-par-slide : à hauteur égale en
  fraction, leur hauteur absolue plus faible laissait la légende chevaucher
  les libellés d'axe. `{{chart:defauts_delai_origine}}` compare le délai
  Incidents/Anomalies uniquement (axe linéaire) — une 3e catégorie US
  (réutilisant `cycle_time` tel quel) a été essayée puis retirée : son délai
  création -> résolution, qui inclut l'attente en backlog, differe souvent
  d'un ordre de grandeur de celui d'un ticket anomalie/incident, rendant les
  deux illisibles côte à côte (même avec un axe logarithmique, essayé aussi).
  Origine par **ticket parent** (`parent.fields.summary`, tel que fourni par
  l'API — pas de résolution du parent dans le périmètre JQL, contrairement à
  une première version par `components` qui a été abandonnée) ; nom du
  parent tronqué à 42 caractères pour éviter qu'un intitulé long ne s'étale
  sur 3 lignes et n'empiète sur la ligne suivante (grille à hauteur de ligne
  fixe). 3 nouvelles clés `coaching.defauts_*_lecture` (220 caractères, voir
  COACH_PROMPT.md).
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
  correspondance étant classé "Inconnu" plutôt qu'ignoré. Couleur par série
  via `style.type_color()` (voir « Code couleur par type de ticket » plus
  haut — remplace une palette cyclique initiale, retirée au profit du code
  couleur uniforme ci-dessous). Même dépendance Tempo que
  `{{chart:tempo_conso}}` (message de repli identique si `TEMPO_API_TOKEN`
  absent ou app Tempo indisponible).
- Code couleur uniforme par type de ticket (`style.TICKET_TYPE_COLORS`/
  `style.type_color()`, voir « Indicateurs produits ») appliqué à
  `{{chart:types}}`, `{{chart:types_conso}}`, `{{chart:conso_corrective}}` et
  `{{chart:tempo_types}}` — les anciennes constantes `CORRECTIVE_*` (4
  couleurs propres à cet indicateur) et `TEMPO_TYPES_PALETTE` (cycle
  arbitraire) sont retirées, remplacées par ce code couleur unique partagé.
  `{{chart:types_conso}}` affiche désormais le % du total entre parenthèses
  après chaque valeur (colonne valeur élargie à 210 -> 330px pour
  l'accueillir sans retour à la ligne). `{{chart:cumulative_flow_diagram}}`
  distingue désormais 4 encarts (Périmètre suivi, À faire, En cours,
  Terminé) au lieu de 3 — `todo`/`in_progress` dans `cfd.totals`
  (`indicators/cumulative_flow_diagram.py`) séparent les US bloquées à la
  toute première étape du `workflow` de celles réellement au-delà (avant
  cette distinction, `in_progress` mélangeait les deux sous "en cours").
  `{{coach:synthese}}` : les 5 lignes de `LECTURE COACHING` ont désormais une
  hauteur proportionnelle au texte réel (même heuristique
  `_estimate_text_height_px` que `vue_ensemble`/`risque_principal`) plutôt
  qu'un découpage en 5 tranches égales, qui laissait un grand vide sous une
  lecture courte pendant qu'une lecture longue frôlait son séparateur.
  `build_ppt.py` préfixe désormais le nom du fichier PPT généré par la date
  de `generated_at` au format AAAAMMJJ (`<AAAAMMJJ>-indicateurs.pptx`) —
  `render_slides_windows.py` et `scripts/inspect_template.py`-like tooling
  doivent prendre le plus récent (`sorted(glob("*-indicateurs.pptx"))[-1]`)
  plutôt qu'un nom fixe.
- `{{chart:sprint_spread}}` : encart rose « Temps de cycle d'un ticket »
  (colonne de droite, les cartes par nombre de sprints passent sur 3
  colonnes), calculé dans `indicators/sprint_spread.py` (`sprint_cycle_time`).
  Début = plus tardif de la 1re affectation à un sprint (changelog, champ
  Sprint ; à défaut la création) et du début du 1er sprint de l'US ; fin =
  1re transition vers un `done_statuses` (NOS : « Attente livraison recette
  métier »), à défaut `resolutiondate`. Toutes les US terminées, y compris
  multi-sprints. Distinct de `cycle_time` (création -> résolution, affiché
  « lead time »). Aucun nouveau champ `project.yaml`, aucune slide ajoutée.
- `{{chart:sprint_cycle_trend}}` ajouté (`indicators/sprint_cycle_trend.py`,
  `render_agile.render_sprint_cycle_trend`, slide insérée après
  `{{chart:sprint_spread}}` dans les deux `template.pptx`) : courbes P15 /
  médiane / P85 du temps de cycle par sprint d'entrée, rail droit (médiane
  globale, sprints incomplets, `sprint_cycle_trend_lecture`). La règle de
  mesure est factorisée dans `indicators/common.sprint_cycle`, partagée avec
  l'encart de `{{chart:sprint_spread}}`.
