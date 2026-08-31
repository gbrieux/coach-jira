from datetime import datetime, timedelta, timezone

import indicators.burndown as burndown
from fixtures import DEFAULT_CONF, make_issue, make_sprint


def test_burndown_us_and_sp():
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=2)
    end = now + timedelta(days=2)
    sprints = [make_sprint("Sprint 1", "active", start.isoformat(), end.isoformat())]

    resolved_day1 = (start + timedelta(days=1)).isoformat()
    issues = [
        make_issue("KEY-1", status="Terminé(e)", sp=5, sprints=["Sprint 1"],
                    resolutiondate=resolved_day1),
        make_issue("KEY-2", status="En cours", sp=3, sprints=["Sprint 1"]),
        # hors périmètre US -> ignorée du scope et du reste-à-faire
        make_issue("KEY-3", itype="Bug", status="Terminé(e)", sp=99, sprints=["Sprint 1"]),
    ]

    out = burndown.compute(issues, sprints, DEFAULT_CONF)
    bd = out["burndown_sprint"]

    assert bd["scope"] == 2
    assert bd["scope_sp"] == 8
    assert len(bd["ideal_sp"]) == len(bd["categories"])
    assert len(bd["real_sp"]) == len(bd["categories"])
    assert bd["ideal_sp"][0] == 8

    # jour 0 : rien terminé -> reste = périmètre entier
    assert (bd["real"][0], bd["real_sp"][0]) == (2, 8)
    # jour 1 : KEY-1 terminée (1 US, 5 SP)
    assert (bd["real"][1], bd["real_sp"][1]) == (1, 3)


def test_no_active_sprint_returns_none():
    sprints = [make_sprint("Sprint 1", "closed", "2026-01-01T00:00:00Z", "2026-01-14T23:59:59Z")]
    out = burndown.compute([], sprints, DEFAULT_CONF)
    assert out["burndown_sprint"] is None
