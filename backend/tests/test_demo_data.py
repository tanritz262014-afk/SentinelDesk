from sqlalchemy import func, select

from app.demo_data import load_demo
from app.models import Alert, Incident, SecurityEvent


def test_load_demo_creates_events_alerts_and_incident(db_session):
    summary = load_demo(db_session)
    assert summary == {"events": 36, "alerts": 6, "incidents": 1}
    assert db_session.scalar(select(func.count()).select_from(SecurityEvent)) == 36
    incident = db_session.scalars(select(Incident)).one()
    assert len(incident.alerts) == 2
    # Demo data never marks anything as confirmed.
    assert {a.verdict for a in db_session.scalars(select(Alert))} == {"Suspected"}
