"""Connects the detection engine to the database.

1. Load rule settings from the detection_rules table.
2. Turn stored events into plain dictionaries for the rules.
3. Run the engine and save each result as an Alert linked to its evidence.
"""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.base import RuleConfig
from app.detection.engine import run_detection
from app.models import Alert, DetectionRule, SecurityEvent


def load_rule_configs(db: Session) -> list[RuleConfig]:
    rules = db.scalars(select(DetectionRule).order_by(DetectionRule.id)).all()
    return [
        RuleConfig(
            id=r.id,
            enabled=r.enabled,
            severity=r.severity,
            threshold=r.threshold,
            window_minutes=r.window_minutes,
        )
        for r in rules
    ]


def event_to_dict(event: SecurityEvent) -> dict:
    return {
        "id": event.id,
        "timestamp": event.timestamp,
        "event_id": event.event_id,
        "hostname": event.hostname,
        "username": event.username,
        "source_ip": event.source_ip,
        "logon_type": event.logon_type,
        "service_name": event.service_name,
        "service_path": event.service_path,
        "extra": json.loads(event.raw_data or "{}"),
    }


def detect_and_save(db: Session, events: list[SecurityEvent]) -> list[Alert]:
    """Run all enabled rules on the given events and store the alerts."""
    if not events:
        return []
    events_by_id = {e.id: e for e in events}
    results = run_detection([event_to_dict(e) for e in events], load_rule_configs(db))

    alerts = []
    for result in results:
        alert = Alert(
            rule_id=result.rule_id,
            title=result.title[:255],
            description=result.description,
            severity=result.severity,
            status="New",
            verdict="Suspected",  # a rule match is never treated as a confirmed attack
            hostname=result.hostname,
            username=result.username,
            source_ip=result.source_ip,
            first_seen=result.first_seen,
            last_seen=result.last_seen,
            event_count=len(result.event_ids),
            evidence=json.dumps(result.evidence, default=str),
            detection_explanation=result.explanation,
        )
        alert.events = [events_by_id[i] for i in result.event_ids if i in events_by_id]
        db.add(alert)
        alerts.append(alert)
    db.commit()
    return alerts
