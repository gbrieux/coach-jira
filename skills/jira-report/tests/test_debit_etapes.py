from datetime import datetime, timedelta, timezone

import indicators.debit_etapes as de_mod
from fixtures import DEFAULT_CONF, make_issue, make_sprint

WORKFLOW = ["À faire", "En cours", "Attente validation PO", "Terminé(e)"]
SPRINTS = [
    make_sprint("Sprint 1", "closed", "2024-01-01T00:00:00+00:00", "2024-01-15T00:00:00+00:00"),
    make_sprint("Sprint 2", "closed", "2024-01-15T00:00:00+00:00", "2024-01-29T00:00:00+00:00"),
    make_sprint("Sprint 3", "active", "2024-01-29T00:00:00+00:00", "2024-02-12T00:00:00+00:00"),
]
CONF = {**DEFAULT_CONF, "workflow": WORKFLOW, "debit_etapes": {"window_sprints": 2}}


def _issues():
    # Présente avant la fenêtre, fait un aller-retour En cours <-> Attente
    # validation PO, puis est livrée dans la fenêtre.
    a = make_issue("KEY-A", status="Terminé(e)", created="2023-12-20T00:00:00+00:00", status_history=[
        ("2024-01-05T00:00:00+00:00", "À faire", "En cours"),
        ("2024-01-10T00:00:00+00:00", "En cours", "Attente validation PO"),
        ("2024-01-12T00:00:00+00:00", "Attente validation PO", "En cours"),  # retour
        ("2024-01-14T00:00:00+00:00", "En cours", "Attente validation PO"),
        ("2024-01-20T00:00:00+00:00", "Attente validation PO", "Terminé(e)"),
    ])
    # Arrivée dans la fenêtre, jamais démarrée.
    b = make_issue("KEY-B", status="À faire", created="2024-01-03T00:00:00+00:00", status_history=[])
    # Arrivée dans la fenêtre, démarrée pendant le sprint actif (hors fenêtre).
    c = make_issue("KEY-C", status="En cours", created="2024-01-04T00:00:00+00:00", status_history=[
        ("2024-02-01T00:00:00+00:00", "À faire", "En cours"),
    ])
    return [a, b, c]


def test_no_workflow_returns_none():
    out = de_mod.compute(_issues(), SPRINTS, {**CONF, "workflow": []})

    assert out == {"debit_etapes": None}


def test_window_is_last_closed_sprints():
    d = de_mod.compute(_issues(), SPRINTS, CONF)["debit_etapes"]

    assert d["sprints"] == ["Sprint 1", "Sprint 2"]  # sprint actif exclu
    assert (d["start"], d["end"]) == ("2024-01-01", "2024-01-29")
    assert d["window_sprints"] == 2


def test_entries_exits_and_stock_per_status():
    d = de_mod.compute(_issues(), SPRINTS, CONF)["debit_etapes"]
    items = {r["name"]: r for r in d["items"]}

    todo = items["À faire"]
    assert (todo["entrees"], todo["sorties"]) == (2, 1)
    assert (todo["stock_debut"], todo["stock_fin"], todo["delta_stock"]) == (1, 2, 1)
    assert (todo["entrees_par_sprint"], todo["sorties_par_sprint"]) == (1.0, 0.5)
    assert todo["couverture_sprints"] == 4.0  # 2 en stock ÷ 0,5 sortie/sprint

    wip = items["En cours"]
    assert (wip["entrees"], wip["sorties"], wip["stock_fin"]) == (2, 2, 0)


def test_backward_transition_counted_as_retour():
    d = de_mod.compute(_issues(), SPRINTS, CONF)["debit_etapes"]
    items = {r["name"]: r for r in d["items"]}

    assert items["En cours"]["retours"] == 1
    assert items["Attente validation PO"]["retours"] == 0
    assert items["À faire"]["retours"] == 0


def test_done_status_excluded_but_counted_as_livree():
    d = de_mod.compute(_issues(), SPRINTS, CONF)["debit_etapes"]

    assert "Terminé(e)" not in {r["name"] for r in d["items"]}
    assert d["livrees"] == 1
    assert d["arrivees"] == 2
    assert d["livrees_par_sprint"] == 0.5


def test_accumulation_points_to_downstream_step():
    d = de_mod.compute(_issues(), SPRINTS, CONF)["debit_etapes"]

    assert d["accumulation"] == {"name": "À faire", "delta_stock": 1, "etape_aval": "En cours"}


def test_no_growing_stock_means_no_accumulation():
    issue = make_issue("KEY-1", status="En cours", created="2023-12-20T00:00:00+00:00", status_history=[
        ("2024-01-05T00:00:00+00:00", "À faire", "En cours"),
    ])
    d = de_mod.compute([issue], SPRINTS, CONF)["debit_etapes"]
    # "En cours" gagne 1 en stock — seul statut qui grossit, aval = statut suivant.
    assert d["accumulation"]["name"] == "En cours"

    issue = make_issue("KEY-1", status="Terminé(e)", created="2023-12-20T00:00:00+00:00", status_history=[
        ("2024-01-05T00:00:00+00:00", "À faire", "Terminé(e)"),
    ])
    d = de_mod.compute([issue], SPRINTS, CONF)["debit_etapes"]
    assert d["accumulation"] is None


def test_instant_visit_ignored_and_neighbours_merged():
    """Un passage de 3 s par "En cours" (automatisation) ne crée ni entrée en
    "En cours", ni fausse sortie/réentrée de "À faire"."""
    issue = make_issue("KEY-1", status="En cours", created="2024-01-02T00:00:00+00:00", status_history=[
        ("2024-01-03T00:00:00+00:00", "À faire", "En cours"),
        ("2024-01-03T00:00:03+00:00", "En cours", "À faire"),
        ("2024-01-08T00:00:00+00:00", "À faire", "En cours"),
    ])
    d = de_mod.compute([issue], SPRINTS, CONF)["debit_etapes"]
    items = {r["name"]: r for r in d["items"]}

    assert (items["À faire"]["entrees"], items["À faire"]["sorties"]) == (1, 1)
    assert items["À faire"]["retours"] == 0
    assert items["En cours"]["entrees"] == 1


def test_without_closed_sprint_falls_back_to_recent_days():
    created = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    issue = make_issue("KEY-1", status="À faire", created=created, status_history=[])

    d = de_mod.compute([issue], [], CONF)["debit_etapes"]

    assert d["sprints"] == []
    assert d["arrivees"] == 1
