"""Database tables, defined as Python classes (SQLAlchemy ORM).

Phase 1 creates the full schema so later phases only add logic, not tables.
All times are stored in UTC.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Allowed values, kept in one place so the API and UI use the same words.
SEVERITIES = ("Low", "Medium", "High", "Critical")
ALERT_STATUSES = ("New", "In Progress", "Closed")
# "Suspected" is the default: a rule match is NOT proof of an attack.
ALERT_VERDICTS = ("Suspected", "Confirmed", "False Positive", "Benign")
INCIDENT_STATUSES = ("New", "Investigating", "Escalated", "Resolved")
INCIDENT_PRIORITIES = ("P1", "P2", "P3", "P4")
TIMELINE_ENTRY_TYPES = ("created", "status_change", "updated", "note", "alert_linked")


def utc_now() -> datetime:
    """Current UTC time without timezone info (SQLite has no timezone type)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Link table: which security events are evidence for which alert (many-to-many).
alert_events = Table(
    "alert_events",
    Base.metadata,
    Column("alert_id", ForeignKey("alerts.id", ondelete="CASCADE"), primary_key=True),
    Column("event_id", ForeignKey("security_events.id", ondelete="CASCADE"), primary_key=True),
)


class LogUpload(Base):
    """One uploaded log file and a summary of its validation result."""

    __tablename__ = "log_uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(10))  # "json" or "csv"
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    accepted_rows: Mapped[int] = mapped_column(Integer, default=0)
    rejected_rows: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    events: Mapped[list["SecurityEvent"]] = relationship(
        back_populates="upload", cascade="all, delete-orphan"
    )


class SecurityEvent(Base):
    """One normalized log event (e.g. a Windows 4625 failed logon)."""

    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_id: Mapped[int | None] = mapped_column(
        ForeignKey("log_uploads.id", ondelete="CASCADE"), index=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    event_id: Mapped[int] = mapped_column(Integer, index=True)  # Windows Event ID
    event_category: Mapped[str] = mapped_column(String(50), default="Other")
    hostname: Mapped[str | None] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255), index=True)
    source_ip: Mapped[str | None] = mapped_column(String(45), index=True)  # 45 fits IPv6
    logon_type: Mapped[str | None] = mapped_column(String(20))
    service_name: Mapped[str | None] = mapped_column(String(255))
    service_path: Mapped[str | None] = mapped_column(String(1024))  # text only, never executed
    message: Mapped[str | None] = mapped_column(Text)
    raw_data: Mapped[str] = mapped_column(Text)  # original row stored as JSON text
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    upload: Mapped[LogUpload | None] = relationship(back_populates="events")
    alerts: Mapped[list["Alert"]] = relationship(secondary=alert_events, back_populates="events")


class DetectionRule(Base):
    """Settings for one detection rule. The rule logic itself lives in app/detection/."""

    __tablename__ = "detection_rules"

    id: Mapped[str] = mapped_column(String(10), primary_key=True)  # e.g. "R001"
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    severity: Mapped[str] = mapped_column(String(10))
    threshold: Mapped[int] = mapped_column(Integer, default=1)
    window_minutes: Mapped[int] = mapped_column(Integer, default=0)
    mitre_technique: Mapped[str | None] = mapped_column(String(50))
    limitations: Mapped[str | None] = mapped_column(Text)
    false_positives: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    alerts: Mapped[list["Alert"]] = relationship(back_populates="rule")


class Alert(Base):
    """A possible security issue raised by a detection rule."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_id: Mapped[str] = mapped_column(ForeignKey("detection_rules.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(10), index=True)
    status: Mapped[str] = mapped_column(String(20), default="New", index=True)
    verdict: Mapped[str] = mapped_column(String(20), default="Suspected")
    hostname: Mapped[str | None] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255))
    source_ip: Mapped[str | None] = mapped_column(String(45))
    first_seen: Mapped[datetime] = mapped_column(DateTime)
    last_seen: Mapped[datetime] = mapped_column(DateTime)
    event_count: Mapped[int] = mapped_column(Integer, default=1)
    evidence: Mapped[str] = mapped_column(Text, default="{}")  # JSON text
    detection_explanation: Mapped[str] = mapped_column(Text, default="")
    incident_id: Mapped[int | None] = mapped_column(
        ForeignKey("incidents.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    rule: Mapped[DetectionRule] = relationship(back_populates="alerts")
    events: Mapped[list[SecurityEvent]] = relationship(secondary=alert_events, back_populates="alerts")
    notes: Mapped[list["AlertNote"]] = relationship(
        back_populates="alert", cascade="all, delete-orphan", order_by="AlertNote.created_at"
    )
    incident: Mapped["Incident | None"] = relationship(back_populates="alerts")


class AlertNote(Base):
    """An analyst's investigation note on an alert."""

    __tablename__ = "alert_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"), index=True)
    author: Mapped[str] = mapped_column(String(100), default="analyst")
    note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    alert: Mapped[Alert] = relationship(back_populates="notes")


class Incident(Base):
    """A confirmed or escalated case that groups one or more alerts."""

    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(10))
    priority: Mapped[str] = mapped_column(String(2), default="P3")
    status: Mapped[str] = mapped_column(String(20), default="New", index=True)
    assigned_to: Mapped[str | None] = mapped_column(String(100))
    resolution_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)

    alerts: Mapped[list[Alert]] = relationship(back_populates="incident")
    timeline: Mapped[list["IncidentTimelineEntry"]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentTimelineEntry.created_at",
    )


class IncidentTimelineEntry(Base):
    """One entry in an incident's timeline (created, status change, note, ...)."""

    __tablename__ = "incident_timeline"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    entry_type: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(String(100), default="analyst")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    incident: Mapped[Incident] = relationship(back_populates="timeline")
