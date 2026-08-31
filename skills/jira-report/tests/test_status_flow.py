import indicators.status_flow as status_flow
from fixtures import DEFAULT_CONF, make_issue


def test_ordered_by_configured_workflow():
    issues = [
        make_issue("KEY-1", status="Terminé(e)"),
        make_issue("KEY-2", status="Bac à sable"),
        make_issue("KEY-3", status="Bac à sable"),
        make_issue("KEY-4", status="En cours"),
    ]
    conf = {**DEFAULT_CONF, "workflow": ["Bac à sable", "En cours", "Terminé(e)"]}

    out = status_flow.compute(issues, [], conf)

    assert list(out["status_counts_us"].keys()) == ["Bac à sable", "En cours", "Terminé(e)"]
    assert out["status_counts_us"] == {"Bac à sable": 2, "En cours": 1, "Terminé(e)": 1}


def test_unknown_status_appended_at_end():
    issues = [
        make_issue("KEY-1", status="Terminé(e)"),
        make_issue("KEY-2", status="Statut Oublié"),
        make_issue("KEY-3", status="Statut Oublié"),
    ]
    conf = {**DEFAULT_CONF, "workflow": ["Terminé(e)"]}

    out = status_flow.compute(issues, [], conf)

    assert list(out["status_counts_us"].keys()) == ["Terminé(e)", "Statut Oublié"]


def test_done_statuses_us_from_config():
    issues = [
        make_issue("KEY-1", status="Terminé(e)"),
        make_issue("KEY-2", status="Bac à sable"),
        make_issue("KEY-3", status="En cours"),
    ]
    conf = {**DEFAULT_CONF, "workflow": ["Bac à sable", "En cours", "Terminé(e)"]}

    out = status_flow.compute(issues, [], conf)

    assert out["done_statuses_us"] == ["Terminé(e)"]


def test_no_workflow_falls_back_to_frequency():
    issues = [
        make_issue("KEY-1", status="Rare"),
        make_issue("KEY-2", status="Fréquent"),
        make_issue("KEY-3", status="Fréquent"),
    ]
    conf = {**DEFAULT_CONF, "workflow": []}

    out = status_flow.compute(issues, [], conf)

    assert list(out["status_counts_us"].keys()) == ["Fréquent", "Rare"]
