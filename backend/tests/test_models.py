import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import Alert, AlertNote, DetectionRule, Incident, IncidentTimelineEntry, SecurityEvent, utc_now
from app.seed import DEFAULT_RULES, seed_detection_rules


def test_default_rules_are_seeded(db_session):
    ids = set(db_session.scalars(select(DetectionRule.id)))
    assert ids == {"R001", "R002", "R003", "R004"}


def test_seeding_twice_does_not_duplicate(db_session):
    assert seed_detection_rules(db_session) == 0
    assert db_session.scalar(select(func.count()).select_from(DetectionRule)) == len(DEFAULT_RULES)


def test_seeding_keeps_analyst_changes(db_session):
    rule = db_session.get(DetectionRule, "R001")
    rule.threshold = 10
    db_session.commit()
    seed_detection_rules(db_session)
    assert db_session.get(DetectionRule, "R001").threshold == 10


def _make_alert(db_session) -> Alert:
    now = utc_now()
    alert = Alert(
        rule_id="R001",
        title="Test alert",
        description="test",
        severity="High",
        first_seen=now,
        last_seen=now,
    )
    db_session.add(alert)
    db_session.commit()
    return alert


def test_new_alert_defaults_to_suspected(db_session):
    alert = _make_alert(db_session)
    assert alert.status == "New"
    assert alert.verdict == "Suspected"


def test_deleting_alert_deletes_its_notes(db_session):
    alert = _make_alert(db_session)
    db_session.add(AlertNote(alert_id=alert.id, note="checked source IP"))
    db_session.commit()

    db_session.delete(alert)
    db_session.commit()
    assert db_session.scalar(select(func.count()).select_from(AlertNote)) == 0


def test_alert_links_to_evidence_events(db_session):
    alert = _make_alert(db_session)
    event = SecurityEvent(timestamp=utc_now(), event_id=4625, raw_data="{}")
    alert.events.append(event)
    db_session.commit()
    db_session.refresh(event)
    assert event.alerts[0].id == alert.id


def test_alert_requires_existing_rule(db_session):
    now = utc_now()
    db_session.add(
        Alert(rule_id="R999", title="x", description="x", severity="Low", first_seen=now, last_seen=now)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_incident_timeline_is_saved(db_session):
    incident = Incident(title="Possible brute force", severity="High", priority="P2")
    incident.timeline.append(IncidentTimelineEntry(entry_type="created", message="Incident created"))
    db_session.add(incident)
    db_session.commit()
    assert incident.status == "New"
    assert incident.timeline[0].entry_type == "created"
