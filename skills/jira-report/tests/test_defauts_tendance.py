from datetime import datetime, timezone, timedelta

import indicators.defauts_tendance as dt_mod
from fixtures import DEFAULT_CONF, make_issue


def _conf(**overrides):
    return {**DEFAULT_CONF, **overrides}


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat()


def test_no_matching_issues_returns_none():
    assert dt_mod.compute([], [], _conf())["defauts_tendance"] is None


def test_created_resolved_series_and_stock_within_current_month():
    now = _now()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    conf = _conf(anomaly_types=["Anomalie"], incident_types=["Incident"],
                 sprint_start_date=start.strftime("%Y-%m-%d"))
    issues = [
        # ouvert tout le mois : créé au début, jamais résolu
        make_issue("A-1", itype="Anomalie", status="Ouvert", created=_iso(start)),
        # créé et résolu dans le mois -> ne compte plus dans le stock en fin de mois
        make_issue("A-2", itype="Anomalie", status="Terminé(e)",
                    created=_iso(start), resolutiondate=_iso(now - timedelta(minutes=5))),
    ]
    out = dt_mod.compute(issues, [], conf)["defauts_tendance"]

    assert len(out["categories"]) == 1  # une seule fenêtre : le mois courant
    assert out["anomalie"]["created"] == [2]
    assert out["anomalie"]["resolved"] == [1]
    assert out["anomalie"]["stock_end"] == 1  # seul A-1 reste ouvert
    assert out["incident"]["created"] == [0]


def test_age_buckets_use_configured_bounds():
    now = _now()
    conf = _conf(anomaly_types=["Anomalie"], sprint_start_date=now.strftime("%Y-%m-%d"),
                 defect_age_buckets=[7, 30, 90])
    ages = [3, 15, 60, 200]  # une par tranche : 0-7j / 8-30j / 31-90j / +90j
    issues = [
        make_issue(f"A-{i}", itype="Anomalie", status="Ouvert",
                    created=_iso(now - timedelta(days=d)))
        for i, d in enumerate(ages)
    ]
    out = dt_mod.compute(issues, [], conf)["defauts_tendance"]
    assert out["age_buckets"]["labels"] == ["0-7 j", "8-30 j", "31-90 j", "+90 j"]
    assert out["age_buckets"]["anomalie"] == [1, 1, 1, 1]
