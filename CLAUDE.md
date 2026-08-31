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

## Ajouter un indicateur

Check-list complète — pensée pour une session qui repart de zéro, sans le
contexte de celle qui a ajouté l'indicateur précédent. Un indicateur touche
toujours plusieurs fichiers ; en oublier un ne casse rien immédiatement (tout
reste optionnel dans le pipeline) mais laisse le nouvel indicateur invisible,
non testé, ou non documenté. Dans l'ordre :

1. **Module de calcul** — `skills/jira-report/scripts/indicators/<nom>.py`,
   expose `compute(issues, sprints, conf) -> dict` et/ou
   `RENDERERS = {"<placeholder>": render_agile.render_<nom>}`. Découverte
   automatique (voir `indicators/__init__.py`) — ne jamais toucher
   `fetch_jira.py`/`build_ppt.py` pour « enregistrer » le module.
2. **Rendu natif** — fonction `render_agile.render_<nom>(slide,
   placeholder_shape, data, template_path, page_num, total_pages)` dans
   `render_agile.py`. Réutiliser les helpers existants (`shapes.py` :
   `add_header`/`add_footer`/`add_rounded_rect`/`add_text` ; `render_agile.py` :
   `_card_stat`, `_set_manual_plot_area`, `CategoryChartData`/`XL_CHART_TYPE`)
   plutôt que redessiner à la main.
3. **Couleurs** — nouvelles constantes dans `style.py` uniquement (jamais de
   `RGBColor(...)` en dur ailleurs dans le skill, voir l'en-tête de ce fichier).
4. **Nouveaux champs `project.yaml`, s'il y en a** — trois endroits à mettre à
   jour ensemble, sous peine de `KeyError` silencieux dans un projet qui ne
   les définit pas ou dans les tests :
   - valeur par défaut dans `fetch_jira.py:DEFAULTS` ;
   - documentation commentée + exemple dans
     `skills/jira-report/scaffold/project.example.yaml` ;
   - même valeur par défaut dans `skills/jira-report/tests/fixtures.py:DEFAULT_CONF`.
5. **Template** — une nouvelle slide `{{chart:<nom>}}` dans les DEUX
   `template.pptx` (jamais un seul) :
   ```bash
   python scripts/duplicate_slide.py <chemin_template.pptx> \
     --source-placeholder "{{chart:<indicateur_proche>}}" \
     --new-placeholder "{{chart:<nom>}}"
   ```
   à lancer une fois sur `templates/template.pptx` (charte réelle, ce dépôt) et
   une fois sur `skills/jira-report/scaffold/template.pptx` (scaffold neutre,
   distribué avec le skill) — choisir `--source-placeholder` sur la slide dont
   la position est la plus proche de celle voulue pour la nouvelle (elle
   s'insère juste après). Vérifier avec
   `python scripts/inspect_template.py <chemin_template.pptx>`.
6. **Tests** — `skills/jira-report/tests/test_<nom>.py`, sur le modèle des
   modules existants (`fixtures.make_issue`/`make_sprint`). Lancer
   `pytest tests/` depuis `skills/jira-report/` avant de considérer l'ajout
   terminé.
7. **Docs** :
   - `skills/jira-report/SKILL.md` — une ligne dans le tableau
     « Indicateurs produits » + une entrée dans « Historique / suivi ».
   - `skills/jira-report/COACH_PROMPT.md` — si l'indicateur a une légende
     `*_lecture` rédigée par le coach, l'ajouter à la structure JSON
     `coaching` (bloc d'exemple en tête de fichier) et à la liste
     « Autres slides ».
8. **QA réelle** — sur un vrai projet : `fetch_jira.py <clé>` (si le module
   calcule à partir de champs pas encore récupérés) puis `build_ppt.py <clé>`
   puis, sur poste Windows, `render_slides_windows.py <clé>` — inspecter
   l'image de la nouvelle slide et vérifier qu'aucun `{{...}}` ne subsiste
   (voir SKILL.md, section « QA »).

**Piège vécu (2026-08-31)** : ne jamais tenir pour acquis qu'un `template.pptx`
re-sauvegardé par python-pptx (ce que fait `duplicate_slide.py`, ou tout autre
script qui appelle `Presentation.save()`) garde intacts tous ses médias — un
média présent dans le fichier mais non référencé par une forme que python-pptx
reconnaît comme telle est élagué au `save()`, silencieusement. C'est ce qui
est arrivé au logo d'en-tête (`ppt/media/imageN.png`, lu par accès direct au
zip dans `shapes.py:template_image_bytes`, hors du modèle de relations
python-pptx) — et le template réel n'a de toute façon plus de logo depuis.
Conséquence tirée : le logo est maintenant **entièrement optionnel** (voir
« Template » dans `SKILL.md`) — `add_header`/`_dark_header` n'en dessinent un
que si `logo_media` est fourni ET que le fichier existe réellement dans
`template.pptx`, sinon l'en-tête se dessine normalement sans logo. Aucun
appelant du skill ne passe `logo_media` par défaut. Après toute manipulation
de template (avec `duplicate_slide.py` ou à la main), rebuilder un vrai PPT
(`build_ppt.py`) pour vérifier que rien ne casse — `inspect_template.py` seul
ne le détecte pas (il ne lit que les placeholders texte, pas les médias).

## Autres notes de session

Le reste (résolution d'équipe, calculs d'indicateurs, rendu du PPT, prompt de
synthèse) vit dans le skill — voir `skills/jira-report/SKILL.md` et
`skills/jira-report/COACH_PROMPT.md`.