"""Alert investigation: list, view, add notes, change status and verdict."""

import json
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.detection.engine import RULE_METADATA
from app.models import Alert, AlertNote, SecurityEvent
from app.routers.events import to_event_detail, to_event_out
from app.schemas import (
    AlertDetailOut,
    AlertListOut,
    AlertNoteOut,
    AlertOut,
    AlertStatusLiteral,
    AlertUpdate,
    EventOut,
    NoteCreate,
    SeverityLiteral,
    VerdictLiteral,
)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

RELATED_WINDOW = timedelta(minutes=60)
MIN_CONFIRM_NOTE_LENGTH = 10


def get_alert_or_404(db: Session, alert_id: int) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


def to_alert_out(alert: Alert) -> AlertOut:
    return AlertOut(
        id=alert.id,
        rule_id=alert.rule_id,
        rule_name=alert.rule.name,
        category=RULE_METADATA.get(alert.rule_id, {}).get("category", "Other"),
        title=alert.title,
        severity=alert.severity,
        status=alert.status,
        verdict=alert.verdict,
        hostname=alert.hostname,
        username=alert.username,
        source_ip=alert.source_ip,
        first_seen=alert.first_seen,
        last_seen=alert.last_seen,
        event_count=alert.event_count,
        incident_id=alert.incident_id,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
    )


def to_alert_detail(alert: Alert) -> AlertDetailOut:
    events = sorted(alert.events, key=lambda e: (e.timestamp, e.id))
    return AlertDetailOut(
        **to_alert_out(alert).model_dump(),
        description=alert.description,
        detection_explanation=alert.detection_explanation,
        evidence=json.loads(alert.evidence or "{}"),
        mitre_technique=alert.rule.mitre_technique,
        rule_limitations=alert.rule.limitations,
        rule_false_positives=alert.rule.false_positives,
        events=[to_event_detail(e) for e in events],
        notes=[AlertNoteOut.model_validate(n) for n in alert.notes],
        incident_title=alert.incident.title if alert.incident else None,
    )


@router.get("", response_model=AlertListOut)
def list_alerts(
    severity: SeverityLiteral | None = None,
    status: AlertStatusLiteral | None = None,
    verdict: VerdictLiteral | None = None,
    rule_id: str | None = Query(None, max_length=10),
    in_incident: bool | None = Query(None, description="true = linked to an incident, false = not linked"),
    q: str | None = Query(None, max_length=100, description="Search title, host, user and IP"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List alerts, most recent activity first."""
    filters = []
    if severity:
        filters.append(Alert.severity == severity)
    if status:
        filters.append(Alert.status == status)
    if verdict:
        filters.append(Alert.verdict == verdict)
    if rule_id:
        filters.append(Alert.rule_id == rule_id)
    if in_incident is True:
        filters.append(Alert.incident_id.is_not(None))
    if in_incident is False:
        filters.append(Alert.incident_id.is_(None))
    if q:
        filters.append(
            or_(
                Alert.title.contains(q, autoescape=True),
                Alert.hostname.contains(q, autoescape=True),
                Alert.username.contains(q, autoescape=True),
                Alert.source_ip.contains(q, autoescape=True),
            )
        )

    total = db.scalar(select(func.count()).select_from(Alert).where(*filters))
    alerts = db.scalars(
        select(Alert).where(*filters).order_by(Alert.last_seen.desc(), Alert.id.desc()).limit(limit).offset(offset)
    ).all()
    return AlertListOut(total=total, limit=limit, offset=offset, items=[to_alert_out(a) for a in alerts])


@router.get("/{alert_id}", response_model=AlertDetailOut)
def get_alert(alert_id: int, db: Session = Depends(get_db)):
    """Full alert details: explanation, evidence events (with raw data) and notes."""
    return to_alert_detail(get_alert_or_404(db, alert_id))


@router.get("/{alert_id}/related", response_model=list[EventOut])
def get_related_events(alert_id: int, db: Session = Depends(get_db)):
    """Other events with the same IP, user or host within 60 minutes of the alert."""
    alert = get_alert_or_404(db, alert_id)

    matches = []
    if alert.source_ip:
        matches.append(SecurityEvent.source_ip == alert.source_ip)
    if alert.username:
        matches.append(SecurityEvent.username == alert.username)
    if alert.hostname:
        matches.append(SecurityEvent.hostname == alert.hostname)
    if not matches:
        return []

    evidence_ids = [e.id for e in alert.events]
    events = db.scalars(
        select(SecurityEvent)
        .where(
            or_(*matches),
            SecurityEvent.timestamp >= alert.first_seen - RELATED_WINDOW,
            SecurityEvent.timestamp <= alert.last_seen + RELATED_WINDOW,
            SecurityEvent.id.not_in(evidence_ids),
        )
        .order_by(SecurityEvent.timestamp, SecurityEvent.id)
        .limit(50)
    ).all()
    return [to_event_out(e) for e in events]


@router.post("/{alert_id}/notes", response_model=AlertNoteOut, status_code=201)
def add_note(alert_id: int, payload: NoteCreate, db: Session = Depends(get_db)):
    alert = get_alert_or_404(db, alert_id)
    text = payload.note.strip()
    if not text:
        raise HTTPException(status_code=422, detail="The note cannot be empty")
    note = AlertNote(alert_id=alert.id, author=payload.author.strip(), note=text)
    db.add(note)
    db.commit()
    return note


@router.patch("/{alert_id}", response_model=AlertDetailOut)
def update_alert(alert_id: int, payload: AlertUpdate, db: Session = Depends(get_db)):
    """Change status and/or verdict.

    Marking an alert "Confirmed" requires a justification note, so nothing is
    labelled a confirmed attack without the analyst recording the evidence.
    """
    alert = get_alert_or_404(db, alert_id)
    author = payload.author.strip()
    note_text = (payload.note or "").strip()

    status_changes = payload.status is not None and payload.status != alert.status
    verdict_changes = payload.verdict is not None and payload.verdict != alert.verdict
    if not status_changes and not verdict_changes and not note_text:
        raise HTTPException(status_code=422, detail="Nothing to update")

    if verdict_changes and payload.verdict == "Confirmed" and len(note_text) < MIN_CONFIRM_NOTE_LENGTH:
        raise HTTPException(
            status_code=422,
            detail="A justification note (at least 10 characters) is required to mark an alert as Confirmed.",
        )

    if status_changes:
        db.add(AlertNote(alert_id=alert.id, author=author, note=f"Status changed from {alert.status} to {payload.status}."))
        alert.status = payload.status
    if verdict_changes:
        db.add(AlertNote(alert_id=alert.id, author=author, note=f"Verdict changed from {alert.verdict} to {payload.verdict}."))
        alert.verdict = payload.verdict
    if note_text:
        db.add(AlertNote(alert_id=alert.id, author=author, note=note_text))

    db.commit()
    db.refresh(alert)
    return to_alert_detail(alert)
