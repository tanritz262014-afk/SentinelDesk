"""Database connection setup (SQLAlchemy + SQLite).

SQLAlchemy builds parameterized SQL for every query, so user input is never
pasted directly into SQL strings. This protects against SQL injection.
"""

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Parent class for all ORM models (tables)."""


def _ensure_sqlite_folder(database_url: str) -> None:
    """Create the folder for the SQLite file if it does not exist yet."""
    prefix = "sqlite:///"
    if database_url.startswith(prefix) and ":memory:" not in database_url:
        Path(database_url[len(prefix):]).parent.mkdir(parents=True, exist_ok=True)


def build_engine(database_url: str) -> Engine:
    _ensure_sqlite_folder(database_url)
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    """SQLite ignores foreign keys unless this is switched on for every connection."""
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


engine = build_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    """FastAPI dependency: open a session for one request, then always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
