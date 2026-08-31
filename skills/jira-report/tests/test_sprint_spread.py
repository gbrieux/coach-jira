import indicators.sprint_spread as sprint_spread
from fixtures import DEFAULT_CONF, make_issue


def test_counts_us_by_number_of_distinct_sprints():
    issues = [
        # terminée sur son 1er sprint
        make_issue("KEY-1", status="Terminé(e)", sprints=["Sprint 1"]),
        # terminée sur son 1er sprint aussi
        make_issue("KEY-2", status="Terminé(e)", sprints=["Sprint 3"]),
        # reportée une fois : 2 sprints traversés
        make_issue("KEY-3", status="Terminé(e)", sprints=["Sprint 1", "Sprint 2"]),
        # pas terminée -> hors périmètre
        make_issue("KEY-4", status="En cours", sprints=["Sprint 1", "Sprint 2", "Sprint 3"]),
        # terminée mais jamais affectée à un sprint -> exclue (pas de sprint "pris")
        make_issue("KEY-5", status="Terminé(e)", sprints=None),
        # type hors périmètre US -> ignorée entièrement
        make_issue("KEY-6", itype="Bug", status="Terminé(e)", sprints=["Sprint 1"]),
    ]

    out = sprint_spread.compute(issues, [], DEFAULT_CONF)

    assert out["sprint_spread"] == {1: 2, 2: 1}


def test_no_measured_us_returns_empty_dict():
    out = sprint_spread.compute([], [], DEFAULT_CONF)
    assert out["sprint_spread"] == {}
