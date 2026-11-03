"""R003 - New user account created (Event ID 4720, MITRE T1136.001).

Every account creation is raised for review because attackers often create
accounts to keep access. Most of these alerts will be normal IT work, so
the analyst checks whether the creation was approved.
"""

from app.detection.base import DetectionResult, RuleConfig, fmt_time

USER_CREATED = 4720


def detect(events: list[dict], config: RuleConfig) -> list[DetectionResult]:
    results = []
    for event in events:
        if event["event_id"] != USER_CREATED:
            continue
        new_account = event.get("username") or "unknown account"
        creator = (event.get("extra") or {}).get("subject_username")
        by_whom = f" by '{creator}'" if creator else ""
        host = event.get("hostname") or "unknown host"
        results.append(
            DetectionResult(
                rule_id=config.id,
                title=f"New user account '{new_account}' created on {host}",
                description=(
                    f"User account '{new_account}' was created{by_whom} on {host} (Event ID 4720). "
                    "Check that this account creation was approved."
                ),
                severity=config.severity,
                first_seen=event["timestamp"],
                last_seen=event["timestamp"],
                event_ids=[event["id"]],
                hostname=event.get("hostname"),
                username=event.get("username"),
                source_ip=event.get("source_ip"),
                explanation=f"Event ID 4720 (user account created) was logged at {fmt_time(event['timestamp'])}.",
                evidence={"new_account": new_account, "created_by": creator},
            )
        )
    return results
