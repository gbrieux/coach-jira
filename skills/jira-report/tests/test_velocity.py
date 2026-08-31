import indicators.velocity as velocity
from fixtures import DEFAULT_CONF, make_issue, make_sprint


def test_velocity_us_and_sp():
    sprints = [
        make_sprint("Sprint 1", "closed", "2026-01-01T00:00:00Z", "2026-01-14T23:59:59Z"),
        make_sprint("Sprint 2", "active", "2026-01-15T00:00:00Z", "2026-01-28T23:59:59Z"),
    ]
    issues = [
        # engagée et terminée sur Sprint 1
        make_issue("KEY-1", status="Terminé(e)", sp=5, sprints=["Sprint 1"]),
        # engagée sur Sprint 1, reportée puis terminée sur Sprint 2
        make_issue("KEY-2", status="Terminé(e)", sp=8, sprints=["Sprint 1", "Sprint 2"]),
        # engagée et pas terminée sur Sprint 2
        make_issue("KEY-3", status="En cours", sp=3, sprints=["Sprint 2"]),
    ]

    out = velocity.compute(issues, sprints, DEFAULT_CONF)
    vel = {v["sprint"]: v for v in out["velocity"]}

    s1 = vel["Sprint 1"]
    assert (s1["engaged"], s1["done"]) == (2, 1)
    assert (s1["sp_engaged"], s1["sp_done"]) == (13, 5)

    s2 = vel["Sprint 2"]
    assert (s2["engaged"], s2["done"]) == (1, 1)
    assert (s2["sp_engaged"], s2["sp_done"]) == (3, 8)

    assert out["median_velocity_sp"] == 6.5
