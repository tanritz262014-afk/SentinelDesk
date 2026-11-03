"""R002 - Successful logon after repeated failures (MITRE T1110 / T1078).

Logic: for every successful logon (4624) that has a source IP, count the
failed logons (4625) from the SAME IP during the previous `window_minutes`.
If that count reaches `threshold`, raise an alert.

Only the first success after a run of failures alerts, so one attack does
not create many duplicate alerts. The alert is still only "Suspected":
the analyst must confirm whether the right person logged in.
"""

from datetime import timedelta

from app.detection.base import DetectionResult, RuleConfig, fmt_time, sort_by_time

SUCCESS_LOGON = 4624
FAILED_LOGON = 4625


def detect(events: list[dict], config: RuleConfig) -> list[DetectionResult]:
    window = timedelta(minutes=config.window_minutes)
    ordered = sort_by_time([e for e in events if e["event_id"] in (SUCCESS_LOGON, FAILED_LOGON) and e.get("source_ip")])

    results = []
    used_failure_ids: set[int] = set()
    for success in ordered:
        if success["event_id"] != SUCCESS_LOGON:
            continue
        start = success["timestamp"] - window
        failures = [
            e for e in ordered
            if e["event_id"] == FAILED_LOGON
            and e["source_ip"] == success["source_ip"]
            and start <= e["timestamp"] < success["timestamp"]
            and e["id"] not in used_failure_ids
        ]
        if len(failures) < config.threshold:
            continue

        used_failure_ids.update(e["id"] for e in failures)
        failed_accounts = sorted({e.get("username") or "unknown" for e in failures})
        who = success.get("username") or "unknown user"
        ip = success["source_ip"]
        results.append(
            DetectionResult(
                rule_id=config.id,
                title=f"Successful logon for {who} after {len(failures)} failures from {ip}",
                description=(
                    f"Account '{who}' logged on successfully (Event ID 4624) from {ip} shortly after "
                    f"{len(failures)} failed logons from the same IP. The password may have been guessed. "
                    "Verify with the account owner before treating this as confirmed."
                ),
                severity=config.severity,
                first_seen=failures[0]["timestamp"],
                last_seen=success["timestamp"],
                event_ids=[e["id"] for e in failures] + [success["id"]],
                hostname=success.get("hostname"),
                username=success.get("username"),
                source_ip=ip,
                explanation=(
                    f"Successful logon at {fmt_time(success['timestamp'])} followed {len(failures)} failed logons "
                    f"from {ip} since {fmt_time(failures[0]['timestamp'])}. The rule threshold is "
                    f"{config.threshold} failures within the previous {config.window_minutes} minutes."
                ),
                evidence={
                    "failed_logons_before_success": len(failures),
                    "accounts_targeted": failed_accounts,
                    "successful_account": who,
                    "logon_type": success.get("logon_type"),
                    "threshold": config.threshold,
                    "window_minutes": config.window_minutes,
                },
            )
        )
    return results
