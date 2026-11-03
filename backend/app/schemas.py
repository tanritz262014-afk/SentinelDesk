"""Pydantic models describing API responses and request bodies.

FastAPI uses these to validate data and to generate the /docs page.
More schemas are added in later phases.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    database: str
    rules_loaded: int
    server_time: datetime


# ----- Log uploads (Phase 2) -----

class RowErrorOut(BaseModel):
    row: int
    message: str


class AlertBrief(BaseModel):
    id: int
    rule_id: str
    title: str
    severity: str


class UploadResult(BaseModel):
    upload_id: int
    filename: str
    file_type: str
    total_rows: int
    accepted_rows: int
    rejected_rows: int
    errors: list[RowErrorOut]
    errors_truncated: bool
    alerts_generated: int = 0
    alerts: list[AlertBrief] = []


class LogUploadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    file_type: str
    file_size_bytes: int
    total_rows: int
    accepted_rows: int
    rejected_rows: int
    uploaded_at: datetime


# ----- Security events (Phase 2) -----

class EventOut(BaseModel):
    id: int
    upload_id: int | None
    timestamp: datetime
    event_id: int
    event_category: str
    event_description: str
    hostname: str | None
    username: str | None
    source_ip: str | None
    logon_type: str | None
    service_name: str | None
    service_path: str | None
    message: str | None


class EventDetailOut(EventOut):
    raw_data: dict


class EventListOut(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[EventOut]


# ----- Detection rules (Phase 3) -----

SeverityLiteral = Literal["Low", "Medium", "High", "Critical"]


class RuleOut(BaseModel):
    id: str
    name: str
    description: str
    enabled: bool
    severity: str
    threshold: int
    window_minutes: int
    mitre_technique: str | None
    limitations: str | None
    false_positives: str | None
    category: str
    uses_threshold: bool
    uses_window: bool
    updated_at: datetime


class RuleUpdate(BaseModel):
    enabled: bool | None = None
    severity: SeverityLiteral | None = None
    threshold: int | None = Field(None, ge=1, le=1000)
    window_minutes: int | None = Field(None, ge=1, le=1440)


# ----- Alerts (Phase 5) -----

AlertStatusLiteral = Literal["New", "In Progress", "Closed"]
VerdictLiteral = Literal["Suspected", "Confirmed", "False Positive", "Benign"]


class AlertNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author: str
    note: str
    created_at: datetime


class AlertOut(BaseModel):
    id: int
    rule_id: str
    rule_name: str
    category: str
    title: str
    severity: str
    status: str
    verdict: str
    hostname: str | None
    username: str | None
    source_ip: str | None
    first_seen: datetime
    last_seen: datetime
    event_count: int
    incident_id: int | None
    created_at: datetime
    updated_at: datetime


class AlertListOut(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AlertOut]


class AlertDetailOut(AlertOut):
    description: str
    detection_explanation: str
    evidence: dict
    mitre_technique: str | None
    rule_limitations: str | None
    rule_false_positives: str | None
    events: list[EventDetailOut]
    notes: list[AlertNoteOut]
    incident_title: str | None


class NoteCreate(BaseModel):
    note: str = Field(..., min_length=1, max_length=2000)
    author: str = Field("analyst", min_length=1, max_length=100)


class AlertUpdate(BaseModel):
    status: AlertStatusLiteral | None = None
    verdict: VerdictLiteral | None = None
    note: str | None = Field(None, max_length=2000)
    author: str = Field("analyst", min_length=1, max_length=100)


# ----- Incidents (Phase 6) -----

IncidentStatusLiteral = Literal["New", "Investigating", "Escalated", "Resolved"]
PriorityLiteral = Literal["P1", "P2", "P3", "P4"]


class TimelineEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_type: str
    message: str
    author: str
    created_at: datetime


class IncidentOut(BaseModel):
    id: int
    title: str
    severity: str
    priority: str
    status: str
    assigned_to: str | None
    alert_count: int
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class IncidentListOut(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[IncidentOut]


class IncidentDetailOut(IncidentOut):
    description: str
    resolution_summary: str | None
    alerts: list[AlertOut]
    timeline: list[TimelineEntryOut]


class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field("", max_length=5000)
    severity: SeverityLiteral
    priority: PriorityLiteral = "P3"
    assigned_to: str | None = Field(None, max_length=100)
    alert_ids: list[int] = Field(default_factory=list, max_length=100)
    author: str = Field("analyst", min_length=1, max_length=100)


class IncidentUpdate(BaseModel):
    status: IncidentStatusLiteral | None = None
    severity: SeverityLiteral | None = None
    priority: PriorityLiteral | None = None
    assigned_to: str | None = Field(None, max_length=100)
    resolution_summary: str | None = Field(None, max_length=5000)
    author: str = Field("analyst", min_length=1, max_length=100)


class LinkAlerts(BaseModel):
    alert_ids: list[int] = Field(..., min_length=1, max_length=100)
    author: str = Field("analyst", min_length=1, max_length=100)


# ----- Dashboard (Phase 7) -----

class CountItem(BaseModel):
    name: str
    count: int


class DashboardSummary(BaseModel):
    total_alerts: int
    critical_alerts: int
    open_alerts: int
    open_incidents: int
    resolved_incidents: int
    total_events: int
    alerts_by_severity: list[CountItem]
    alerts_by_category: list[CountItem]
    alerts_by_verdict: list[CountItem]
    events_by_category: list[CountItem]
    recent_events: list[EventOut]
    recent_alerts: list[AlertOut]
