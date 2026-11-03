"""Numbers for the SOC dashboard, computed with simple COUNT queries."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.detection.engine import RULE_METADATA
from app.models import ALERT_VERDICTS, SEVERITIES, Alert, Incident, SecurityEvent
from app.routers.alerts import to_alert_out
from app.routers.events import to_event_out
from app.schemas import CountItem, DashboardSummary

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

OPEN_INCIDENT_STATUSES = ("New", "Investigating", "Escalated")


def count(db: Session, model, *filters) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*filters)) or 0


def grouped_counts(db: Session, column) -> dict[str, int]:
    return dict(db.execute(select(column, func.count()).group_by(column)).all())


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)):
    by_severity = grouped_counts(db, Alert.severity)
    by_verdict = grouped_counts(db, Alert.verdict)

    # Alert category comes from the rule that raised it.
    by_category: dict[str, int] = {}
    for rule_id, n in grouped_counts(db, Alert.rule_id).items():
        category = RULE_METADATA.get(rule_id, {}).get("category", "Other")
        by_category[category] = by_category.get(category, 0) + n

    events_by_category = grouped_counts(db, SecurityEvent.event_category)

    recent_events = db.scalars(
        select(SecurityEvent).order_by(SecurityEvent.timestamp.desc(), SecurityEvent.id.desc()).limit(10)
    ).all()
    recent_alerts = db.scalars(select(Alert).order_by(Alert.last_seen.desc(), Alert.id.desc()).limit(5)).all()

    return DashboardSummary(
        total_alerts=count(db, Alert),
        critical_alerts=by_severity.get("Critical", 0),
        open_alerts=count(db, Alert, Alert.status != "Closed"),
        open_incidents=count(db, Incident, Incident.status.in_(OPEN_INCIDENT_STATUSES)),
        resolved_incidents=count(db, Incident, Incident.status == "Resolved"),
        total_events=count(db, SecurityEvent),
        # Always return every severity/verdict (with 0) so charts keep a stable order.
        alerts_by_severity=[CountItem(name=s, count=by_severity.get(s, 0)) for s in SEVERITIES],
        alerts_by_verdict=[CountItem(name=v, count=by_verdict.get(v, 0)) for v in ALERT_VERDICTS],
        alerts_by_category=[
            CountItem(name=k, count=v) for k, v in sorted(by_category.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        events_by_category=[
            CountItem(name=k, count=v) for k, v in sorted(events_by_category.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        recent_events=[to_event_out(e) for e in recent_events],
        recent_alerts=[to_alert_out(a) for a in recent_alerts],
    )
