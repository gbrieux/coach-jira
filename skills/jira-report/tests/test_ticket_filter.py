import indicators.conso_corrective as conso_corrective
import indicators.status_flow as status_flow
import indicators.tempo_types as tempo_types
import indicators.types as types_
import indicators.velocity as velocity
from indicators.common import filter_issues, ticket_types
from fixtures import DEFAULT_CONF, make_issue, make_sprint


def _conf(**ticket_filter):
    return {**DEFAULT_CONF, "ticket_filter": ticket_filter}


def test_ticket_types_default_absent_and_empty():
    # clé absente -> filtre historique passé en `default`
    assert ticket_types(DEFAULT_CONF, "velocity", ["User Story"]) == {"User Story"}
    # clé absente sans défaut -> tous les tickets
    assert ticket_types(DEFAULT_CONF, "types") is None
    # liste vide -> tous les tickets, même si l'indicateur filtre sur us_types par défaut
    assert ticket_types(_conf(velocity=[]), "velocity", ["User Story"]) is None
    # clé définie -> remplace le défaut
    assert ticket_types(_conf(velocity=["Bug"]), "velocity", ["User Story"]) == {"Bug"}
    # ticket_filter absent du conf (projet sans DEFAULTS) -> pas de KeyError
    conf = {k: v for k, v in DEFAULT_CONF.items() if k != "ticket_filter"}
    assert ticket_types(conf, "types") is None


def test_filter_issues():
    issues = [make_issue("A-1", itype="User Story"), make_issue("A-2", itype="Bug")]
    assert [it["key"] for it in filter_issues(issues, _conf(types=["Bug"]), "types")] == ["A-2"]
    assert len(filter_issues(issues, DEFAULT_CONF, "types")) == 2


def test_velocity_ticket_filter_overrides_us_types():
    sprints = [make_sprint("Sprint 1", "closed", "2026-01-01T00:00:00Z", "2026-01-14T23:59:59Z")]
    issues = [
        make_issue("K-1", itype="User Story", sprints=["Sprint 1"]),
        make_issue("K-2", itype="Technical Story", sprints=["Sprint 1"]),
    ]
    default = velocity.compute(issues, sprints, DEFAULT_CONF)["velocity"][0]
    assert default["done"] == 1  # us_types seul
    widened = velocity.compute(
        issues, sprints, _conf(velocity=["User Story", "Technical Story"]))["velocity"][0]
    assert widened["done"] == 2
    # la clé d'un autre indicateur n'a pas d'effet
    other = velocity.compute(issues, sprints, _conf(burnup=["Technical Story"]))["velocity"][0]
    assert other["done"] == 1


def test_status_ticket_filter():
    issues = [make_issue("K-1", itype="User Story", status="En cours"),
              make_issue("K-2", itype="Bug", status="En cours")]
    assert status_flow.compute(issues, [], DEFAULT_CONF)["status_counts_us"] == {"En cours": 1}
    assert status_flow.compute(issues, [], _conf(status=[]))["status_counts_us"] == {"En cours": 2}


def test_types_ticket_filter():
    issues = [make_issue("K-1", itype="User Story"), make_issue("K-2", itype="Bug")]
    assert types_.compute(issues, [], DEFAULT_CONF)["type_counts"] == {"User Story": 1, "Bug": 1}
    assert types_.compute(issues, [], _conf(types=["Bug"]))["type_counts"] == {"Bug": 1}


def test_conso_corrective_filter_restricts_input_only():
    conf = {**_conf(conso_corrective=["Bug", "User Story"]), "anomaly_types": ["Bug", "Anomalie"],
            "sprint_start_date": "2026-01-01"}
    issues = [
        make_issue("K-1", itype="Bug", resolutiondate="2026-01-10T00:00:00Z", timespent=28800),
        make_issue("K-2", itype="Anomalie", resolutiondate="2026-01-10T00:00:00Z", timespent=28800),
        make_issue("K-3", itype="User Story", resolutiondate="2026-01-10T00:00:00Z", timespent=28800),
    ]
    out = conso_corrective.compute(issues, [], conf)["conso_corrective"]
    # "Anomalie" hors filtre -> exclu ; "Bug" reste classé anomalie via anomaly_types
    assert out["totals_jh"]["anomalie"] == 1.0
    assert out["totals_jh"]["us"] == 1.0


def test_tempo_types_filter_drops_worklogs_of_excluded_issues():
    issues = [make_issue("K-1", itype="User Story", id="1"), make_issue("K-2", itype="Bug", id="2")]
    worklogs = [
        {"issue_id": "1", "date": "2026-01-05", "seconds": 28800},
        {"issue_id": "2", "date": "2026-01-05", "seconds": 28800},
        {"issue_id": "99", "date": "2026-01-05", "seconds": 28800},  # ticket hors JQL
    ]
    base = {**DEFAULT_CONF, "tempo_worklogs": worklogs, "sprint_start_date": "2026-01-01"}
    out = tempo_types.compute(issues, [], base)["tempo_types"]
    assert set(out["totals_jh"]) == {"User Story", "Bug", "Inconnu"}
    out = tempo_types.compute(issues, [], {**base, "ticket_filter": {"tempo_types": ["Bug"]}})["tempo_types"]
    assert out["totals_jh"] == {"Bug": 1.0}
