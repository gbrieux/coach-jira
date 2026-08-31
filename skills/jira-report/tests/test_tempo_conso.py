import indicators.tempo_conso as tempo_conso
from fixtures import DEFAULT_CONF, make_issue, make_sprint


def _conf(**overrides):
    return {**DEFAULT_CONF, **overrides}


def test_no_tempo_data_returns_none():
    conf = _conf(tempo_worklogs=None)
    issues = [make_issue("KEY-1", status="Terminé(e)", resolutiondate="2026-01-05T10:00:00Z")]
    sprints = [make_sprint("Sprint 1", "closed", "2026-01-01T00:00:00Z", "2026-01-14T23:59:59Z")]
    assert tempo_conso.compute(issues, sprints, conf)["tempo_conso"] is None


def test_buckets_conso_by_sprint_date_window_and_pairs_with_done_us():
    sprints = [
        make_sprint("Sprint 1", "closed", "2026-01-01T00:00:00Z", "2026-01-14T23:59:59Z"),
        make_sprint("Sprint 2", "active", "2026-01-15T00:00:00Z", "2026-01-28T23:59:59Z"),
    ]
    issues = [
        # terminée pendant le Sprint 1
        make_issue("KEY-1", created="2025-12-20T10:00:00Z",
                    resolutiondate="2026-01-05T10:00:00Z", status="Terminé(e)"),
        # pas terminée -> ne compte pas dans done_us
        make_issue("KEY-2", created="2026-01-16T10:00:00Z", status="En cours"),
    ]
    conf = _conf(tempo_worklogs=[
        {"date": "2026-01-05", "seconds": 28800},   # dans Sprint 1 -> 1 jh
        {"date": "2026-01-20", "seconds": 14400},   # dans Sprint 2 -> 0.5 jh
        {"date": "2025-12-01", "seconds": 57600},   # avant le 1er sprint -> Sprint 0 (backlog) -> 2 jh
    ])

    out = tempo_conso.compute(issues, sprints, conf)["tempo_conso"]
    by_prefix = {cat.split(" ")[0]: (conso, done)
                 for cat, conso, done in zip(out["categories"], out["conso_jh"], out["done_us"])}

    assert by_prefix["S0"] == (2.0, 0)
    assert by_prefix["S1"] == (1.0, 1)
    assert by_prefix["S2"] == (0.5, 0)
    assert out["total_conso_jh"] == 3.5
    assert out["total_done_us"] == 1
    assert out["avg_jh_per_us"] == 3.5


def test_no_rollup_returns_none():
    # tempo_worklogs présent mais aucun sprint -> _build_rollup ne peut rien
    # construire (voir burnup.py) -> indicateur absent plutôt qu'un graphique
    # avec un seul point trompeur.
    conf = _conf(tempo_worklogs=[{"date": "2026-01-05", "seconds": 28800}])
    issues = [make_issue("KEY-1", status="Terminé(e)", resolutiondate="2026-01-05T10:00:00Z")]
    assert tempo_conso.compute(issues, [], conf)["tempo_conso"] is None
