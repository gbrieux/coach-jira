import indicators.conso_corrective as cc
from fixtures import DEFAULT_CONF, make_issue


def _conf(**overrides):
    return {**DEFAULT_CONF, **overrides}


def test_categorizes_by_configured_type_lists():
    conf = _conf(anomaly_types=["Anomalie", "Bug"], incident_types=["Incident"],
                 tech_types=["Technical Story"])
    assert cc._category("Bug", conf) == "anomalie"
    assert cc._category("Incident", conf) == "incident"
    assert cc._category("Technical Story", conf) == "us_tech"
    assert cc._category("User Story", conf) == "us"
    assert cc._category("Epic", conf) is None


def test_month_range_wraps_year():
    assert cc._month_range((2025, 11), (2026, 2)) == [
        (2025, 11), (2025, 12), (2026, 1), (2026, 2)
    ]


def test_compute_buckets_conso_by_month_and_category():
    conf = _conf(anomaly_types=["Anomalie"], incident_types=["Incident"],
                 tech_types=["Technical Story"], sprint_start_date="2026-01-01")
    issues = [
        make_issue("KEY-1", itype="Anomalie", status="Terminé(e)",
                    resolutiondate="2026-01-15T10:00:00Z", timespent=28800),  # 1 jh
        make_issue("KEY-2", itype="Incident", status="Terminé(e)",
                    resolutiondate="2026-01-20T10:00:00Z", timespent=14400),  # 0.5 jh
        make_issue("KEY-3", itype="User Story", status="Terminé(e)",
                    resolutiondate="2026-01-25T10:00:00Z", timespent=57600),  # 2 jh
        # pas terminé -> hors périmètre
        make_issue("KEY-4", itype="Anomalie", status="En cours",
                    resolutiondate=None, timespent=28800),
        # type hors des 4 catégories configurées -> exclu (pas de bucket "Autre")
        make_issue("KEY-5", itype="Epic", status="Terminé(e)",
                    resolutiondate="2026-01-10T10:00:00Z", timespent=28800),
    ]

    out = cc.compute(issues, [], conf)
    data = out["conso_corrective"]
    idx = data["categories"].index("01/01/2026")

    assert data["series"]["anomalie"][idx] == 1.0
    assert data["series"]["incident"][idx] == 0.5
    assert data["series"]["us"][idx] == 2.0
    assert data["series"]["us_tech"][idx] == 0.0
    assert data["total_jh"] == 3.5
    assert data["corrective_jh"] == 1.5
    assert data["corrective_pct"] == round(100 * 1.5 / 3.5, 1)


def test_no_matching_issues_returns_none():
    assert cc.compute([], [], _conf())["conso_corrective"] is None
