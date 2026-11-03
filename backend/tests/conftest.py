"""Shared test setup.

Each test gets a fresh, empty SQLite database in a temporary folder, so tests
never touch your real data/sentineldesk.db file.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.database import Base, build_engine, get_db
from app.main import app
from app.seed import seed_detection_rules


@pytest.fixture()
def db_session(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()
    seed_detection_rules(session)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    """API test client that uses the temporary test database."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    # Not using "with TestClient(...)" on purpose: that would run the startup
    # code against the real database file instead of the test database.
    yield TestClient(app)
    app.dependency_overrides.clear()
