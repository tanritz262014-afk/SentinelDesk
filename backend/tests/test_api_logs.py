"""API tests for log upload and event browsing."""

import json
from pathlib import Path

from sqlalchemy import func, select

from app.models import LogUpload, SecurityEvent

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"


def upload(client, filename: str, content: bytes):
    return client.post("/api/logs/upload", files={"file": (filename, content, "application/octet-stream")})


def upload_sample(client, filename: str):
    return upload(client, filename, (SAMPLE_DIR / filename).read_bytes())


def test_upload_json_stores_events(client, db_session):
    response = upload_sample(client, "suspicious_events.json")
    assert response.status_code == 201
    body = response.json()
    assert body["file_type"] == "json"
    assert body["accepted_rows"] == 12
    assert body["rejected_rows"] == 0
    assert db_session.scalar(select(func.count()).select_from(SecurityEvent)) == 12
    assert db_session.get(LogUpload, body["upload_id"]).filename == "suspicious_events.json"


def test_upload_csv(client):
    response = upload_sample(client, "mixed_events.csv")
    assert response.status_code == 201
    assert response.json()["accepted_rows"] == 11


def test_partial_upload_reports_row_errors(client):
    response = upload_sample(client, "invalid_events.json")
    assert response.status_code == 201
    body = response.json()
    assert body["accepted_rows"] == 2
    assert body["rejected_rows"] == 6
    assert {"row": 2, "message": "timestamp is required"} in body["errors"]
    assert body["errors_truncated"] is False


def test_file_with_no_valid_rows_is_rejected_and_nothing_saved(client, db_session):
    response = upload(client, "bad.json", json.dumps([{"event_id": 4625}]).encode())
    assert response.status_code == 422
    assert response.json()["errors"][0]["message"] == "timestamp is required"
    assert db_session.scalar(select(func.count()).select_from(LogUpload)) == 0


def test_wrong_file_type_is_rejected(client):
    response = upload(client, "payload.exe", b"MZ")
    assert response.status_code == 415
    assert "Only .json and .csv" in response.json()["detail"]


def test_oversized_file_is_rejected(client):
    too_big = b"[" + b" " * (2 * 1024 * 1024) + b"]"
    response = upload(client, "big.json", too_big)
    assert response.status_code == 413


def test_missing_file_field_returns_422(client):
    response = client.post("/api/logs/upload")
    assert response.status_code == 422


def test_path_traversal_filename_is_sanitized(client, db_session):
    response = upload(client, "../../secret.json", (SAMPLE_DIR / "normal_events.json").read_bytes())
    assert response.status_code == 201
    assert response.json()["filename"] == "secret.json"


def test_list_uploads_newest_first(client):
    upload_sample(client, "normal_events.json")
    upload_sample(client, "mixed_events.csv")
    uploads = client.get("/api/logs/uploads").json()
    assert [u["filename"] for u in uploads] == ["mixed_events.csv", "normal_events.json"]


# ----- /api/events -----

def test_list_events_newest_first_with_description(client):
    upload_sample(client, "suspicious_events.json")
    body = client.get("/api/events").json()
    assert body["total"] == 12
    first = body["items"][0]
    assert first["event_id"] == 7045
    assert first["event_description"] == "A new service was installed in the system"


def test_filter_events(client):
    upload_sample(client, "suspicious_events.json")
    upload_sample(client, "normal_events.json")
    body = client.get("/api/events", params={"event_id": 4625, "source_ip": "203.0.113.45"}).json()
    assert body["total"] == 8
    assert all(e["username"] == "admin.backup" for e in body["items"])

    by_category = client.get("/api/events", params={"category": "Account Management"}).json()
    assert by_category["total"] == 1


def test_text_search(client):
    upload_sample(client, "suspicious_events.json")
    assert client.get("/api/events", params={"q": "SRV-FILE"}).json()["total"] == 11


def test_pagination(client):
    upload_sample(client, "normal_events.json")
    page = client.get("/api/events", params={"limit": 5, "offset": 10}).json()
    assert page["total"] == 13
    assert len(page["items"]) == 3


def test_sql_injection_attempt_is_treated_as_plain_text(client):
    upload_sample(client, "normal_events.json")
    attack = "' OR '1'='1' --"
    assert client.get("/api/events", params={"username": attack}).json()["total"] == 0
    assert client.get("/api/events", params={"q": attack}).json()["total"] == 0
    # Wildcard characters are matched literally, not as "match anything".
    assert client.get("/api/events", params={"q": "%"}).json()["total"] == 0


def test_invalid_query_parameters_are_rejected(client):
    assert client.get("/api/events", params={"limit": 0}).status_code == 422
    assert client.get("/api/events", params={"limit": 501}).status_code == 422
    assert client.get("/api/events", params={"event_id": "abc"}).status_code == 422


def test_get_single_event_includes_raw_data(client):
    upload_sample(client, "suspicious_events.json")
    event_pk = client.get("/api/events", params={"event_id": 4720}).json()["items"][0]["id"]
    detail = client.get(f"/api/events/{event_pk}").json()
    # Extra fields that SentinelDesk does not model are still kept in raw_data.
    assert detail["raw_data"]["subject_username"] == "admin.backup"


def test_get_missing_event_returns_404(client):
    assert client.get("/api/events/99999").status_code == 404
