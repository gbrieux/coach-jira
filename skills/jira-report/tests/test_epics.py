"""fetch_jira.build_epics — {{liste_epics}}, aligné sur cumul_estimation_conso."""
import tempfile
from pathlib import Path

import workspace

# fetch_jira résout le répertoire de données à l'import : le neutraliser le
# temps de l'import (les tests ne dépendent jamais de .data-dir-path/.env).
_orig_data_root = workspace.data_root
workspace.data_root = lambda: Path(tempfile.gettempdir())
try:
    import fetch_jira
finally:
    workspace.data_root = _orig_data_root

import indicators.cumul_estimation_conso as cumul_estimation_conso
from fixtures import DEFAULT_CONF, make_issue

D = 28800  # 1 jh


def _issues():
    return [
        make_issue("E-1", itype="Epic", status="En cours", created="2025-02-17T09:00:00+00:00",
                   timeoriginalestimate=10 * D),
        make_issue("E-2", itype="Epic", status="À faire", created="2025-05-01T09:00:00+00:00"),
        make_issue("US-1", created="2025-02-18T09:00:00+00:00", parent=("E-1", "Epic 1"),
                   timeoriginalestimate=4 * D, timespent=6 * D),
        make_issue("US-2", status="En cours", created="2025-02-18T09:00:00+00:00", parent=("E-1", "Epic 1"),
                   timeoriginalestimate=3 * D, timespent=1 * D),
        make_issue("ST-1", itype="Sous-tâche", created="2025-02-19T09:00:00+00:00", parent=("US-1", "US 1"),
                   timespent=2 * D),
        make_issue("US-3", created="2025-05-02T09:00:00+00:00", parent=("E-2", "Epic 2"),
                   timeoriginalestimate=5 * D, timespent=5 * D),
        make_issue("US-4", status="À faire", created="2025-06-01T09:00:00+00:00",
                   timeoriginalestimate=2 * D, timespent=3 * D),
    ]


def test_estimate_is_epic_own_estimate():
    ep = fetch_jira.build_epics(_issues(), DEFAULT_CONF)
    by_key = {e["key"]: e for e in ep["items"]}
    assert by_key["E-1"]["estimate_jh"] == 10.0
    assert by_key["E-1"]["detail_estimate_jh"] == 7.0
    assert by_key["E-2"]["estimate_jh"] == 0.0
    assert by_key["E-2"]["raf_theo_jh"] == -5.0
    assert ep["total_estimate_jh"] == 10.0


def test_subtask_rolls_up_to_epic_of_its_parent():
    ep = fetch_jira.build_epics(_issues(), DEFAULT_CONF)
    by_key = {e["key"]: e for e in ep["items"]}
    assert by_key["E-1"]["conso_jh"] == 9.0  # 6 + 1 + 2 (sous-tâche via US-1)


def test_no_epic_row_and_totals_match_cumul_indicator():
    issues = _issues()
    ep = fetch_jira.build_epics(issues, DEFAULT_CONF)
    assert ep["no_epic"]["conso_jh"] == 3.0
    assert ep["no_epic"]["ticket_count"] == 1
    assert ep["no_epic"]["estimate_jh"] == 0.0

    cec = cumul_estimation_conso.compute(issues, [], DEFAULT_CONF)["cumul_estimation_conso"]
    assert ep["total_conso_jh"] == cec["total_consomme_jh"] == 17.0
    assert ep["total_estimate_jh"] == cec["total_estime_epics_jh"]
    rows = ep["items"] + [ep["no_epic"]]
    assert round(sum(e["conso_jh"] for e in rows), 1) == ep["total_conso_jh"]


def test_avancement_and_projection_cover_all_us():
    ep = fetch_jira.build_epics(_issues(), DEFAULT_CONF)
    # US-1, US-3 terminées ; US-2, US-4 non (US-4 sans EPIC)
    assert (ep["us_done_total"], ep["us_total"]) == (2, 4)
    assert ep["avancement_pct"] == 50.0
    assert ep["projection_theorique_jh"] == 34.0  # 17 / 0,5
    assert ep["previsibilite_pct"] == 240.0       # (34 − 10) / 10


def test_no_epic_absent_when_all_attached():
    issues = [it for it in _issues() if it["key"] != "US-4"]
    assert fetch_jira.build_epics(issues, DEFAULT_CONF)["no_epic"] is None
