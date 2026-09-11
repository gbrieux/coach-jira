import indicators.tempo_types as tempo_types
from fixtures import DEFAULT_CONF, make_issue


def _conf(**overrides):
    return {**DEFAULT_CONF, **overrides}


def test_no_tempo_data_returns_none():
    conf = _conf(tempo_worklogs=None)
    issues = [make_issue("KEY-1", id="1", itype="User Story")]
    assert tempo_types.compute(issues, [], conf)["tempo_types"] is None


def test_buckets_conso_by_month_and_ticket_type():
    conf = _conf(sprint_start_date="2026-01-01", tempo_worklogs=[
        {"date": "2026-01-05", "seconds": 28800, "issue_id": "1"},   # US -> 1 jh, janvier
        {"date": "2026-01-20", "seconds": 14400, "issue_id": "2"},   # Incident -> 0.5 jh, janvier
        {"date": "2026-02-10", "seconds": 57600, "issue_id": "1"},   # US -> 2 jh, février
    ])
    issues = [
        make_issue("KEY-1", id="1", itype="User Story"),
        make_issue("KEY-2", id="2", itype="Incident"),
    ]

    out = tempo_types.compute(issues, [], conf)["tempo_types"]
    jan = out["categories"].index("01/01/2026")
    fev = out["categories"].index("01/02/2026")

    assert out["series"]["User Story"][jan] == 1.0
    assert out["series"]["User Story"][fev] == 2.0
    assert out["series"]["Incident"][jan] == 0.5
    assert out["series"]["Incident"][fev] == 0.0
    assert out["totals_jh"] == {"User Story": 3.0, "Incident": 0.5}
    assert out["total_jh"] == 3.5
    # trié par jh décroissant -> le type dominant en premier
    assert out["types_order"] == ["User Story", "Incident"]


def test_worklog_without_matching_issue_is_classed_inconnu():
    conf = _conf(sprint_start_date="2026-01-01", tempo_worklogs=[
        {"date": "2026-01-05", "seconds": 28800, "issue_id": "999"},
    ])
    out = tempo_types.compute([], [], conf)["tempo_types"]
    jan = out["categories"].index("01/01/2026")
    assert out["series"]["Inconnu"][jan] == 1.0


def test_month_range_wraps_year():
    assert tempo_types._month_range((2025, 11), (2026, 2)) == [
        (2025, 11), (2025, 12), (2026, 1), (2026, 2)
    ]


def test_no_matching_worklogs_returns_none():
    conf = _conf(tempo_worklogs=[])
    assert tempo_types.compute([], [], conf)["tempo_types"] is None
