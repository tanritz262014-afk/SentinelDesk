"""Endpoints to browse stored security events."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.detection.event_catalog import get_description
from app.models import SecurityEvent
from app.schemas import EventDetailOut, EventListOut, EventOut

router = APIRouter(prefix="/api/events", tags=["events"])


def to_event_out(event: SecurityEvent) -> EventOut:
    return EventOut(
        id=event.id,
        upload_id=event.upload_id,
        timestamp=event.timestamp,
        event_id=event.event_id,
        event_category=event.event_category,
        event_description=get_description(event.event_id),
        hostname=event.hostname,
        username=event.username,
        source_ip=event.source_ip,
        logon_type=event.logon_type,
        service_name=event.service_name,
        service_path=event.service_path,
        message=event.message,
    )


def to_event_detail(event: SecurityEvent) -> EventDetailOut:
    return EventDetailOut(**to_event_out(event).model_dump(), raw_data=json.loads(event.raw_data))


@router.get("", response_model=EventListOut)
def list_events(
    event_id: int | None = Query(None, description="Windows Event ID, e.g. 4625"),
    category: str | None = Query(None, max_length=50),
    username: str | None = Query(None, max_length=255),
    hostname: str | None = Query(None, max_length=255),
    source_ip: str | None = Query(None, max_length=45),
    upload_id: int | None = None,
    q: str | None = Query(None, max_length=100, description="Text search in user, host, IP and message"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List events, newest first, with optional filters.

    Every filter value is passed to the database as a bound parameter,
    never pasted into the SQL text.
    """
    filters = []
    if event_id is not None:
        filters.append(SecurityEvent.event_id == event_id)
    if category:
        filters.append(SecurityEvent.event_category == category)
    if username:
        filters.append(SecurityEvent.username == username)
    if hostname:
        filters.append(SecurityEvent.hostname == hostname)
    if source_ip:
        filters.append(SecurityEvent.source_ip == source_ip)
    if upload_id is not None:
        filters.append(SecurityEvent.upload_id == upload_id)
    if q:
        # autoescape=True makes % and _ in the search text match literally.
        filters.append(
            or_(
                SecurityEvent.username.contains(q, autoescape=True),
                SecurityEvent.hostname.contains(q, autoescape=True),
                SecurityEvent.source_ip.contains(q, autoescape=True),
                SecurityEvent.message.contains(q, autoescape=True),
            )
        )

    total = db.scalar(select(func.count()).select_from(SecurityEvent).where(*filters))
    events = db.scalars(
        select(SecurityEvent)
        .where(*filters)
        .order_by(SecurityEvent.timestamp.desc(), SecurityEvent.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return EventListOut(total=total, limit=limit, offset=offset, items=[to_event_out(e) for e in events])


@router.get("/{event_pk}", response_model=EventDetailOut)
def get_event(event_pk: int, db: Session = Depends(get_db)):
    """Get one event, including the original raw row."""
    event = db.get(SecurityEvent, event_pk)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return to_event_detail(event)
