"""Load the synthetic sample logs so the dashboard has data to show.

Run from the backend folder:
    python -m app.demo_data            # add the sample data to the database
    python -m app.demo_data --reset    # delete ALL data first, then load samples

All sample data is synthetic (fictional users, documentation IP ranges).
"""

import argparse
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.models import Alert, Incident, IncidentTimelineEntry
from app.seed import seed_detection_rules
from app.services.ingest_service import store_upload
from app.services.log_parser import parse_log_file

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"
DEMO_FILES = ("suspicious_events.json", "normal_events.json", "mixed_events.csv")


def load_demo(db: Session, with_incident: bool = True) -> dict:
    settings = get_settings()
    summary = {"events": 0, "alerts": 0, "incidents": 0}
    alerts_by_rule: dict[str, Alert] = {}

    for name in DEMO_FILES:
        content = (SAMPLE_DIR / name).read_bytes()
        result = parse_log_file(name, content, settings.max_upload_bytes, settings.max_events_per_file)
        upload, alerts = store_upload(db, name, len(content), result)
        summary["events"] += upload.accepted_rows
        summary["alerts"] += len(alerts)
        for alert in alerts:
            alerts_by_rule.setdefault(alert.rule_id, alert)
        print(f"  loaded {name}: {upload.accepted_rows} events, {len(alerts)} alerts")

    brute_force, success = alerts_by_rule.get("R001"), alerts_by_rule.get("R002")
    if with_incident and brute_force and success:
        incident = Incident(
            title="Possible brute force against admin.backup on SRV-FILE-01",
            description="Demo incident: repeated failed logons from 203.0.113.45 followed by a successful logon.",
            severity="Critical",
            priority="P1",
            status="Investigating",
            assigned_to="l1.analyst",
        )
        incident.timeline = [
            IncidentTimelineEntry(entry_type="created", message="Incident created from alerts R001 and R002.", author="demo"),
            IncidentTimelineEntry(entry_type="status_change", message="Status changed from New to Investigating.", author="demo"),
        ]
        brute_force.incident = incident
        success.incident = incident
        brute_force.status = success.status = "In Progress"
        db.add(incident)
        db.commit()
        summary["incidents"] = 1
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Load SentinelDesk demo data.")
    parser.add_argument("--reset", action="store_true", help="delete all existing data first")
    parser.add_argument("--no-incident", action="store_true", help="do not create the demo incident")
    args = parser.parse_args()

    if args.reset:
        print(f"Resetting database: {get_settings().database_url}")
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        seed_detection_rules(db)
        summary = load_demo(db, with_incident=not args.no_incident)
    print(f"Done: {summary['events']} events, {summary['alerts']} alerts, {summary['incidents']} incident(s).")


if __name__ == "__main__":
    main()
