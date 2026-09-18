import indicators.dispersion_etapes as disp_mod
from fixtures import DEFAULT_CONF, make_issue

WORKFLOW = ["À faire", "En cours", "Terminé(e)"]


def test_no_workflow_returns_none():
    issues = [make_issue("KEY-1", status="À faire", created="2024-01-01T00:00:00+00:00")]
    conf = {**DEFAULT_CONF, "workflow": []}

    out = disp_mod.compute(issues, [], conf)

    assert out == {"dispersion_etapes": None}


def test_closed_interval_duration_measured():
    issue = make_issue(
        "KEY-1", status="En cours", created="2024-01-01T00:00:00+00:00",
        status_history=[("2024-01-04T00:00:00+00:00", "À faire", "En cours")],
    )
    conf = {**DEFAULT_CONF, "workflow": WORKFLOW}

    out = disp_mod.compute([issue], [], conf)
    items = {r["name"]: r for r in out["dispersion_etapes"]["items"]}

    # "À faire" quitté après 3 jours pile : seul intervalle clos mesuré.
    assert items["À faire"]["count"] == 1
    assert items["À faire"]["median"] == 3
    # "En cours" jamais quitté par cette US -> aucun échantillon, absent.
    assert "En cours" not in items


def test_open_interval_excluded_from_current_status():
    """L'intervalle en cours (US toujours dans ce statut) est censuré, pas
    mesuré — sinon la distribution serait biaisée vers le bas par des US
    encore en train d'accumuler du temps."""
    issue = make_issue("KEY-1", status="À faire", created="2024-01-01T00:00:00+00:00")
    conf = {**DEFAULT_CONF, "workflow": WORKFLOW}

    out = disp_mod.compute([issue], [], conf)

    assert out == {"dispersion_etapes": None}


def test_group_index_from_cfd_groups():
    workflow = ["Bac à sable", "Affinage technique", "À faire", "En cours", "Terminé(e)"]
    groups = {
        "À faire": ["Bac à sable", "Affinage technique", "À faire"],
        "En cours": ["En cours"],
        "Terminé": ["Terminé(e)"],
    }
    issue = make_issue(
        "KEY-1", status="Terminé(e)", created="2024-01-01T00:00:00+00:00",
        status_history=[
            ("2024-01-03T00:00:00+00:00", "Bac à sable", "Affinage technique"),
            ("2024-01-05T00:00:00+00:00", "Affinage technique", "À faire"),
            ("2024-01-07T00:00:00+00:00", "À faire", "En cours"),
            ("2024-01-09T00:00:00+00:00", "En cours", "Terminé(e)"),
        ],
    )
    conf = {**DEFAULT_CONF, "workflow": workflow, "cfd": {"groups": groups}}

    out = disp_mod.compute([issue], [], conf)
    d = out["dispersion_etapes"]
    items = {r["name"]: r for r in d["items"]}

    assert d["group_labels"] == ["À faire", "En cours", "Terminé"]
    assert items["Bac à sable"]["group_index"] == 0
    assert items["Affinage technique"]["group_index"] == 0
    assert items["À faire"]["group_index"] == 0
    assert items["En cours"]["group_index"] == 1
    # "Terminé(e)" jamais quitté -> pas d'échantillon, absent malgré le groupe.
    assert "Terminé(e)" not in items


def test_status_missing_from_groups_is_ignored():
    workflow = ["À faire", "Bloqué", "En cours", "Terminé(e)"]
    groups = {"À faire": ["À faire"], "En cours": ["En cours"], "Terminé": ["Terminé(e)"]}
    issue = make_issue(
        "KEY-1", status="En cours", created="2024-01-01T00:00:00+00:00",
        status_history=[
            ("2024-01-02T00:00:00+00:00", "À faire", "Bloqué"),
            ("2024-01-03T00:00:00+00:00", "Bloqué", "En cours"),
        ],
    )
    conf = {**DEFAULT_CONF, "workflow": workflow, "cfd": {"groups": groups}}

    out = disp_mod.compute([issue], [], conf)
    names = {r["name"] for r in out["dispersion_etapes"]["items"]}

    assert "Bloqué" not in names


def test_non_us_types_excluded():
    issue = make_issue(
        "KEY-1", itype="Tâche", status="En cours", created="2024-01-01T00:00:00+00:00",
        status_history=[("2024-01-02T00:00:00+00:00", "À faire", "En cours")],
    )
    conf = {**DEFAULT_CONF, "workflow": WORKFLOW}

    out = disp_mod.compute([issue], [], conf)

    assert out == {"dispersion_etapes": None}


def test_renamed_status_resolved_via_id():
    issue1 = make_issue(
        "KEY-1", status="Terminé(e)", status_id="10002", created="2024-01-01T00:00:00+00:00",
        status_history=[
            ("2024-01-04T00:00:00+00:00", "10003", "To Do", "10002", "Done"),
        ],
    )
    issue2 = make_issue("KEY-2", itype="Tâche", status="À faire", status_id="10003",
                         created="2024-01-01T00:00:00+00:00")
    conf = {**DEFAULT_CONF, "workflow": WORKFLOW}

    out = disp_mod.compute([issue1, issue2], [], conf)
    items = {r["name"]: r for r in out["dispersion_etapes"]["items"]}

    assert items["À faire"]["count"] == 1
    assert items["À faire"]["median"] == 3


def test_oscillation_counts_each_visit_separately():
    """Un ticket qui repasse par un statut déjà quitté (aller-retour dans le
    workflow, ex. À faire -> En cours -> À faire -> En cours) doit produire
    un échantillon par visite, pas un seul agrégé ni la perte d'une visite."""
    issue = make_issue(
        "KEY-1", status="En cours", created="2024-01-01T00:00:00+00:00",
        status_history=[
            ("2024-01-02T00:00:00+00:00", "À faire", "En cours"),     # "À faire" #1 : 1j
            ("2024-01-05T00:00:00+00:00", "En cours", "À faire"),     # "En cours" #1 : 3j
            ("2024-01-09T00:00:00+00:00", "À faire", "En cours"),     # "À faire" #2 : 4j
        ],
    )
    conf = {**DEFAULT_CONF, "workflow": WORKFLOW}

    out = disp_mod.compute([issue], [], conf)
    items = {r["name"]: r for r in out["dispersion_etapes"]["items"]}

    # Deux visites distinctes de "À faire" (1j et 4j) -> 2 échantillons, pas 1
    # (médiane de [1, 4] = 2.5 ; si les visites étaient fusionnées/écrasées,
    # count vaudrait 1 et la médiane serait 1 ou 4, jamais 2.5).
    assert items["À faire"]["count"] == 2
    assert items["À faire"]["median"] == 2.5
    assert items["En cours"]["count"] == 1
    assert items["En cours"]["median"] == 3


def test_done_status_excluded_even_with_reopened_samples():
    """Un ticket réouvert (repasse par "Terminé(e)" puis en ressort) produit
    un intervalle clos mesurable pour ce statut — mais un statut terminal
    (`done_statuses`) n'a aucun intérêt sur cette slide et reste exclu, même
    quand des échantillons existent (demande explicite)."""
    issue = make_issue(
        "KEY-1", status="En cours", created="2024-01-01T00:00:00+00:00",
        status_history=[
            ("2024-01-02T00:00:00+00:00", "À faire", "En cours"),
            ("2024-01-05T00:00:00+00:00", "En cours", "Terminé(e)"),
            ("2024-01-08T00:00:00+00:00", "Terminé(e)", "En cours"),  # réouverture
        ],
    )
    conf = {**DEFAULT_CONF, "workflow": WORKFLOW}

    out = disp_mod.compute([issue], [], conf)
    names = {r["name"] for r in out["dispersion_etapes"]["items"]}

    assert "Terminé(e)" not in names


def test_instant_transition_excluded_by_default():
    """Une transition à quelques secondes (signature d'une automatisation
    JIRA à la création, pas un vrai temps passé — voir diagnostic réel projet
    NOS, docstring du module) est ignorée par défaut (seuil 300s = 5 min)."""
    issue = make_issue(
        "KEY-1", status="En cours", created="2024-01-01T00:00:00+00:00",
        status_history=[("2024-01-01T00:00:03+00:00", "À faire", "En cours")],
    )
    conf = {**DEFAULT_CONF, "workflow": WORKFLOW}

    out = disp_mod.compute([issue], [], conf)

    assert out == {"dispersion_etapes": None}


def test_min_transition_seconds_configurable():
    issue = make_issue(
        "KEY-1", status="En cours", created="2024-01-01T00:00:00+00:00",
        status_history=[("2024-01-01T00:00:03+00:00", "À faire", "En cours")],
    )
    conf = {**DEFAULT_CONF, "workflow": WORKFLOW, "dispersion_etapes": {"min_transition_seconds": 1}}

    out = disp_mod.compute([issue], [], conf)
    items = {r["name"]: r for r in out["dispersion_etapes"]["items"]}

    assert items["À faire"]["count"] == 1


def test_transition_above_threshold_still_counted():
    issue = make_issue(
        "KEY-1", status="En cours", created="2024-01-01T00:00:00+00:00",
        status_history=[("2024-01-01T00:10:00+00:00", "À faire", "En cours")],  # 600s > 300s
    )
    conf = {**DEFAULT_CONF, "workflow": WORKFLOW}

    out = disp_mod.compute([issue], [], conf)
    items = {r["name"]: r for r in out["dispersion_etapes"]["items"]}

    assert items["À faire"]["count"] == 1


def test_us_count_counts_distinct_measured_issues():
    issue1 = make_issue(
        "KEY-1", status="En cours", created="2024-01-01T00:00:00+00:00",
        status_history=[("2024-01-03T00:00:00+00:00", "À faire", "En cours")],
    )
    issue2 = make_issue(
        "KEY-2", status="Terminé(e)", created="2024-01-01T00:00:00+00:00",
        status_history=[
            ("2024-01-02T00:00:00+00:00", "À faire", "En cours"),
            ("2024-01-05T00:00:00+00:00", "En cours", "Terminé(e)"),
        ],
    )
    conf = {**DEFAULT_CONF, "workflow": WORKFLOW}

    out = disp_mod.compute([issue1, issue2], [], conf)

    assert out["dispersion_etapes"]["us_count"] == 2
