from datetime import datetime, timezone

import indicators.cumulative_flow_diagram as cfd_mod
from fixtures import DEFAULT_CONF, make_issue

WORKFLOW = ["À faire", "En cours", "Terminé(e)"]


def test_no_workflow_returns_none():
    issues = [make_issue("KEY-1", status="À faire", created="2024-01-01T00:00:00+00:00")]
    conf = {**DEFAULT_CONF, "workflow": []}

    out = cfd_mod.compute(issues, [], conf)

    assert out == {"cfd": None}


def test_reconstructs_daily_stage_counts_from_changelog():
    issue1 = make_issue(
        "KEY-1", status="Terminé(e)", created="2024-01-01T00:00:00+00:00",
        status_history=[
            ("2024-01-03T09:00:00+00:00", "À faire", "En cours"),
            ("2024-01-06T09:00:00+00:00", "En cours", "Terminé(e)"),
        ],
    )
    issue2 = make_issue("KEY-2", status="À faire", created="2024-01-02T00:00:00+00:00")
    conf = {**DEFAULT_CONF, "workflow": WORKFLOW}

    out = cfd_mod.compute([issue1, issue2], [], conf)
    cfd = out["cfd"]
    reached = cfd["reached"]

    assert cfd["categories"][0] == "01/01"
    # jour 0 (01/01) : seule KEY-1 existe, en "À faire"
    assert [r[0] for r in reached] == [1, 0, 0]
    # jour 1 (02/01) : KEY-2 apparaît, toujours "À faire" pour les deux
    assert [r[1] for r in reached] == [2, 0, 0]
    # jour 2 (03/01) : KEY-1 passe "En cours"
    assert [r[2] for r in reached] == [2, 1, 0]
    # jour 5 (06/01) : KEY-1 termine, KEY-2 n'a jamais bougé
    assert [r[5] for r in reached] == [2, 1, 1]

    assert cfd["totals"] == {"scope": 2, "done": 1, "in_progress": 1}


def test_unknown_status_in_history_keeps_last_known_stage():
    issue = make_issue(
        "KEY-1", status="Terminé(e)", created="2024-01-01T00:00:00+00:00",
        status_history=[
            ("2024-01-02T09:00:00+00:00", "À faire", "En cours"),
            ("2024-01-03T09:00:00+00:00", "En cours", "Statut Externe Inconnu"),
            ("2024-01-04T09:00:00+00:00", "Statut Externe Inconnu", "Terminé(e)"),
        ],
    )
    conf = {**DEFAULT_CONF, "workflow": WORKFLOW}

    out = cfd_mod.compute([issue], [], conf)
    reached = out["cfd"]["reached"]

    # jour 3 (04/01) : le statut inconnu n'a pas fait reculer le curseur,
    # la transition suivante (Terminé(e)) s'applique normalement.
    assert [r[3] for r in reached] == [1, 1, 1]


def test_renamed_status_resolved_via_id():
    """Un statut renommé depuis (même id, nouveau libellé) doit être reconnu
    dans les vieilles transitions du changelog, qui portent l'ancien libellé
    (`toString`) — cas réel observé : id 10003 "To Do" -> "À faire", id
    10002 "Done" -> "Terminé(e)"."""
    issue1 = make_issue(
        "KEY-1", status="Terminé(e)", status_id="10002", created="2024-01-01T00:00:00+00:00",
        status_history=[
            ("2024-01-02T09:00:00+00:00", "10003", "To Do", "10002", "Done"),
        ],
    )
    # Fournit la résolution id -> libellé actuel pour "10003" (issue non-US,
    # exclue du CFD elle-même mais scannée pour la table de résolution).
    issue2 = make_issue("KEY-2", itype="Tâche", status="À faire", status_id="10003",
                         created="2024-01-01T00:00:00+00:00")
    conf = {**DEFAULT_CONF, "workflow": WORKFLOW}

    out = cfd_mod.compute([issue1, issue2], [], conf)
    reached = out["cfd"]["reached"]

    assert [r[1] for r in reached] == [1, 1, 1]
    assert out["cfd"]["totals"] == {"scope": 1, "done": 1, "in_progress": 0}


def test_non_us_types_excluded():
    issues = [
        make_issue("KEY-1", itype="Tâche", status="Terminé(e)", created="2024-01-01T00:00:00+00:00"),
    ]
    conf = {**DEFAULT_CONF, "workflow": WORKFLOW}

    out = cfd_mod.compute(issues, [], conf)

    assert out == {"cfd": None}


def test_cfd_groups_merge_several_statuses_into_one_stage():
    workflow = ["Bac à sable", "Affinage technique", "À faire", "En cours", "Terminé(e)"]
    groups = {
        "À faire": ["Bac à sable", "Affinage technique", "À faire"],
        "En cours": ["En cours"],
        "Terminé": ["Terminé(e)"],
    }
    issue = make_issue(
        "KEY-1", status="Terminé(e)", created="2024-01-01T00:00:00+00:00",
        status_history=[
            ("2024-01-03T09:00:00+00:00", "Bac à sable", "Affinage technique"),
            ("2024-01-05T09:00:00+00:00", "Affinage technique", "À faire"),
            ("2024-01-07T09:00:00+00:00", "À faire", "En cours"),
            ("2024-01-09T09:00:00+00:00", "En cours", "Terminé(e)"),
        ],
    )
    conf = {**DEFAULT_CONF, "workflow": workflow, "cfd": {"groups": groups}}

    out = cfd_mod.compute([issue], [], conf)
    cfd = out["cfd"]

    assert cfd["workflow"] == ["À faire", "En cours", "Terminé"]
    reached = cfd["reached"]
    # jour 1 : "Bac à sable" -> groupe "À faire"
    assert [r[1] for r in reached] == [1, 0, 0]
    # jour 3 : passage "Affinage technique", même groupe "À faire" -> pas de changement
    assert [r[3] for r in reached] == [1, 0, 0]
    # jour 5 : passage "À faire" (le statut), toujours le même groupe -> pas de changement
    assert [r[5] for r in reached] == [1, 0, 0]
    # jour 7 : "En cours" -> groupe "En cours"
    assert [r[7] for r in reached] == [1, 1, 0]
    # jour 9 : "Terminé(e)" -> groupe "Terminé"
    assert [r[9] for r in reached] == [1, 1, 1]


def test_cfd_groups_missing_status_warns_and_ignores(capsys):
    workflow = ["À faire", "En cours", "Bloqué", "Terminé(e)"]
    groups = {"À faire": ["À faire"], "En cours": ["En cours"], "Terminé": ["Terminé(e)"]}
    issues = [make_issue("KEY-1", status="À faire", created="2024-01-01T00:00:00+00:00")]
    conf = {**DEFAULT_CONF, "workflow": workflow, "cfd": {"groups": groups}}

    out = cfd_mod.compute(issues, [], conf)

    assert out["cfd"] is not None
    captured = capsys.readouterr()
    assert "Bloqué" in captured.out


def test_cfd_date_bounds_configured():
    issue1 = make_issue("KEY-1", status="Terminé(e)", created="2024-01-01T00:00:00+00:00")
    # Créée après la fenêtre configurée -> ne doit pas compter dans les totaux.
    issue2 = make_issue("KEY-2", status="À faire", created="2024-01-10T00:00:00+00:00")
    conf = {**DEFAULT_CONF, "workflow": WORKFLOW,
            "cfd": {"start_date": "2024-01-05", "end_date": "2024-01-08"}}

    out = cfd_mod.compute([issue1, issue2], [], conf)
    cfd = out["cfd"]

    assert cfd["categories"] == ["05/01", "06/01", "07/01", "08/01"]
    assert cfd["totals"] == {"scope": 1, "done": 1, "in_progress": 0}


def test_cfd_end_date_in_future_capped_to_today():
    issue = make_issue("KEY-1", status="À faire", created="2024-01-01T00:00:00+00:00")
    conf = {**DEFAULT_CONF, "workflow": WORKFLOW, "cfd": {"end_date": "2099-01-01"}}

    out = cfd_mod.compute([issue], [], conf)
    today = datetime.now(timezone.utc).date()

    assert out["cfd"]["categories"][-1] == today.strftime("%d/%m")
