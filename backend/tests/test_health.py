from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.main import app


def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert body["rules_loaded"] == 4


def test_root_points_to_docs(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "/docs" in response.json()["message"]


def test_health_reports_503_when_database_fails(client):
    class BrokenSession:
        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("database is locked"))

    app.dependency_overrides[get_db] = lambda: BrokenSession()
    response = client.get("/api/health")
    assert response.status_code == 503
    # The internal error text must not be sent to the client.
    assert "locked" not in response.text
    assert response.json()["detail"] == "Database unavailable"


def test_cors_allows_frontend_origin(client):
    response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_blocks_unknown_origin(client):
    response = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in response.headers
