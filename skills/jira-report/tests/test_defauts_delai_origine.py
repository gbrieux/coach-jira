from datetime import datetime, timezone

import indicators.defauts_delai_origine as ddo
from fixtures import DEFAULT_CONF, make_issue


def _conf(**overrides):
    return {**DEFAULT_CONF, **overrides}


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat()


def test_no_matching_issues_returns_none():
    assert ddo.compute([], [], _conf())["defauts_delai_origine"] is None


def test_delay_stats_in_calendar_days_no_window_restriction():
    conf = _conf(anomaly_types=["Anomalie"], incident_types=["Incident"], work_types=["Travaux"])
    issues = [
        make_issue("A-1", itype="Anomalie", status="Terminé(e)",
                    created="2025-01-01T00:00:00+00:00", resolutiondate="2025-01-11T00:00:00+00:00"),  # 10j
        make_issue("A-2", itype="Anomalie", status="En cours",
                    created="2025-01-01T00:00:00+00:00"),  # pas résolu -> hors calcul
        make_issue("I-1", itype="Incident", status="Terminé(e)",
                    created="2025-01-01T00:00:00+00:00", resolutiondate="2025-01-03T00:00:00+00:00"),  # 2j
        make_issue("W-1", itype="Travaux", status="Terminé(e)",
                    created="2025-01-01T00:00:00+00:00", resolutiondate="2025-01-06T00:00:00+00:00"),  # 5j
    ]
    out = ddo.compute(issues, [], conf)["defauts_delai_origine"]
    assert out["delay"]["anomalie"]["count"] == 1
    assert out["delay"]["anomalie"]["median"] == 10
    assert out["delay"]["incident"]["count"] == 1
    assert out["delay"]["incident"]["median"] == 2
    assert out["delay"]["travaux"]["count"] == 1
    assert out["delay"]["travaux"]["median"] == 5


def test_origin_by_parent_and_no_parent():
    now = _now()
    conf = _conf(anomaly_types=["Anomalie"], incident_types=["Incident"], work_types=["Travaux"],
                 sprint_start_date=now.strftime("%Y-%m-%d"))
    issues = [
        make_issue("A-1", itype="Anomalie", status="Ouvert", created=_iso(now),
                    parent=("PRJ-1", "Souscription en ligne")),
        make_issue("I-1", itype="Incident", status="Ouvert", created=_iso(now),
                    parent=("PRJ-1", "Souscription en ligne")),
        make_issue("W-1", itype="Travaux", status="Ouvert", created=_iso(now),
                    parent=("PRJ-1", "Souscription en ligne")),
        make_issue("A-2", itype="Anomalie", status="Ouvert", created=_iso(now)),  # pas de parent
    ]
    out = ddo.compute(issues, [], conf)["defauts_delai_origine"]
    by_key = {p["key"]: p for p in out["origin"]["parents"]}
    assert by_key["PRJ-1"] == {"key": "PRJ-1", "name": "Souscription en ligne",
                                "anomalie": 1, "incident": 1, "travaux": 1}
    assert out["origin"]["no_parent"] == {"anomalie": 1, "incident": 0, "travaux": 0}


def test_origin_beyond_top_n_goes_to_other():
    now = _now()
    conf = _conf(anomaly_types=["Anomalie"], sprint_start_date=now.strftime("%Y-%m-%d"))
    # 7 parents distincts, un ticket chacun -> le 7e (le moins chargé) doit
    # sortir du top 6 (ddo.TOP_N_PARENTS) et tomber dans "other".
    issues = [
        make_issue(f"A-{i}", itype="Anomalie", status="Ouvert", created=_iso(now),
                    parent=(f"PRJ-{i}", f"Parent {i}"))
        for i in range(7)
    ]
    out = ddo.compute(issues, [], conf)["defauts_delai_origine"]
    assert len(out["origin"]["parents"]) == 6
    assert out["origin"]["other"]["anomalie"] == 1
