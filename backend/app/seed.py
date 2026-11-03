"""Default detection rule settings.

The thresholds here are only starting values. Analysts can tune them later
from the Detection Rules page (Phase 4). Seeding is idempotent: running it
again never duplicates or overwrites rules that already exist.
"""

from sqlalchemy.orm import Session

from app.models import DetectionRule

DEFAULT_RULES = [
    {
        "id": "R001",
        "name": "Repeated failed logins",
        "description": (
            "Raises an alert when one account fails to log on (Event ID 4625) from the same "
            "source IP at least <threshold> times within <window_minutes> minutes."
        ),
        "severity": "High",
        "threshold": 5,
        "window_minutes": 5,
        "mitre_technique": "T1110 - Brute Force",
        "limitations": (
            "Misses slow attacks that stay under the threshold and password spraying "
            "(one attempt against many accounts). Depends on accurate timestamps."
        ),
        "false_positives": (
            "Users mistyping passwords, service accounts with expired credentials, "
            "many users sharing one NAT/proxy IP."
        ),
    },
    {
        "id": "R002",
        "name": "Successful logon after repeated failures",
        "description": (
            "Raises an alert when a successful logon (Event ID 4624) comes from a source IP that "
            "had at least <threshold> failed logons (4625) in the previous <window_minutes> minutes."
        ),
        "severity": "Critical",
        "threshold": 5,
        "window_minutes": 10,
        "mitre_technique": "T1110 / T1078 - Brute Force / Valid Accounts",
        "limitations": (
            "Cannot tell whether the same person made the failures and the success. "
            "The alert is still only 'Suspected' until an analyst verifies it."
        ),
        "false_positives": "A legitimate user who forgot their password and then remembered it.",
    },
    {
        "id": "R003",
        "name": "New user account created",
        "description": "Raises an alert for every user account creation (Event ID 4720).",
        "severity": "Medium",
        "threshold": 1,
        "window_minutes": 0,
        "mitre_technique": "T1136.001 - Create Account: Local Account",
        "limitations": "Does not know whether the account creation was approved (no ticketing integration).",
        "false_positives": "Normal onboarding of new employees by IT administrators.",
    },
    {
        "id": "R004",
        "name": "New service installed",
        "description": (
            "Raises an alert for every new service installation (Event ID 7045). Severity is raised "
            "to High when the service file path is in a user-writable folder such as Temp or AppData."
        ),
        "severity": "Medium",
        "threshold": 1,
        "window_minutes": 0,
        "mitre_technique": "T1543.003 - Create or Modify System Process: Windows Service",
        "limitations": (
            "Only checks the path text; it does not inspect the file. Attackers can use "
            "normal-looking paths."
        ),
        "false_positives": "Software installs, updates, drivers, and IT management agents.",
    },
]


def seed_detection_rules(db: Session) -> int:
    """Insert any missing default rules. Returns how many were added."""
    added = 0
    for rule_data in DEFAULT_RULES:
        if db.get(DetectionRule, rule_data["id"]) is None:
            db.add(DetectionRule(enabled=True, **rule_data))
            added += 1
    db.commit()
    return added
