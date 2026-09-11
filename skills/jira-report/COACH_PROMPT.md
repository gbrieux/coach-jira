# Prompt — Synthèse du coach agile

Instructions pour rédiger les textes narratifs du PPT « design agile ». Cette étape
est effectuée par **Claude en session, pas par un script** : lire
`projects/<clé>/output/data.json`, exécuter les contrôles préalables, poser les
questions de session, rédiger les textes, puis les écrire dans le JSON sous la clé
`coaching`.

Ce prompt est générique : il ne cite aucun projet, aucune équipe, aucune clé de
ticket réelle. Il ne parle que de noms de champs du JSON et de règles.

---

## Sortie attendue

`coaching` est un **objet** (pas une chaîne), avec cette structure exacte :

```json
"coaching": {
  "vue_ensemble": "…",
  "risque_principal": "…",
  "delta": "…",
  "lecture": {
    "Vélocité": "…",
    "Cycle time": "…",
    "Périmètre": "…",
    "Flux": "…",
    "Sprint NN": "…"
  },
  "recommandations": ["…", "…", "…"],
  "questions": ["…", "…", "…"],
  "burndown_lecture": "…",
  "velocity_lecture": "…",
  "types_lecture": "…",
  "cycle_time_lecture": "…",
  "conso_corrective_lecture": "…",
  "tempo_conso_lecture": "…",
  "epics_lecture": "…"
}
```

Tous les champs sont optionnels — un champ absent fait disparaître proprement la
carte ou le texte correspondant, aucune ne bloque le rendu. **Ne jamais inventer de
contenu pour un champ que les données ne justifient pas** : un champ absent est
meilleur qu'un champ creux.

---

## Étape 0 — Résoudre le contexte

```bash
python scripts/resolve_context.py <project_key>
```

Renvoie `organisation.md` (contexte transverse, toujours applicable) + le
`contexte/<team_id>.md` de l'équipe. **Si la commande échoue** (team_id absent,
fichier introuvable), afficher l'erreur telle quelle et s'arrêter — ne jamais
inventer de contexte équipe ni continuer sans lui.

Ne jamais mentionner un nom de fichier ni l'existence du contexte dans le texte
final : l'information est intégrée naturellement, sourcée par le fond.

---

## Étape 1 — Contrôles préalables (obligatoires, avant toute rédaction)

À exécuter dans cet ordre. Chacun peut changer la lecture d'un chiffre ; les faire
après avoir rédigé ne sert à rien.

### 1.1 Ancrage temporel

Toute formule du type « au <date> » se réfère à **`generated_at`**, jamais à la date
du jour de la session. Si l'écart entre les deux dépasse quelques jours, le dire une
fois dans `vue_ensemble` et ne plus employer « aujourd'hui ».

### 1.2 Jointure contexte — clés de tickets

Scanner le contexte à la recherche de **clés de tickets ou d'epics** citées
explicitement. Pour chacune :

- si la clé est présente dans `epics.items[].key`, la lecture de cet epic doit
  intégrer ce que dit le contexte (charge transverse, sous-chiffrage connu, epic
  fourre-tout, périmètre gelé…) ;
- si la clé est **absente du périmètre**, ne pas l'ignorer silencieusement : le
  signaler quand elle change l'interprétation (charge répartie sur plusieurs epics
  dont un seul est dans le JQL analysé) ;
- **ne jamais interpréter la prévisibilité des epics avant cette jointure.** Un
  `previsibilite_pct` élevé ou un `raf_theo_jh` négatif porté par un epic non estimé
  et connu du contexte comme non fonctionnel n'est pas un dérapage d'estimation.
  Conclure l'inverse est un faux procès fait à l'équipe.

### 1.3 Fraîcheur et cohérence du contexte

- Comparer la date des blocs de contexte à `generated_at`. Un contexte
  significativement plus ancien que les données est utilisable, mais ne peut pas
  servir à expliquer un chiffre postérieur sans réserve explicite.
- Un bloc **non daté** ne peut pas fonder une affirmation sur une évolution
  (« depuis que… ») : il n'a pas de position dans le temps.
- Si **deux passages du contexte se contredisent**, ne pas trancher : retenir la
  version datée la plus récente et signaler l'ambiguïté en question de session
  (§2).
- Si le contexte **contredit les données** (contexte : « presque terminé » /
  données : avancement faible), signaler l'écart plutôt que de choisir un camp.

### 1.4 Arbitrage des chiffres homonymes

Plusieurs champs mesurent des choses proches avec des définitions différentes. Le
tableau ci-dessous fixe le chiffre canonique par usage. **Ne jamais faire
d'arithmétique entre deux lignes de ce tableau.**

| Usage | Champ canonique | À ne pas utiliser pour ça |
|---|---|---|
| Avancement du périmètre | `burnup_release.done_cumul_us` / `scope_cumul_us`, dernier point non nul | `total_issues` (tous types, jamais un dénominateur d'avancement US) |
| Nombre d'US terminées **à date** | `status_counts_us` sur les statuts de `done_statuses_us` | `velocity[].done` |
| US terminées **par sprint** | `sprint_table[].done_us` (attribution par date de résolution) | `velocity[].done` (attribution par champ Sprint) |
| Engagement d'un sprint | `velocity[].engaged` vs `velocity[].done` | `sprint_table` |
| Story points du périmètre | `scope_cumul_sp` / `done_cumul_sp` | mélange avec les compteurs d'US |
| Conso sur le périmètre US | `sprint_table[].conso_cumul_us_jh` | les autres totaux de conso |
| Conso worklogs toutes natures | `tempo_conso.total_conso_jh` | `type_conso_jh` |
| Conso par type de ticket | `type_conso_jh` | `epics.total_conso_jh` |
| Conso rollup par epic | `epics.total_conso_jh` | `conso_corrective.total_jh` |
| Conso des tickets terminés, par mois | `conso_corrective.total_jh` | tout le reste |

Si deux champs canoniques divergent sur ce qui devrait être le même fait, l'écart se
tranche **ici**, en amont : retenir le champ canonique et ne mentionner la divergence
dans le texte **que si elle change la conclusion**. Expliquer la plomberie de l'outil
sur une slide destinée à des sponsors est un défaut, pas une précision.

### 1.5 État des sprints

- Exclure de toute lecture de tendance les sprints `state == "future"` et le
  pseudo-sprint initial (`num == 0`) : leurs zéros ne sont pas des contre-performances.
- Le sprint `active` est **partiel** : tout chiffre qui en vient est annoncé comme
  tel, jamais comparé à un sprint clos sans réserve.
- Compter les sprints réellement clos. C'est la taille d'échantillon de tout le
  raisonnement (§1.8).

### 1.6 Troncature des séries

Toute série temporelle (`burndown_sprint.real`, `real_sp`, `done_cumul_us`,
`trend_*`…) se lit **jusqu'à son dernier point renseigné**. Les `null` de fin sont du
futur, pas un plateau. Un plateau ne peut être affirmé que sur des points réellement
renseignés et consécutifs.

Cas particulier : une série de reste à faire **plate sur plusieurs jours** peut
signifier « rien ne se termine » ou « le champ n'est pas mis à jour ». Si la série en
US bouge et la série en points ne bouge pas (ou l'inverse), c'est un problème de
saisie, pas de production : le traiter en §1.9.

### 1.7 Couverture du périmètre US

Les indicateurs US-scopés ignorent tout type hors `us_types`. Calculer une fois la
part de `type_conso_jh` portée par les types US sur le total.

- Part élevée — les indicateurs US représentent bien l'activité ; le dire une fois
  suffit, ne pas y revenir.
- Part faible — l'annoncer explicitement : une partie substantielle de la charge est
  invisible dans le burnup, la vélocité et le cycle time.

### 1.8 Niveau de confiance

Avant toute projection, évaluer la solidité de l'échantillon :

- nombre de sprints clos exploitables ;
- présence de sprints aberrants (un sprint très au-dessus ou très en dessous des
  autres, ou un sprint quasi nul) ;
- `cycle_time.count` par rapport au périmètre total.

Sur un échantillon court ou hétérogène, une médiane de vélocité n'a qu'une valeur
indicative. **Le dire est obligatoire**, dans `vue_ensemble`, en une proposition.
Une projection présentée sans réserve sur 3 ou 4 sprints dont un aberrant est une
erreur, pas une synthèse.

### 1.9 Hygiène des données

Relever ce qui relève de la saisie et non de la performance, et le traiter comme tel :

- epics dont le statut n'a pas suivi l'avancement (statut initial alors que des US
  sont terminées) ;
- éléments avec conso mais sans estimation, ou l'inverse ;
- US engagées sans estimation (`sp_engaged` nul avec des US engagées) ;
- `estimate_jh` à zéro sur un epic démarré ;
- écart entre deux attributions temporelles du même fait (§1.4) ;
- `not_started_count` élevé rapporté au nombre total d'epics.

**Distinguer explicitement « l'équipe est lente » de « l'outil ne reflète pas la
réalité ».** Sans ce tri, la synthèse est attaquable en réunion et le coach perd la
main. Ce qui relève de la saisie va en recommandation ou en question, jamais en
constat de performance.

---

## Étape 2 — Questions de session (famille A)

Ces questions sont posées **à l'utilisateur, dans le chat**, avant ou pendant la
rédaction. Elles ne vont **jamais** dans le JSON. Elles comblent ce que les données ne
peuvent pas dire.

À poser systématiquement quand l'information manque :

1. **Date ou échéance cible.** Aucun champ du JSON ne la porte. Sans elle, aucune
   affirmation du type « on tient / on ne tient pas » n'est possible : dire que
   l'échéance n'est pas renseignée et s'en tenir aux scénarios.
2. **Capacité réellement affectée.** Si le contexte donne un effectif, le confronter
   à la durée de sprint (déductible des dates) et à la conso observée sur le
   périmètre. Un écart important a plusieurs explications concurrentes (équipe
   partagée sur plusieurs périmètres, worklogs incomplets, charge hors JQL) que les
   données ne permettent pas de départager. **Poser la question ; ne jamais écrire
   une conclusion de capacité sur la slide.**
3. **Sens d'une incohérence relevée en §1.4 ou §1.9**, quand elle change la lecture.
4. **Arbitrage attendu**, quand l'écart entre scénarios est large : sur quel levier
   la décision est censée porter.

Formuler au maximum 4 questions, groupées, en une fois. Les réponses obtenues sont
candidates à un ajout de contexte (voir « Proposer un ajout de contexte ») — c'est
ce qui rendra la prochaine analyse meilleure.

---

## Étape 3 — Delta avec l'analyse précédente

```bash
python scripts/coaching_history.py last <project_key>
```

Renvoie la dernière synthèse archivée et sa date, ou rien s'il n'y en a pas.

- **Pas d'historique** — ne pas produire le champ `delta`.
- **Historique disponible** — rédiger `delta` : ce qui a bougé depuis, en priorité
  dans cet ordre : avancement et scénarios d'atterrissage, vélocité, cycle time,
  périmètre, flux. Et le devenir des recommandations précédentes : reprises,
  abandonnées, sans effet visible.

Pour que le delta soit lisible d'une fois sur l'autre, **les clés de `lecture` sont
figées** (§5.3) et le vocabulaire reste stable : le même phénomène se nomme toujours
de la même façon.

---

## Étape 4 — Règles d'analyse

### 4.1 Le contexte explique, il ne remplace jamais un chiffre

Un chiffre est d'abord interprété à partir des données. Le contexte intervient pour
éclairer *pourquoi* ce chiffre est ce qu'il est, quand c'est manifeste. Ne jamais
forcer un lien qui n'existe pas : si rien dans le contexte n'éclaire un chiffre, s'en
tenir aux données.

Le contexte est autant là pour expliquer une **hausse** brutale (renfort, changement
de priorité, dégel de périmètre) qu'une baisse. Et une hausse expliquée par un
événement ponctuel **n'est pas une nouvelle vitesse nominale** : le dire quand la
projection s'appuie dessus.

### 4.2 Un risque issu du seul contexte est légitime

Un risque décrit dans le contexte et sans trace dans les données (dette de
synchronisation, dépendance externe, décision d'organisation en attente) peut être le
risque principal. Dans ce cas, le marquer comme non tracé dans les indicateurs,
plutôt que de le déguiser en lecture de chiffre.

### 4.3 Triangulation de l'atterrissage

Trois méthodes indépendantes, à confronter :

1. **Courbes de tendance** : `burnup_release.trend_pessimist` / `trend_median` /
   `trend_optimist`. Pour chacune, repérer le premier index où la courbe atteint le
   périmètre courant, puis convertir cet index en date via `categories` /
   `category_dates`, et en nombre de sprints via `anchor_index`. Exprimer le résultat
   **en date**, pas seulement en nombre de sprints. Si une courbe n'atteint pas le
   périmètre dans l'horizon disponible, le dire ainsi — ne pas extrapoler.
2. **Reste ÷ vélocité** : (`scope_cumul_us` − `done_cumul_us`) rapporté à
   `median_velocity_us`, `avg_velocity` et à `burnup_release.velocity_us`.
3. **Projection en charge** : `epics.projection_theorique_jh` face à
   `epics.total_estimate_jh`, après la jointure §1.2.

Convergence des trois — l'affirmation est tenable en comité. Divergence — c'est ça le
sujet, et il faut le nommer.

Deux scénarios qui donnent le même résultat sont presque toujours un effet de bord
(courbe qui butte sur la fin de l'horizon) : le signaler comme tel, ne pas le
recopier comme un fait.

### 4.4 Traduire chaque scénario en rythme requis

Une date sans rythme n'engage personne. Pour le ou les scénarios cités, calculer la
vélocité nécessaire et la comparer au réalisé : au meilleur sprint clos et à la
médiane. Un scénario qui suppose un multiple de ce que l'équipe n'a atteint qu'une
fois doit être présenté comme tel.

### 4.5 Cycle time : biais du survivant et prévisibilité

- `cycle_time` ne porte que sur les éléments **terminés** (`count`). Les éléments
  encore ouverts, dont les plus anciens, n'y sont pas. La situation réelle est donc
  au mieux égale à ce que montre la statistique. Ce caveat est obligatoire dès que
  `count` est nettement inférieur au périmètre.
- Écart `mean` / `median` important — des cas longs tirent la moyenne.
- Rapport `p85` / `median` élevé — la dispersion interdit de prévoir un élément à
  l'unité ; c'est un argument pour prévoir par le flux plutôt que par l'estimation.
- Comparer la médiane à la **durée d'un sprint** : une médiane supérieure à la durée
  du sprint explique mécaniquement les débordements d'un sprint sur l'autre.

### 4.6 Débit contre arrivée

Avec `burnup_release` (ou `sprint_table`) et `cfd` :

- comparer la progression du **périmètre** et celle du **terminé** sur la fenêtre :
  si les deux progressent au même rythme, le reste à faire ne baisse pas, l'équipe
  court pour rester sur place. C'est une lecture qu'aucun graphique du deck ne donne
  seul ;
- suivre le **WIP** (éléments entrés en cours et non terminés) : une montée continue
  est un goulot, une chute brutale est une purge de fin de sprint, pas une
  accélération durable.

### 4.7 Engagement ≠ vélocité

Deux diagnostics distincts, deux remèdes opposés :

- écart `engaged` / `done` important et récurrent — problème de **calibrage** du
  sprint (dimensionnement, découpage, DoR) ;
- `done` très variable d'un sprint à l'autre à engagement stable — problème de
  **capacité ou de flux**.

Ne pas fondre les deux sous « vélocité erratique ».

### 4.8 Estimation contre réel

Deux niveaux, complémentaires :

- niveau élément : estimation cumulée rapportée au nombre d'éléments, face à
  `tempo_conso.avg_jh_per_us` ;
- niveau epic : `epics.previsibilite_pct`, `total_raf_theo_jh`, après §1.2.

Un facteur important entre estimé et réel est un signal de prévisibilité, pas une
faute : la question est de savoir si les estimations sont faites, à quelle maille, et
avec quelle unité.

### 4.9 Signal convergent autorisé

Quand plusieurs indicateurs décrivent **le même phénomène** (cycle time long +
éléments traversant plusieurs sprints + accumulation en amont), les traiter ensemble
dans une seule entrée plutôt que de les répartir artificiellement. La règle « un
sujet par entrée » cède devant un signal convergent : c'est le croisement qui fait la
valeur de la synthèse.

### 4.10 Le socle commun comme étalon

Le contexte transverse porte les critères communs (Definition of Ready, Definition of
Done, règles de saisie). Les utiliser comme grille de lecture du flux et de la
qualité : un statut intermédiaire encombré se lit à la lumière du critère de DoR
correspondant, une file d'attente en fin de chaîne à la lumière de la DoD. Les
recommandations s'y réfèrent explicitement quand elles s'appuient dessus.

---

## Étape 5 — Rédaction de la slide coach

### 5.1 `vue_ensemble` — prose continue, pas de puces

Destinataire : **sponsors / direction**. Répondre, dans cet ordre :

1. Où en est-on ? Avancement du périmètre suivi (§1.4), volume, éventuellement charge.
2. Quels scénarios d'atterrissage, **en dates**, et à quel rythme requis (§4.3, §4.4) ?
3. Quel niveau de confiance (§1.8) ? Si aucune échéance cible n'est renseignée, le
   dire une fois.
4. Quel est le risque principal — **un seul**, le plus significatif, annoncé ici et
   développé dans `risque_principal`.

Inclure **une observation factuelle positive** si les données en portent une (un
sprint qui démontre une capacité, un délai qui s'améliore, un périmètre qui se
stabilise). Une synthèse qui ne nomme jamais un point positif se fait retourner par
l'équipe et discrédite le reste.

Ton factuel, pas de jargon non expliqué, **aucune recommandation ici**.

### 5.2 `risque_principal`

Développe le risque déjà évoqué dans `vue_ensemble` — affiché seul dans une carte, à
côté. Un seul risque, sa cause, sa conséquence si rien ne change. Pas de solution
ici : elle est en recommandation.

Choisir le risque par **impact × probabilité**, dans cet ordre de priorité quand
plusieurs se disputent la place : tenue de l'objectif, qualité livrée, soutenabilité
de l'équipe, fiabilité du pilotage.

### 5.3 `lecture` — dictionnaire ordonné, clés figées

**Exactement 5 entrées, dans cet ordre, avec ces libellés :**

| Clé | Champs de référence |
|---|---|
| `Vélocité` | `velocity`, `avg_velocity`, `median_velocity_us`, `median_velocity_sp` |
| `Cycle time` | `cycle_time`, `sprint_spread` |
| `Périmètre` | `sprint_table`, `burnup_release`, `epics` |
| `Flux` | `status_counts_us`, `cfd` |
| `Sprint NN` | `burndown_sprint` (NN = numéro du sprint en cours) |

Une entrée = une lecture, pas une liste de chiffres. Si les données d'une entrée sont
absentes ou insuffisantes (`burndown_sprint` à `null` faute de sprint actif, par
exemple), écrire la raison en une phrase courte plutôt que de meubler ou de supprimer
la clé.

Ces libellés ne changent **jamais** d'un refresh à l'autre : c'est ce qui rend le
`delta` lisible. Ne pas ajouter de sixième entrée : elle ne serait pas rendue.

### 5.4 `recommandations` — 3 maximum

- **Une recommandation = une action = un destinataire.** Jamais deux sujets dans un
  même item.
- Chacune reliée explicitement à une observation ci-dessus. Jamais de généralité du
  type « améliorer la communication » sans lien avec un chiffre du JSON.
- S'appuyer sur le contexte équipe et le contexte transverse pour que l'action soit
  réaliste : une action déjà tentée et documentée comme un échec n'est pas une
  recommandation.
- Formuler à l'impératif, action d'abord. **Aucune question ici** : elles ont leur
  champ (§6).
- Ce qui relève de la saisie (§1.9) est recevable comme recommandation, mais nommé
  comme tel.

### 5.5 Nommer la décision attendue

Quand l'écart entre scénarios est large, la sortie utile n'est pas une action
d'équipe mais un **arbitrage**, sur l'un des trois leviers : périmètre, date, moyens.
Le nommer, et nommer qui décide — dans `vue_ensemble` s'il s'agit du cadrage, en
recommandation s'il s'agit d'une action à déclencher.

---

## Étape 6 — `questions` (famille B, sur la slide)

2 à 3 questions de coach, destinées à **ouvrir la conversation** en revue de sprint,
en rétrospective ou en comité. Elles sont affichées sur la slide, pas posées dans le
chat.

**4 critères cumulatifs.** Une question qui en manque un est écartée :

1. **ancrée** sur un chiffre précis du JSON ou un fait précis du contexte ;
2. **adressée** à un rôle nommé (équipe, PO, sponsor, coach) ;
3. **ouverte** — ni oui/non, ni réponse à un seul chiffre ;
4. **sincère** — la réponse n'est pas déjà dans la synthèse. Une question dont la
   réponse est écrite trois lignes au-dessus est rhétorique, donc inutile.

Bons exemples de forme : « Qu'est-ce qui empêche aujourd'hui de terminer les
éléments en attente en fin de chaîne, et qui peut le débloquer ? » — « Sur quel
levier veut-on jouer si le rythme observé se confirme : périmètre, date ou moyens ? »
— « Qu'est-ce qui a rendu le meilleur sprint possible, et qu'est-ce qui empêche de le
reproduire ? »

Contre-exemples à ne jamais produire : « Comment améliorer la communication ? » —
« Peut-on tenir la date ? » (fermée) — « Combien d'éléments restent à faire ? »
(la réponse est sur la slide).

---

## Étape 7 — Légendes de graphiques

Une légende est une **lecture de la courbe affichée sur sa slide**, pas une synthèse.
1 à 2 phrases. Elle interprète la forme, la tendance et le piège de lecture propre à
l'indicateur.

### 7.1 Règle de non-recouvrement

Une observation déjà écrite dans une légende ne peut apparaître dans `lecture` que si
elle y est **croisée avec autre chose**. Inversement, une légende ne reprend pas une
conclusion transverse de la slide coach. Sans cette règle, le même constat apparaît
trois fois dans le deck et la synthèse perd sa valeur.

### 7.2 Neutralité d'unité

Plusieurs légendes sont affichées **à l'identique sur plusieurs variantes de la même
slide** (version combinée, version en éléments, version en points). Une légende ne
doit donc commenter que ce qui est visible sur **toutes** les variantes : ne pas
mentionner une série qui n'existe que sur l'une d'elles. Si la lecture porte
réellement sur l'écart entre les deux unités, l'écrire de façon à rester vraie sur
chaque variante.

### 7.3 Périmètre de chaque légende

| Champ | Slide | Champs autorisés | À ne pas y mettre |
|---|---|---|---|
| `burndown_lecture` | Burndown du sprint en cours | `burndown_sprint` | tout ce qui dépasse le sprint courant |
| `velocity_lecture` | Vélocité / engagement par sprint | `velocity`, médianes | le cycle time, le périmètre |
| `types_lecture` | Répartition des types de tickets, en **nombre** | `type_counts` | la consommation (autre slide, autres champs) |
| `cycle_time_lecture` | Cycle time (percentiles) | `cycle_time` | la vélocité |
| `conso_corrective_lecture` | Charge corrective par mois | `conso_corrective` | la conso totale du projet |
| `tempo_conso_lecture` | Conso worklogs vs éléments terminés | `tempo_conso` | une lecture de productivité (voir ci-dessous) |
| `epics_lecture` | Avancement par epic | `epics` (après §1.2) | la vélocité, le sprint courant |

Cas particuliers :

- `conso_corrective_lecture` : ne pas commenter si toutes les séries sont à zéro
  (catégories non configurées : rien à interpréter). Un mois en cours est partiel :
  aucune tendance ne se conclut dessus. La ventilation suit le mois de résolution,
  pas celui du travail.
- `tempo_conso_lecture` : ne pas commenter si le champ est absent (outil non installé
  sur ce projet). Le décalage entre conso et clôtures est temporel par nature :
  **jamais de lecture en productivité**.
- `epics_lecture` : interdiction absolue de commenter la prévisibilité avant la
  jointure §1.2.

---

## Contraintes de rendu

La mise en page est à **positions fixes** : les cadres de texte grandissent avec le
contenu, mais les éléments voisins ne bougent pas. Un texte trop long ne réduit pas la
police, il **passe sous l'élément suivant ou sort de la slide**. Les plafonds
ci-dessous ne sont pas indicatifs.

| Champ | Plafond | Limite dure |
|---|---|---|
| `vue_ensemble` | **380 caractères** | au-delà, la fin passe sous la carte du risque |
| `risque_principal` | **150 caractères** | au-delà, le texte sort de sa carte |
| `delta` | **300 caractères** | — |
| chaque valeur de `lecture` | **150 caractères** | **exactement 5 entrées** ; une 6ᵉ dépasse la carte |
| chaque `recommandations` | **105 caractères**, numérotation incluse | **3 maximum** ; une 4ᵉ sort de la slide |
| chaque `questions` | **110 caractères** | 3 maximum |
| `burndown_lecture` | **200 caractères** | colonne étroite |
| `velocity_lecture` | **200 caractères** | colonne étroite |
| `tempo_conso_lecture` | **200 caractères** | colonne étroite |
| `conso_corrective_lecture` | **250 caractères** | — |
| `cycle_time_lecture` | **220 caractères** | bandeau bas, 2 lignes |
| `types_lecture` | **250 caractères** | bandeau large, 2 lignes |
| `epics_lecture` | **250 caractères** | — |

Ces plafonds sont la **référence unique** utilisée par `scripts/check_coaching.py` —
ne pas les recopier ailleurs (SKILL.md, autres docs) sans les faire diverger : y
renvoyer à la place.

Ne jamais chercher à gagner de la place en réduisant la police en dessous de 12 pt :
couper le contenu, pas la lisibilité. Si un champ ne tient pas, c'est qu'il contient
deux idées : en garder une.

---

## Auto-vérification avant écriture

Passer chaque point. Un seul échec = on corrige avant d'écrire le JSON.

1. **Longueurs** : chaque champ sous son plafond, `lecture` à 5 entrées exactement,
   `recommandations` et `questions` à 3 items maximum. Vérifiable automatiquement
   avec `scripts/check_coaching.py` (voir « Écriture du JSON » plus bas).
2. **Chiffres** : chaque nombre cité existe tel quel dans le JSON, ou est un calcul
   explicitement prévu ici (avancement, écart à l'idéal, rythme requis). Aucun chiffre
   reconstitué de mémoire.
3. **Homonymes** : aucun même nombre employé avec deux sens différents sur la même
   slide sans que son périmètre soit précisé à chaque fois.
4. **Dénominateurs** : aucun mélange entre un total tous types et un périmètre
   restreint.
5. **Non-recouvrement** : aucune phrase de légende reprise dans `lecture`, et
   réciproquement.
6. **Unités** : aucune légende ne mentionne une série absente d'une de ses variantes.
7. **Traçabilité** : chaque recommandation renvoie à une observation présente dans le
   texte.
8. **Confiance** : la réserve sur l'échantillon est présente dès qu'une projection est
   citée.
9. **Plomberie** : aucune explication de mécanique interne de l'outil sur la slide,
   sauf si elle change la conclusion.
10. **Personnes** : aucune formulation qui juge des personnes (§ ci-dessous).

---

## Écriture du JSON (UTF-8 obligatoire)

Sous Windows PowerShell 5.1, ne jamais envoyer un here-string contenant des accents
avec `@'…'@ | python -` : `$OutputEncoding` vaut `us-ascii` par défaut et remplace les
caractères accentués par `?` avant leur arrivée dans Python.

Archiver la synthèse précédente **avant** d'écrire la nouvelle :

```bash
python scripts/coaching_history.py archive <project_key>
```

Puis écrire l'objet coaching dans un fichier réellement UTF-8, le valider, et
l'injecter :

```powershell
python scripts/check_coaching.py <coaching_utf8.json>
python scripts/set_coaching.py <project_key> <coaching_utf8.json>
```

`check_coaching.py` vérifie les plafonds et cardinalités du tableau ci-dessus
(« Contraintes de rendu ») et rien d'autre — sortie 0 si injectable, 1 sinon ;
`set_coaching.py` l'appelle aussi en interne juste avant d'injecter, donc une synthèse
qui casserait le rendu est refusée à la source même si cette étape est sautée. Le
helper valide en plus l'encodage, puis injecte de manière atomique.

---

## Proposer un ajout de contexte

Un fait peut mériter d'être conservé pour les prochaines analyses de cette équipe :
changement d'effectif, décision d'organisation, point de blocage récurrent, réponse
donnée à une question de session (§2), sens d'une incohérence de données. Dans ce cas :

1. **Proposer, ne jamais écrire directement** : montrer le bloc exact tel qu'il serait
   ajouté, au format
   ```markdown
   ## AAAA-MM-JJ — [sujet court]
   Contenu…
   ```
   avec la date du jour, jamais devinée ni approximative. **Toujours daté** : un bloc
   sans date est inexploitable pour les analyses suivantes.
2. **Attendre une confirmation explicite** avant d'écrire quoi que ce soit.
3. Une fois confirmé, écrire le bloc dans un fichier temporaire UTF-8 puis :
   ```bash
   python scripts/append_context.py <team_id> <bloc_utf8.md>
   ```
   Le script ajoute toujours en fin de fichier et crée `contexte/<team_id>.md` s'il
   n'existe pas.

Cette règle s'applique autant quand l'utilisateur demande un ajout que quand c'est
vous qui en repérez un pertinent : montrer puis attendre, jamais écrire en silence.

---

## Contraintes de forme

- **Français, ton professionnel et direct.** Ni flatterie, ni alarmisme.
- **Décrire un système, jamais des personnes.** « Le délai médian est de N jours »,
  pas « l'équipe est lente ». « L'engagement dépasse la capacité observée », pas
  « l'équipe s'engage mal ». Sur un support qui monte en direction, c'est la
  différence entre un outil de coaching et un réquisitoire.
- **Ne jamais inventer un chiffre.** Si une donnée manque, est nulle ou vide, le dire
  explicitement plutôt que de l'ignorer ou de l'extrapoler.
- **Ne pas recopier les chiffres déjà visibles** sur la slide concernée : les
  interpréter. Sur la slide coach, qui ne porte aucun graphique, les chiffres
  nécessaires au raisonnement sont attendus.
- **Vocabulaire stable** d'un refresh au suivant : le même phénomène se nomme toujours
  de la même façon, sans quoi le `delta` devient illisible.
- **Aucun nom de fichier, aucune référence au contexte en tant que source** dans le
  texte rendu.
- Anti-patterns à ne jamais produire : généralité sans chiffre, jargon agile non
  expliqué, projection sans réserve, recommandation à deux sujets, question
  rhétorique, comparaison d'un sprint partiel avec des sprints clos.
