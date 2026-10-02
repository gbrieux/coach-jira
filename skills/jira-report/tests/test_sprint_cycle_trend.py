import indicators.sprint_cycle_trend as sprint_cycle_trend
from fixtures import DEFAULT_CONF, make_issue, make_sprint

CONF = {**DEFAULT_CONF, "done_statuses": ["Terminé(e)", "Attente livraison recette métier"]}
SPRINTS = [make_sprint("Sprint 1", "closed", "2026-01-05T08:00:00+00:00", "2026-01-26T08:00:00+00:00"),
           make_sprint("Sprint 2", "active", "2026-01-26T08:00:00+00:00", "2026-02-16T08:00:00+00:00")]


def _done(key, sprints, created, done_at):
    return make_issue(key, status="Terminé(e)", sprints=sprints, created=created,
                      status_history=[(done_at, "En cours", "Attente livraison recette métier"),
                                      ("2026-03-01T08:00:00+00:00", "Attente livraison recette métier", "Terminé(e)")])


def test_cycle_grouped_by_entry_sprint():
    issues = [
        # entrée S1 (créée avant -> début du sprint 05/01), finie 15/01 -> 10 j
        _done("K-1", ["Sprint 1"], "2025-12-01T08:00:00+00:00", "2026-01-15T08:00:00+00:00"),
        # entrée S1, débordée sur S2, finie 04/02 -> 30 j, comptée dans S1
        _done("K-2", ["Sprint 1", "Sprint 2"], "2025-12-01T08:00:00+00:00", "2026-02-04T08:00:00+00:00"),
        # entrée S2 (début 26/01), finie 31/01 -> 5 j
        _done("K-3", ["Sprint 2"], "2026-01-02T08:00:00+00:00", "2026-01-31T08:00:00+00:00"),
        # entrée S2, pas terminée -> open
        make_issue("K-4", status="En cours", sprints=["Sprint 2"], created="2026-01-02T08:00:00+00:00"),
        # hors US
        make_issue("K-5", itype="Bug", status="Terminé(e)", sprints=["Sprint 1"],
                   created="2026-01-06T08:00:00+00:00", resolutiondate="2026-01-07T08:00:00+00:00"),
    ]

    items = sprint_cycle_trend.compute(issues, SPRINTS, CONF)["sprint_cycle_trend"]["items"]

    s1, s2 = items
    assert (s1["sprint"], s1["count"], s1["open"], s1["median"]) == ("Sprint 1", 2, 0, 20.0)
    assert (s1["p15"], s1["p85"]) == (13.0, 27.0)
    assert (s2["count"], s2["open"], s2["median"], s2["state"]) == (1, 1, 5.0, "active")


def test_sprint_without_measured_us_has_none_values():
    issues = [_done("K-1", ["Sprint 1"], "2025-12-01T08:00:00+00:00", "2026-01-15T08:00:00+00:00")]
    s2 = sprint_cycle_trend.compute(issues, SPRINTS, CONF)["sprint_cycle_trend"]["items"][1]
    assert s2["count"] == 0 and s2["median"] is None and s2["p85"] is None


def test_unknown_sprint_ignored_and_empty_returns_none():
    issues = [_done("K-1", ["Sprint X"], "2025-12-01T08:00:00+00:00", "2026-01-15T08:00:00+00:00")]
    assert sprint_cycle_trend.compute(issues, SPRINTS, CONF)["sprint_cycle_trend"] is None
    assert sprint_cycle_trend.compute([], [], CONF)["sprint_cycle_trend"] is None


def test_future_sprints_excluded():
    sprints = SPRINTS + [make_sprint("Sprint 3", "future", "2026-02-16T08:00:00+00:00", "2026-03-09T08:00:00+00:00")]
    issues = [_done("K-1", ["Sprint 1"], "2025-12-01T08:00:00+00:00", "2026-01-15T08:00:00+00:00")]
    items = sprint_cycle_trend.compute(issues, sprints, CONF)["sprint_cycle_trend"]["items"]
    assert [it["sprint"] for it in items] == ["Sprint 1", "Sprint 2"]
