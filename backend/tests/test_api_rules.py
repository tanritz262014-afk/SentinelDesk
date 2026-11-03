"""API tests for detection rule settings and detection during upload."""

from pathlib import Path

from sqlalchemy import select

from app.models import Alert

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"


def upload_sample(client, filename):
    content = (SAMPLE_DIR / filename).read_bytes()
    return client.post("/api/logs/upload", files={"file": (filename, content, "application/octet-stream")})


def test_list_rules_includes_metadata(client):
    rules = client.get("/api/rules").json()
    assert [r["id"] for r in rules] == ["R001", "R002", "R003", "R004"]
    r001 = rules[0]
    assert r001["uses_threshold"] is True
    assert r001["category"] == "Authentication"
    assert r001["false_positives"]


def test_update_rule_threshold(client):
    response = client.put("/api/rules/R001", json={"threshold": 8, "window_minutes": 10})
    assert response.status_code == 200
    assert response.json()["threshold"] == 8
    assert response.json()["window_minutes"] == 10


def test_update_rule_validation(client):
    assert client.put("/api/rules/R001", json={"threshold": 0}).status_code == 422
    assert client.put("/api/rules/R001", json={"window_minutes": 5000}).status_code == 422
    assert client.put("/api/rules/R001", json={"severity": "Extreme"}).status_code == 422
    assert client.put("/api/rules/R003", json={"threshold": 3}).status_code == 422
    assert client.put("/api/rules/R999", json={"enabled": False}).status_code == 404


def test_upload_generates_suspected_alerts(client, db_session):
    body = upload_sample(client, "suspicious_events.json").json()
    assert body["alerts_generated"] == 4
    assert sorted(a["rule_id"] for a in body["alerts"]) == ["R001", "R002", "R003", "R004"]

    alerts = db_session.scalars(select(Alert)).all()
    assert all(a.verdict == "Suspected" and a.status == "New" for a in alerts)
    brute = next(a for a in alerts if a.rule_id == "R001")
    assert brute.event_count == 8
    assert len(brute.events) == 8


def test_normal_upload_generates_no_alerts(client):
    assert upload_sample(client, "normal_events.json").json()["alerts_generated"] == 0


def test_disabled_rule_is_skipped_on_upload(client):
    client.put("/api/rules/R004", json={"enabled": False})
    body = upload_sample(client, "suspicious_events.json").json()
    assert "R004" not in {a["rule_id"] for a in body["alerts"]}


def test_tuned_threshold_applies_to_next_upload(client):
    client.put("/api/rules/R001", json={"threshold": 10})
    client.put("/api/rules/R002", json={"threshold": 10})
    body = upload_sample(client, "suspicious_events.json").json()
    assert {a["rule_id"] for a in body["alerts"]} == {"R003", "R004"}
