import indicators.temps_par_etape as tpe_mod
from fixtures import DEFAULT_CONF, make_issue

WORKFLOW = ["À faire", "En cours", "Terminé(e)"]


def test_no_workflow_returns_none():
    issues = [make_issue("KEY-1", status="À faire", created="2024-01-01T00:00:00+00:00")]
    conf = {**DEFAULT_CONF, "workflow": []}

    out = tpe_mod.compute(issues, [], conf)

    assert out == {"temps_par_etape": None}


def test_median_per_status_and_cumulative_total():
    issue1 = make_issue(
        "KEY-1", status="En cours", created="2024-01-01T00:00:00+00:00",
        status_history=[("2024-01-04T00:00:00+00:00", "À faire", "En cours")],  # 3j en "À faire"
    )
    issue2 = make_issue(
        "KEY-2", status="En cours", created="2024-01-01T00:00:00+00:00",
        status_history=[("2024-01-06T00:00:00+00:00", "À faire", "En cours")],  # 5j en "À faire"
    )
    conf = {**DEFAULT_CONF, "workflow": WORKFLOW}

    out = tpe_mod.compute([issue1, issue2], [], conf)
    d = out["temps_par_etape"]
    items = {r["name"]: r for r in d["items"]}

    assert items["À faire"]["median"] == 4  # médiane de [3, 5]
    assert items["À faire"]["count"] == 2
    assert "En cours" not in items  # jamais quitté -> pas d'échantillon
    assert d["total_median"] == 4


def test_oscillation_counts_each_visit_separately():
    """Même garantie que dispersion_etapes.py : un aller-retour dans le
    workflow produit un échantillon par visite, jamais fusionné ni perdu."""
    issue = make_issue(
        "KEY-1", status="En cours", created="2024-01-01T00:00:00+00:00",
        status_history=[
            ("2024-01-02T00:00:00+00:00", "À faire", "En cours"),     # "À faire" #1 : 1j
            ("2024-01-05T00:00:00+00:00", "En cours", "À faire"),     # "En cours" #1 : 3j
            ("2024-01-09T00:00:00+00:00", "À faire", "En cours"),     # "À faire" #2 : 4j
        ],
    )
    conf = {**DEFAULT_CONF, "workflow": WORKFLOW}

    out = tpe_mod.compute([issue], [], conf)
    items = {r["name"]: r for r in out["temps_par_etape"]["items"]}

    assert items["À faire"]["count"] == 2
    assert items["À faire"]["median"] == 2.5  # médiane de [1, 4]


def test_done_status_excluded():
    issue = make_issue(
        "KEY-1", status="En cours", created="2024-01-01T00:00:00+00:00",
        status_history=[
            ("2024-01-02T00:00:00+00:00", "À faire", "En cours"),
            ("2024-01-05T00:00:00+00:00", "En cours", "Terminé(e)"),
            ("2024-01-08T00:00:00+00:00", "Terminé(e)", "En cours"),  # réouverture
        ],
    )
    conf = {**DEFAULT_CONF, "workflow": WORKFLOW}

    out = tpe_mod.compute([issue], [], conf)
    names = {r["name"] for r in out["temps_par_etape"]["items"]}

    assert "Terminé(e)" not in names


def test_instant_transition_excluded_by_default():
    issue = make_issue(
        "KEY-1", status="En cours", created="2024-01-01T00:00:00+00:00",
        status_history=[("2024-01-01T00:00:03+00:00", "À faire", "En cours")],  # 3s
    )
    conf = {**DEFAULT_CONF, "workflow": WORKFLOW}

    out = tpe_mod.compute([issue], [], conf)

    assert out == {"temps_par_etape": None}


def test_groups_aggregate_member_medians():
    workflow = ["Bac à sable", "Affinage technique", "À faire", "En cours", "Terminé(e)"]
    groups = {
        "À faire": ["Bac à sable", "Affinage technique", "À faire"],
        "En cours": ["En cours"],
        "Terminé": ["Terminé(e)"],
    }
    issue = make_issue(
        "KEY-1", status="Terminé(e)", created="2024-01-01T00:00:00+00:00",
        status_history=[
            ("2024-01-03T00:00:00+00:00", "Bac à sable", "Affinage technique"),   # 2j
            ("2024-01-05T00:00:00+00:00", "Affinage technique", "À faire"),       # 2j
            ("2024-01-08T00:00:00+00:00", "À faire", "En cours"),                 # 3j
            ("2024-01-10T00:00:00+00:00", "En cours", "Terminé(e)"),              # 2j
        ],
    )
    conf = {**DEFAULT_CONF, "workflow": workflow, "cfd": {"groups": groups}}

    out = tpe_mod.compute([issue], [], conf)
    d = out["temps_par_etape"]

    assert d["group_labels"] == ["À faire", "En cours", "Terminé"]
    by_label = {g["label"]: g for g in d["groups"]}
    assert by_label["À faire"]["median_sum"] == 7  # 2 + 2 + 3
    assert by_label["À faire"]["n_statuses"] == 3
    assert by_label["En cours"]["median_sum"] == 2
    assert "Terminé" not in by_label  # aucun statut du groupe n'a d'échantillon affiché
    assert d["total_median"] == 9


def test_non_us_types_excluded():
    issue = make_issue(
        "KEY-1", itype="Tâche", status="En cours", created="2024-01-01T00:00:00+00:00",
        status_history=[("2024-01-02T00:00:00+00:00", "À faire", "En cours")],
    )
    conf = {**DEFAULT_CONF, "workflow": WORKFLOW}

    out = tpe_mod.compute([issue], [], conf)

    assert out == {"temps_par_etape": None}


def test_us_count_scoped_to_displayed_statuses():
    """Contrairement à `dispersion_etapes.us_count` (tout `workflow`), le
    dénominateur ici ne porte que sur les statuts réellement affichés — un
    ticket qui n'a contribué qu'à un statut terminal ne doit pas compter."""
    issue_shown = make_issue(
        "KEY-1", status="En cours", created="2024-01-01T00:00:00+00:00",
        status_history=[("2024-01-04T00:00:00+00:00", "À faire", "En cours")],
    )
    conf = {**DEFAULT_CONF, "workflow": WORKFLOW}

    out = tpe_mod.compute([issue_shown], [], conf)

    assert out["temps_par_etape"]["us_count"] == 1
