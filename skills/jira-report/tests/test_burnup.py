import indicators.burnup as burnup
from fixtures import DEFAULT_CONF, make_issue, make_sprint


def test_rollup_and_release_us_and_sp_cumuls():
    sprints = [
        make_sprint("Sprint 1", "closed", "2026-01-01T00:00:00Z", "2026-01-14T23:59:59Z"),
        make_sprint("Sprint 2", "active", "2026-01-15T00:00:00Z", "2026-01-28T23:59:59Z"),
    ]
    issues = [
        # créée avant le 1er sprint -> Sprint 0 ; résolue pendant le Sprint 1
        make_issue("KEY-1", created="2025-12-20T10:00:00Z",
                    resolutiondate="2026-01-05T10:00:00Z", status="Terminé(e)", sp=5),
        # ajoutée et terminée pendant le Sprint 1
        make_issue("KEY-2", created="2026-01-03T10:00:00Z",
                    resolutiondate="2026-01-10T10:00:00Z", status="Terminé(e)", sp=3),
        # ajoutée pendant le Sprint 2, pas terminée
        make_issue("KEY-3", created="2026-01-16T10:00:00Z", status="En cours", sp=8),
        # type hors périmètre US -> ignorée entièrement
        make_issue("KEY-4", itype="Bug", created="2026-01-03T10:00:00Z", sp=13),
    ]

    out = burnup.compute(issues, sprints, DEFAULT_CONF)
    rollup = {r["sprint"]: r for r in out["burnup"]}

    s0 = rollup["Sprint 0"]
    assert (s0["added_us"], s0["done_us"]) == (1, 0)
    assert (s0["scope_cumul_us"], s0["done_cumul_us"]) == (1, 0)
    assert (s0["added_sp"], s0["done_sp"]) == (5, 0)
    assert (s0["scope_cumul_sp"], s0["done_cumul_sp"]) == (5, 0)

    s1 = rollup["Sprint 1"]
    # KEY-1 (résolue ici bien que créée avant S1) + KEY-2 sont toutes deux
    # terminées dans la fenêtre du Sprint 1.
    assert (s1["added_us"], s1["done_us"]) == (1, 2)
    assert (s1["scope_cumul_us"], s1["done_cumul_us"]) == (2, 2)
    assert (s1["added_sp"], s1["done_sp"]) == (3, 8)
    assert (s1["scope_cumul_sp"], s1["done_cumul_sp"]) == (8, 8)

    s2 = rollup["Sprint 2"]
    assert (s2["added_us"], s2["done_us"]) == (1, 0)
    assert (s2["scope_cumul_us"], s2["done_cumul_us"]) == (3, 2)
    assert (s2["added_sp"], s2["done_sp"]) == (8, 0)
    assert (s2["scope_cumul_sp"], s2["done_cumul_sp"]) == (16, 8)

    release = out["burnup_release"]
    assert release["scope_cumul_sp"][-1] == 16
    assert release["done_cumul_sp"][-1] == 8
    assert len(release["scope_cumul_sp"]) == len(release["categories"])
    assert len(release["done_cumul_sp"]) == len(release["categories"])


def test_no_sprints_returns_empty_rollup():
    out = burnup.compute([], [], DEFAULT_CONF)
    assert out["burnup"] == []
    assert out["burnup_release"] is None
