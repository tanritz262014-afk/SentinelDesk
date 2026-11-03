"""API tests for incident management and report export."""

from pathlib import Path

import pytest

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"


@pytest.fixture()
def alerts(client):
    content = (SAMPLE_DIR / "suspicious_events.json").read_bytes()
    body = client.post("/api/logs/upload", files={"file": ("s.json", content, "application/json")}).json()
    return {a["rule_id"]: a["id"] for a in body["alerts"]}


def create(client, alert_ids, **overrides):
    payload = {
        "title": "Possible brute force on SRV-FILE-01",
        "description": "Failed logons followed by a success from an external IP.",
        "severity": "High",
        "priority": "P2",
        "assigned_to": "l1.analyst",
        "alert_ids": alert_ids,
        **overrides,
    }
    return client.post("/api/incidents", json=payload)


def test_create_incident_links_alerts_and_writes_timeline(client, alerts):
    response = create(client, [alerts["R001"], alerts["R002"]])
    assert response.status_code == 201
    incident = response.json()
    assert incident["status"] == "New"
    assert incident["alert_count"] == 2
    types = [t["entry_type"] for t in incident["timeline"]]
    assert types == ["created", "alert_linked", "alert_linked"]

    alert = client.get(f"/api/alerts/{alerts['R001']}").json()
    assert alert["incident_id"] == incident["id"]
    assert alert["notes"][-1]["note"].startswith("Linked to incident")


def test_create_incident_without_alerts(client):
    response = create(client, [])
    assert response.status_code == 201
    assert response.json()["alert_count"] == 0


def test_create_validation(client, alerts):
    assert create(client, [], title="x").status_code == 422
    assert create(client, [], severity="Extreme").status_code == 422
    assert create(client, [], priority="P9").status_code == 422
    assert create(client, [99999]).status_code == 404


def test_alert_cannot_be_in_two_incidents(client, alerts):
    create(client, [alerts["R001"]])
    response = create(client, [alerts["R001"]])
    assert response.status_code == 409
    # Nothing from the failed request was saved.
    assert client.get("/api/incidents").json()["total"] == 1


def test_status_workflow(client, alerts):
    incident_id = create(client, [alerts["R002"]]).json()["id"]
    url = f"/api/incidents/{incident_id}"

    assert client.patch(url, json={"status": "Investigating"}).json()["status"] == "Investigating"
    assert client.patch(url, json={"status": "Escalated"}).json()["status"] == "Escalated"

    no_summary = client.patch(url, json={"status": "Resolved"})
    assert no_summary.status_code == 422
    assert "resolution summary" in no_summary.json()["detail"]

    resolved = client.patch(
        url, json={"status": "Resolved", "resolution_summary": "Password reset, IP blocked at the firewall."}
    ).json()
    assert resolved["status"] == "Resolved"
    assert resolved["resolved_at"] is not None

    reopened = client.patch(url, json={"status": "Investigating"}).json()
    assert reopened["resolved_at"] is None

    messages = [t["message"] for t in reopened["timeline"] if t["entry_type"] == "status_change"]
    assert messages == [
        "Status changed from New to Investigating.",
        "Status changed from Investigating to Escalated.",
        "Status changed from Escalated to Resolved.",
        "Status changed from Resolved to Investigating.",
    ]


def test_invalid_transition_rejected(client, alerts):
    incident_id = create(client, [alerts["R003"]]).json()["id"]
    url = f"/api/incidents/{incident_id}"
    client.patch(url, json={"status": "Investigating"})
    response = client.patch(url, json={"status": "New"})
    assert response.status_code == 422
    assert "Cannot change status" in response.json()["detail"]


def test_field_updates_are_logged(client, alerts):
    incident_id = create(client, [alerts["R003"]]).json()["id"]
    detail = client.patch(
        f"/api/incidents/{incident_id}", json={"priority": "P1", "severity": "Critical", "assigned_to": "l2.responder"}
    ).json()
    assert detail["priority"] == "P1"
    messages = [t["message"] for t in detail["timeline"]]
    assert "Priority changed from P2 to P1." in messages
    assert "Severity changed from High to Critical." in messages
    assert "Assigned to l2.responder." in messages
    assert client.patch(f"/api/incidents/{incident_id}", json={}).status_code == 422


def test_notes_and_linking_more_alerts(client, alerts):
    incident_id = create(client, [alerts["R001"]]).json()["id"]
    detail = client.post(f"/api/incidents/{incident_id}/notes", json={"note": "Contacted the server owner."}).json()
    assert detail["timeline"][-1]["entry_type"] == "note"

    detail = client.post(f"/api/incidents/{incident_id}/alerts", json={"alert_ids": [alerts["R003"], alerts["R004"]]}).json()
    assert detail["alert_count"] == 3


def test_list_and_filter_incidents(client, alerts):
    create(client, [alerts["R001"]], priority="P1")
    create(client, [alerts["R003"]], title="New account created", priority="P3")
    assert client.get("/api/incidents").json()["total"] == 2
    assert client.get("/api/incidents", params={"priority": "P1"}).json()["total"] == 1
    assert client.get("/api/incidents", params={"q": "account"}).json()["total"] == 1
    assert client.get("/api/incidents", params={"status": "Done"}).status_code == 422


def test_markdown_report(client, alerts):
    incident_id = create(client, [alerts["R001"], alerts["R002"]]).json()["id"]
    response = client.get(f"/api/incidents/{incident_id}/report")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert f'filename="incident-{incident_id}-report.md"' in response.headers["content-disposition"]
    text = response.text
    assert text.startswith(f"# Incident Report #{incident_id}")
    assert "## Linked alerts" in text
    # Nothing was confirmed, so the report must not claim a confirmed attack.
    assert "remains suspected" in text


def test_report_reflects_confirmed_alert(client, alerts):
    client.patch(
        f"/api/alerts/{alerts['R002']}",
        json={"verdict": "Confirmed", "note": "User confirmed they did not log in."},
    )
    incident_id = create(client, [alerts["R002"]]).json()["id"]
    report = client.get(f"/api/incidents/{incident_id}/report", params={"format": "json"}).json()
    assert report["verdict_summary"] == {"Confirmed": 1}
    assert "1 of 1 linked alert(s) were confirmed" in report["assessment"]
    assert report["alerts"][0]["notes"]


def test_report_escapes_html_from_logs(client):
    incident_id = create(client, [], title="<img src=x onerror=alert(1)>").json()["id"]
    text = client.get(f"/api/incidents/{incident_id}/report").text
    assert "<img" not in text
    assert "&lt;img src=x onerror=alert(1)&gt;" in text


def test_report_format_validation_and_404(client):
    incident_id = create(client, []).json()["id"]
    assert client.get(f"/api/incidents/{incident_id}/report", params={"format": "pdf"}).status_code == 422
    assert client.get("/api/incidents/999").status_code == 404
    assert client.get("/api/incidents/999/report").status_code == 404
