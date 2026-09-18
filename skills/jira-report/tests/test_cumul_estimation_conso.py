import indicators.cumul_estimation_conso as cec
from fixtures import DEFAULT_CONF, make_issue


def _conf(**overrides):
    return {**DEFAULT_CONF, **overrides}


def test_cumulates_estimate_and_conso_by_creation_date_excluding_epics():
    issues = [
        make_issue("KEY-1", itype="User Story", created="2026-01-01T10:00:00Z",
                   timeoriginalestimate=28800, timespent=14400),  # 1 jh estimé, 0.5 jh conso
        make_issue("KEY-2", itype="Anomalie", created="2026-01-02T10:00:00Z",
                   timeoriginalestimate=14400, timespent=14400),  # 0.5 jh estimé, 0.5 jh conso
        # Epic : exclu des courbes estimé/consommé, alimente sa propre courbe
        make_issue("KEY-3", itype="Epic", created="2026-01-01T09:00:00Z",
                   timeoriginalestimate=86400, timespent=57600),  # 3 jh estimé Epic
    ]
    out = cec.compute(issues, [], _conf())
    data = out["cumul_estimation_conso"]

    idx1 = data["categories"].index("01/01/2026")
    idx2 = data["categories"].index("02/01/2026")

    assert data["estime_jh"][idx1] == 1.0
    assert data["consomme_jh"][idx1] == 0.5
    assert data["estime_epics_jh"][idx1] == 3.0

    assert data["estime_jh"][idx2] == 1.5
    assert data["consomme_jh"][idx2] == 1.0
    assert data["estime_epics_jh"][idx2] == 3.0  # cumulé, pas de nouvel Epic ce jour-là

    assert data["total_estime_jh"] == 1.5
    assert data["total_consomme_jh"] == 1.0
    assert data["total_estime_epics_jh"] == 3.0
    assert data["ecart_conso_estime_jh"] == 0.5
    assert data["ecart_epics_detail_jh"] == 1.5


def test_missing_estimate_or_conso_counts_as_zero():
    issues = [
        make_issue("KEY-1", itype="User Story", created="2026-01-01T10:00:00Z",
                   timeoriginalestimate=None, timespent=None),
    ]
    data = cec.compute(issues, [], _conf())["cumul_estimation_conso"]
    assert data["estime_jh"][0] == 0.0
    assert data["consomme_jh"][0] == 0.0


def test_issue_without_created_date_is_ignored():
    issues = [
        make_issue("KEY-1", itype="User Story", created=None, timeoriginalestimate=28800),
    ]
    assert cec.compute(issues, [], _conf())["cumul_estimation_conso"] is None


def test_no_issues_returns_none():
    assert cec.compute([], [], _conf())["cumul_estimation_conso"] is None
