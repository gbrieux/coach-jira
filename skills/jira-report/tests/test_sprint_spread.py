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


# ------------------------------------------------------- sprint_cycle_time
from fixtures import make_sprint

CONF_CYCLE = {**DEFAULT_CONF,
              "done_statuses": ["Terminé(e)", "Attente livraison recette métier"],
              "workflow": ["À faire", "En cours", "Attente livraison recette métier", "Terminé(e)"]}
SPRINTS = [make_sprint("Sprint 1", "closed", "2026-01-05T08:00:00+00:00", "2026-01-26T08:00:00+00:00"),
           make_sprint("Sprint 2", "closed", "2026-01-26T08:00:00+00:00", "2026-02-16T08:00:00+00:00")]


def _with_sprint_added(issue, when):
    issue.setdefault("changelog", {"histories": []})["histories"].append(
        {"created": when, "items": [{"field": "Sprint", "from": "", "fromString": "", "to": "1", "toString": "Sprint 1"}]})
    return issue


def test_cycle_starts_at_sprint_start_when_added_before():
    it = make_issue("KEY-1", status="Terminé(e)", sprints=["Sprint 1"], created="2025-12-01T08:00:00+00:00",
                    status_history=[("2026-01-15T08:00:00+00:00", "En cours", "Attente livraison recette métier"),
                                    ("2026-01-20T08:00:00+00:00", "Attente livraison recette métier", "Terminé(e)")])
    _with_sprint_added(it, "2025-12-20T08:00:00+00:00")

    ct = sprint_spread.compute([it], SPRINTS, CONF_CYCLE)["sprint_cycle_time"]

    # début du sprint (05/01) -> 1re étape terminée (15/01), pas Terminé(e)
    assert ct["count"] == 1 and ct["median"] == 10.0
    assert ct["done_label"] == "Attente livraison recette métier"


def test_cycle_starts_at_addition_when_added_mid_sprint():
    it = make_issue("KEY-2", status="Terminé(e)", sprints=["Sprint 1", "Sprint 2"], created="2026-01-02T08:00:00+00:00",
                    status_history=[("2026-01-30T08:00:00+00:00", "En cours", "Terminé(e)")])
    _with_sprint_added(it, "2026-01-10T08:00:00+00:00")

    ct = sprint_spread.compute([it], SPRINTS, CONF_CYCLE)["sprint_cycle_time"]

    assert ct["median"] == 20.0  # 10/01 -> 30/01, sur deux sprints


def test_cycle_falls_back_to_creation_and_resolutiondate():
    # pas de changelog sprint (créée dans le sprint), pas de transition -> resolutiondate
    it = make_issue("KEY-3", status="Terminé(e)", sprints=["Sprint 1"], created="2026-01-08T08:00:00+00:00",
                    resolutiondate="2026-01-12T08:00:00+00:00")

    ct = sprint_spread.compute([it], SPRINTS, CONF_CYCLE)["sprint_cycle_time"]

    assert ct["median"] == 4.0


def test_cycle_excludes_non_us_and_unfinished():
    issues = [
        make_issue("KEY-4", itype="Bug", status="Terminé(e)", sprints=["Sprint 1"],
                   created="2026-01-08T08:00:00+00:00", resolutiondate="2026-01-12T08:00:00+00:00"),
        make_issue("KEY-5", status="En cours", sprints=["Sprint 1"], created="2026-01-08T08:00:00+00:00"),
    ]
    ct = sprint_spread.compute(issues, SPRINTS, CONF_CYCLE)["sprint_cycle_time"]
    assert ct["count"] == 0
