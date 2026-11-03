"""Incident management: create from alerts, track status, timeline, export reports."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Alert, AlertNote, Incident, IncidentTimelineEntry, utc_now
from app.routers.alerts import to_alert_out
from app.schemas import (
    IncidentCreate,
    IncidentDetailOut,
    IncidentListOut,
    IncidentOut,
    IncidentStatusLiteral,
    IncidentUpdate,
    LinkAlerts,
    NoteCreate,
    PriorityLiteral,
    SeverityLiteral,
    TimelineEntryOut,
)
from app.services.report_service import build_report, render_markdown

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

# Which status changes are allowed. Resolved incidents can be reopened.
ALLOWED_TRANSITIONS = {
    "New": {"Investigating", "Escalated", "Resolved"},
    "Investigating": {"Escalated", "Resolved"},
    "Escalated": {"Investigating", "Resolved"},
    "Resolved": {"Investigating"},
}


def get_incident_or_404(db: Session, incident_id: int) -> Incident:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


def add_timeline(incident: Incident, entry_type: str, message: str, author: str) -> None:
    incident.timeline.append(IncidentTimelineEntry(entry_type=entry_type, message=message, author=author))


def to_incident_out(incident: Incident) -> IncidentOut:
    return IncidentOut(
        id=incident.id,
        title=incident.title,
        severity=incident.severity,
        priority=incident.priority,
        status=incident.status,
        assigned_to=incident.assigned_to,
        alert_count=len(incident.alerts),
        created_at=incident.created_at,
        updated_at=incident.updated_at,
        resolved_at=incident.resolved_at,
    )


def to_incident_detail(incident: Incident) -> IncidentDetailOut:
    alerts = sorted(incident.alerts, key=lambda a: (a.first_seen, a.id))
    return IncidentDetailOut(
        **to_incident_out(incident).model_dump(),
        description=incident.description,
        resolution_summary=incident.resolution_summary,
        alerts=[to_alert_out(a) for a in alerts],
        timeline=[TimelineEntryOut.model_validate(t) for t in incident.timeline],
    )


def find_linkable_alerts(db: Session, alert_ids: list[int], incident_id: int | None) -> list[Alert]:
    """Check the alert IDs before changing anything. Each alert can belong to only one incident."""
    unique_ids = list(dict.fromkeys(alert_ids))
    alerts = db.scalars(select(Alert).where(Alert.id.in_(unique_ids)).order_by(Alert.id)).all()
    found = {a.id for a in alerts}
    missing = [i for i in unique_ids if i not in found]
    if missing:
        raise HTTPException(status_code=404, detail=f"Alert(s) not found: {', '.join(map(str, missing))}")
    taken = [a.id for a in alerts if a.incident_id is not None and a.incident_id != incident_id]
    if taken:
        raise HTTPException(
            status_code=409, detail=f"Alert(s) already linked to another incident: {', '.join(map(str, taken))}"
        )
    return alerts


def link_alerts(db: Session, incident: Incident, alerts: list[Alert], author: str) -> None:
    for alert in alerts:
        if alert.incident_id == incident.id:
            continue
        alert.incident = incident
        add_timeline(incident, "alert_linked", f"Alert #{alert.id} linked: {alert.title}", author)
        db.add(AlertNote(alert_id=alert.id, author=author, note=f"Linked to incident: {incident.title}"))


@router.post("", response_model=IncidentDetailOut, status_code=201)
def create_incident(payload: IncidentCreate, db: Session = Depends(get_db)):
    author = payload.author.strip()
    alerts = find_linkable_alerts(db, payload.alert_ids, None)  # fail before saving anything
    incident = Incident(
        title=payload.title.strip(),
        description=payload.description.strip(),
        severity=payload.severity,
        priority=payload.priority,
        assigned_to=(payload.assigned_to or "").strip() or None,
        status="New",
    )
    db.add(incident)
    add_timeline(incident, "created", f"Incident created with severity {incident.severity} and priority {incident.priority}.", author)
    db.flush()  # gives the incident an ID before linking alerts
    link_alerts(db, incident, alerts, author)
    db.commit()
    db.refresh(incident)
    return to_incident_detail(incident)


@router.get("", response_model=IncidentListOut)
def list_incidents(
    status: IncidentStatusLiteral | None = None,
    severity: SeverityLiteral | None = None,
    priority: PriorityLiteral | None = None,
    q: str | None = Query(None, max_length=100, description="Search title, description and assignee"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    filters = []
    if status:
        filters.append(Incident.status == status)
    if severity:
        filters.append(Incident.severity == severity)
    if priority:
        filters.append(Incident.priority == priority)
    if q:
        filters.append(
            or_(
                Incident.title.contains(q, autoescape=True),
                Incident.description.contains(q, autoescape=True),
                Incident.assigned_to.contains(q, autoescape=True),
            )
        )
    total = db.scalar(select(func.count()).select_from(Incident).where(*filters))
    incidents = db.scalars(
        select(Incident).where(*filters).order_by(Incident.updated_at.desc(), Incident.id.desc()).limit(limit).offset(offset)
    ).all()
    return IncidentListOut(total=total, limit=limit, offset=offset, items=[to_incident_out(i) for i in incidents])


@router.get("/{incident_id}", response_model=IncidentDetailOut)
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    return to_incident_detail(get_incident_or_404(db, incident_id))


@router.patch("/{incident_id}", response_model=IncidentDetailOut)
def update_incident(incident_id: int, payload: IncidentUpdate, db: Session = Depends(get_db)):
    """Update status and details. Every change is written to the timeline."""
    incident = get_incident_or_404(db, incident_id)
    author = payload.author.strip()
    changed = False

    if payload.status is not None and payload.status != incident.status:
        if payload.status not in ALLOWED_TRANSITIONS[incident.status]:
            raise HTTPException(
                status_code=422, detail=f"Cannot change status from {incident.status} to {payload.status}."
            )
        if payload.status == "Resolved":
            summary = (payload.resolution_summary or incident.resolution_summary or "").strip()
            if len(summary) < 10:
                raise HTTPException(
                    status_code=422, detail="A resolution summary (at least 10 characters) is required to resolve an incident."
                )
            incident.resolved_at = utc_now()
        if incident.status == "Resolved":
            incident.resolved_at = None  # reopened
        add_timeline(incident, "status_change", f"Status changed from {incident.status} to {payload.status}.", author)
        incident.status = payload.status
        changed = True

    for field_name, label in (("severity", "Severity"), ("priority", "Priority")):
        new_value = getattr(payload, field_name)
        if new_value is not None and new_value != getattr(incident, field_name):
            add_timeline(incident, "updated", f"{label} changed from {getattr(incident, field_name)} to {new_value}.", author)
            setattr(incident, field_name, new_value)
            changed = True

    if payload.assigned_to is not None:
        new_owner = payload.assigned_to.strip() or None
        if new_owner != incident.assigned_to:
            add_timeline(incident, "updated", f"Assigned to {new_owner or 'nobody'}.", author)
            incident.assigned_to = new_owner
            changed = True

    if payload.resolution_summary is not None:
        summary = payload.resolution_summary.strip() or None
        if summary != incident.resolution_summary:
            add_timeline(incident, "updated", "Resolution summary updated.", author)
            incident.resolution_summary = summary
            changed = True

    if not changed:
        raise HTTPException(status_code=422, detail="Nothing to update")

    db.commit()
    db.refresh(incident)
    return to_incident_detail(incident)


@router.post("/{incident_id}/notes", response_model=IncidentDetailOut, status_code=201)
def add_incident_note(incident_id: int, payload: NoteCreate, db: Session = Depends(get_db)):
    incident = get_incident_or_404(db, incident_id)
    text = payload.note.strip()
    if not text:
        raise HTTPException(status_code=422, detail="The note cannot be empty")
    add_timeline(incident, "note", text, payload.author.strip())
    db.commit()
    db.refresh(incident)
    return to_incident_detail(incident)


@router.post("/{incident_id}/alerts", response_model=IncidentDetailOut)
def add_alerts_to_incident(incident_id: int, payload: LinkAlerts, db: Session = Depends(get_db)):
    incident = get_incident_or_404(db, incident_id)
    alerts = find_linkable_alerts(db, payload.alert_ids, incident.id)
    link_alerts(db, incident, alerts, payload.author.strip())
    db.commit()
    db.refresh(incident)
    return to_incident_detail(incident)


@router.get("/{incident_id}/report")
def export_report(
    incident_id: int,
    format: str = Query("markdown", pattern="^(markdown|json)$"),
    db: Session = Depends(get_db),
):
    """Download the incident report as Markdown or JSON."""
    report = build_report(get_incident_or_404(db, incident_id))
    if format == "json":
        content = json.dumps(report, indent=2, ensure_ascii=False)
        media_type, extension = "application/json", "json"
    else:
        content = render_markdown(report)
        media_type, extension = "text/markdown; charset=utf-8", "md"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="incident-{incident_id}-report.{extension}"'},
    )
