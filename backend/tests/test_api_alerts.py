"""API tests for alert investigation."""

from pathlib import Path

import pytest

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"


def upload_sample(client, filename):
    content = (SAMPLE_DIR / filename).read_bytes()
    return client.post("/api/logs/upload", files={"file": (filename, content, "application/octet-stream")}).json()


@pytest.fixture()
def alerts(client):
    """Upload the suspicious sample and return {rule_id: alert_id}."""
    body = upload_sample(client, "suspicious_events.json")
    return {a["rule_id"]: a["id"] for a in body["alerts"]}


def test_list_alerts(client, alerts):
    body = client.get("/api/alerts").json()
    assert body["total"] == 4
    # Most recent activity first: the service install (09:31) is newest.
    assert body["items"][0]["rule_id"] == "R004"
    assert body["items"][0]["category"] == "Service Installation"
    assert all(a["verdict"] == "Suspected" for a in body["items"])


@pytest.mark.parametrize(
    "params, expected",
    [
        ({"severity": "Critical"}, {"R002"}),
        ({"severity": "High"}, {"R001", "R004"}),
        ({"rule_id": "R003"}, {"R003"}),
        ({"q": "svc_support2"}, {"R003"}),
        ({"q": "203.0.113.45"}, {"R001", "R002"}),
        ({"status": "Closed"}, set()),
        ({"in_incident": "false"}, {"R001", "R002", "R003", "R004"}),
    ],
)
def test_filter_alerts(client, alerts, params, expected):
    items = client.get("/api/alerts", params=params).json()["items"]
    assert {a["rule_id"] for a in items} == expected


def test_invalid_filter_values_rejected(client):
    assert client.get("/api/alerts", params={"severity": "Extreme"}).status_code == 422
    assert client.get("/api/alerts", params={"verdict": "Hacked"}).status_code == 422


def test_alert_detail_has_evidence_and_rule_context(client, alerts):
    detail = client.get(f"/api/alerts/{alerts['R001']}").json()
    assert detail["event_count"] == 8
    assert len(detail["events"]) == 8
    assert detail["events"][0]["raw_data"]["event_id"] == 4625
    assert "threshold is 5 failures within 5 minutes" in detail["detection_explanation"]
    assert detail["evidence"]["failed_logons"] == 8
    assert detail["mitre_technique"].startswith("T1110")
    assert detail["rule_false_positives"]
    assert detail["notes"] == []


def test_related_events_exclude_evidence(client, alerts):
    related = client.get(f"/api/alerts/{alerts['R001']}/related").json()
    detail = client.get(f"/api/alerts/{alerts['R001']}").json()
    evidence_ids = {e["id"] for e in detail["events"]}
    assert related, "expected related events on the same host/user/IP"
    assert not evidence_ids & {e["id"] for e in related}
    # The successful logon from the same IP is related context.
    assert any(e["event_id"] == 4624 and e["source_ip"] == "203.0.113.45" for e in related)


def test_add_note(client, alerts):
    response = client.post(f"/api/alerts/{alerts['R003']}/notes", json={"note": "Checked ticket system: no request found.", "author": "l1.analyst"})
    assert response.status_code == 201
    notes = client.get(f"/api/alerts/{alerts['R003']}").json()["notes"]
    assert notes[0]["author"] == "l1.analyst"


def test_empty_note_rejected(client, alerts):
    assert client.post(f"/api/alerts/{alerts['R003']}/notes", json={"note": ""}).status_code == 422
    assert client.post(f"/api/alerts/{alerts['R003']}/notes", json={"note": "   "}).status_code == 422


def test_status_change_records_system_note(client, alerts):
    detail = client.patch(f"/api/alerts/{alerts['R004']}", json={"status": "In Progress"}).json()
    assert detail["status"] == "In Progress"
    assert detail["notes"][-1]["note"] == "Status changed from New to In Progress."


def test_confirmed_requires_justification(client, alerts):
    url = f"/api/alerts/{alerts['R002']}"
    response = client.patch(url, json={"verdict": "Confirmed"})
    assert response.status_code == 422
    assert "justification" in response.json()["detail"]
    assert client.patch(url, json={"verdict": "Confirmed", "note": "short"}).status_code == 422
    # Still Suspected after the rejected attempts.
    assert client.get(url).json()["verdict"] == "Suspected"


def test_confirmed_with_justification(client, alerts):
    justification = "Account owner confirmed they did not log in; source IP is not a company address."
    detail = client.patch(
        f"/api/alerts/{alerts['R002']}",
        json={"verdict": "Confirmed", "status": "In Progress", "note": justification},
    ).json()
    assert detail["verdict"] == "Confirmed"
    notes = [n["note"] for n in detail["notes"]]
    assert "Verdict changed from Suspected to Confirmed." in notes
    assert justification in notes


def test_false_positive_does_not_need_note(client, alerts):
    detail = client.patch(f"/api/alerts/{alerts['R003']}", json={"verdict": "False Positive", "status": "Closed"}).json()
    assert detail["verdict"] == "False Positive"
    assert detail["status"] == "Closed"


def test_update_validation(client, alerts):
    url = f"/api/alerts/{alerts['R001']}"
    assert client.patch(url, json={}).status_code == 422
    assert client.patch(url, json={"status": "Done"}).status_code == 422
    assert client.patch(url, json={"verdict": "Hacked"}).status_code == 422


def test_missing_alert_returns_404(client):
    assert client.get("/api/alerts/999").status_code == 404
    assert client.get("/api/alerts/999/related").status_code == 404
    assert client.patch("/api/alerts/999", json={"status": "Closed"}).status_code == 404
    assert client.post("/api/alerts/999/notes", json={"note": "x"}).status_code == 404
