"""Constructeurs minimalistes d'issues/sprints JIRA synthétiques pour les
tests des modules indicators/*.py — pas les JSON réels de projects/*/output/
(ce sont des sorties de compute(), pas des entrées)."""

DEFAULT_CONF = {
    "sprint_field": "customfield_10020",
    "story_points_field": "customfield_10016",
    "seconds_per_day": 28800,
    "done_statuses": ["Done", "Terminé", "Terminé(e)", "Closed", "Resolved", "Fermé(e)"],
    "us_types": ["User Story", "Story"],
    "anomaly_types": [],
    "incident_types": [],
    "tech_types": [],
    "sprint_duration_days": 21,
}


def make_issue(key, itype="User Story", status="Terminé(e)", status_id=None, created=None,
                resolutiondate=None, sprints=None, sp=None,
                timeoriginalestimate=None, timespent=None,
                sprint_field="customfield_10020", story_points_field="customfield_10016",
                status_history=None, id=None):
    """`status_history` (pour cumulative_flow_diagram.py) : liste de
    (date_iso, from_status, to_status) — un changelog JIRA minimal
    (expand=changelog) — ou, pour simuler un statut renommé depuis, de
    (date_iso, from_id, from_status, to_id, to_status)."""
    fields = {
        "issuetype": {"name": itype},
        "status": {"name": status, "id": status_id},
        "created": created,
        "resolutiondate": resolutiondate,
        "timeoriginalestimate": timeoriginalestimate,
        "timespent": timespent,
    }
    if sprints is not None:
        fields[sprint_field] = [{"name": s} for s in sprints]
    if sp is not None:
        fields[story_points_field] = sp
    issue = {"key": key, "id": id or key, "fields": fields}
    if status_history is not None:
        histories = []
        for entry in status_history:
            if len(entry) == 3:
                dt, frm, to = entry
                from_id = to_id = None
            else:
                dt, from_id, frm, to_id, to = entry
            histories.append({"created": dt, "items": [
                {"field": "status", "from": from_id, "fromString": frm, "to": to_id, "toString": to}
            ]})
        issue["changelog"] = {"histories": histories}
    return issue


def make_sprint(name, state, start, end):
    return {"name": name, "state": state, "startDate": start, "endDate": end}
