"""API tests for the dashboard summary."""

from pathlib import Path

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"


def upload_sample(client, filename):
    content = (SAMPLE_DIR / filename).read_bytes()
    return client.post("/api/logs/upload", files={"file": (filename, content, "application/octet-stream")}).json()


def as_dict(items):
    return {i["name"]: i["count"] for i in items}


def test_empty_database_returns_zeros(client):
    body = client.get("/api/dashboard/summary").json()
    assert body["total_alerts"] == 0
    assert body["open_incidents"] == 0
    assert as_dict(body["alerts_by_severity"]) == {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
    assert body["alerts_by_category"] == []
    assert body["recent_events"] == []


def test_counts_after_uploads(client):
    upload_sample(client, "suspicious_events.json")
    upload_sample(client, "normal_events.json")
    upload_sample(client, "mixed_events.csv")
    body = client.get("/api/dashboard/summary").json()

    assert body["total_events"] == 36
    assert body["total_alerts"] == 6
    assert body["critical_alerts"] == 1
    assert as_dict(body["alerts_by_severity"]) == {"Low": 0, "Medium": 2, "High": 3, "Critical": 1}
    assert as_dict(body["alerts_by_category"]) == {"Authentication": 3, "Account Management": 1, "Service Installation": 2}
    assert as_dict(body["alerts_by_verdict"])["Suspected"] == 6
    assert as_dict(body["events_by_category"])["Authentication Failure"] == 18  # 8 + 3 + 7
    assert len(body["recent_events"]) == 10
    assert len(body["recent_alerts"]) == 5


def test_incident_counts(client):
    alerts = upload_sample(client, "suspicious_events.json")["alerts"]
    first = client.post("/api/incidents", json={"title": "Case one", "severity": "High", "alert_ids": [alerts[0]["id"]]}).json()
    client.post("/api/incidents", json={"title": "Case two", "severity": "Low"})
    client.patch(f"/api/incidents/{first['id']}", json={"status": "Resolved", "resolution_summary": "Handled and documented."})

    body = client.get("/api/dashboard/summary").json()
    assert body["open_incidents"] == 1
    assert body["resolved_incidents"] == 1
