"""R004 - New service installed (Event ID 7045, MITRE T1543.003).

Windows services start automatically, often with SYSTEM rights, so they are
a common way for attackers to stay on a machine. Every new service is raised
for review. If the service file is in a folder that normal users can write
to (Temp, AppData, Users\\Public), the severity is raised to High.

The service path is only compared as text. It is never opened or executed.
"""

from app.detection.base import DetectionResult, RuleConfig, fmt_time

SERVICE_INSTALLED = 7045
SUSPICIOUS_PATH_PARTS = ("\\temp\\", "\\appdata\\", "\\users\\public\\")


def is_suspicious_path(path: str | None) -> bool:
    if not path:
        return False
    normalized = path.lower().replace("/", "\\")
    return any(part in normalized for part in SUSPICIOUS_PATH_PARTS)


def detect(events: list[dict], config: RuleConfig) -> list[DetectionResult]:
    results = []
    for event in events:
        if event["event_id"] != SERVICE_INSTALLED:
            continue
        name = event.get("service_name") or "unknown service"
        path = event.get("service_path")
        suspicious = is_suspicious_path(path)
        host = event.get("hostname") or "unknown host"

        reason = (
            "The service file is in a user-writable folder (Temp, AppData or Users\\Public), "
            "which is unusual for legitimate software."
            if suspicious
            else "The service file path does not match the suspicious-folder list."
        )
        results.append(
            DetectionResult(
                rule_id=config.id,
                title=f"New service '{name}' installed on {host}",
                description=(
                    f"Service '{name}' was installed on {host} (Event ID 7045) with path: {path or 'not recorded'}. "
                    f"{reason}"
                ),
                severity="High" if suspicious else config.severity,
                first_seen=event["timestamp"],
                last_seen=event["timestamp"],
                event_ids=[event["id"]],
                hostname=event.get("hostname"),
                username=event.get("username"),
                source_ip=event.get("source_ip"),
                explanation=(
                    f"Event ID 7045 (service installed) was logged at {fmt_time(event['timestamp'])}. "
                    + ("Severity raised to High because of the file location." if suspicious else "")
                ).strip(),
                evidence={"service_name": name, "service_path": path, "suspicious_location": suspicious},
            )
        )
    return results
