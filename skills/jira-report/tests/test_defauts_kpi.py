from datetime import datetime, timezone, timedelta

import indicators.defauts_kpi as dk
from fixtures import DEFAULT_CONF, make_issue


def _conf(**overrides):
    return {**DEFAULT_CONF, **overrides}


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat()


def _window_conf(**overrides):
    """sprint_start_date = début du mois courant -> fenêtre = mois courant
    uniquement, quelle que soit la date d'exécution du test."""
    now = _now()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return _conf(anomaly_types=["Anomalie"], incident_types=["Incident"],
                 sprint_start_date=start.strftime("%Y-%m-%d"), **overrides)


def test_no_matching_issues_returns_none():
    assert dk.compute([], [], _conf())["defauts_kpi"] is None


def test_created_resolved_and_jh_within_window():
    now = _now()
    conf = _window_conf()
    issues = [
        make_issue("A-1", itype="Anomalie", status="Terminé(e)",
                    created=_iso(now), resolutiondate=_iso(now), timespent=28800),  # 1 jh
        make_issue("A-2", itype="Anomalie", status="En cours", created=_iso(now)),  # ouvert
        make_issue("I-1", itype="Incident", status="Terminé(e)",
                    created=_iso(now), resolutiondate=_iso(now), timespent=14400),  # 0.5 jh
        make_issue("US-1", itype="User Story", status="Terminé(e)",
                    resolutiondate=_iso(now), timespent=57600),  # 2 jh, entre dans le total tous types
    ]
    out = dk.compute(issues, [], conf)["defauts_kpi"]

    assert out["anomalie"]["created"] == 2
    assert out["anomalie"]["resolved"] == 1
    assert out["anomalie"]["open_now"] == 1
    assert out["anomalie"]["jh"] == 1.0
    assert out["anomalie"]["jh_per_resolved"] == 1.0

    assert out["incident"]["created"] == 1
    assert out["incident"]["resolved"] == 1
    assert out["incident"]["jh"] == 0.5

    # Dénominateur "taux de défaut" : TOUS types de tickets terminés (pas
    # seulement anomalie/incident) — 1 + 0.5 + 2 (US) = 3.5 jh.
    assert out["total_jh"] == 3.5
    assert out["anomalie"]["defect_rate_pct"] == round(100 * 1.0 / 3.5, 1)
    assert out["incident"]["defect_rate_pct"] == round(100 * 0.5 / 3.5, 1)


def test_backlog_open_over_90_days():
    conf = _window_conf()
    now = _now()
    old = now - timedelta(days=120)
    recent = now - timedelta(days=10)
    issues = [
        make_issue("A-1", itype="Anomalie", status="Ouvert", created=_iso(old)),
        make_issue("A-2", itype="Anomalie", status="Ouvert", created=_iso(recent)),
    ]
    out = dk.compute(issues, [], conf)["defauts_kpi"]
    assert out["anomalie"]["open_now"] == 2
    assert out["anomalie"]["open_over_90d"] == 1
    assert out["incident"]["open_now"] == 0


def test_backlog_ignores_date_created_before_window():
    """Le backlog ouvert n'est pas borné par la fenêtre — un ticket créé
    avant `sprint_start_date` et toujours ouvert compte quand même."""
    now = _now()
    conf = _conf(anomaly_types=["Anomalie"], sprint_start_date=now.strftime("%Y-%m-%d"))
    old = now - timedelta(days=400)
    issues = [make_issue("A-1", itype="Anomalie", status="Ouvert", created=_iso(old))]
    out = dk.compute(issues, [], conf)["defauts_kpi"]
    assert out["anomalie"]["open_now"] == 1
    assert out["anomalie"]["created"] == 0  # créé hors fenêtre
