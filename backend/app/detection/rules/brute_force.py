"""R001 - Repeated failed logins (possible brute force, MITRE T1110).

Logic:
1. Take only failed logons (Event ID 4625).
2. Group them by (username, source_ip).
3. Walk through each group in time order with a sliding window. When
   `threshold` failures fall inside `window_minutes`, a burst starts.
4. The burst keeps growing while the next failure arrives within
   `window_minutes` of the previous one. Each burst becomes one alert.

Limitations: slow attacks that stay under the threshold and password
spraying (one try against many accounts) are not detected by this rule.
"""

from collections import defaultdict
from datetime import timedelta

from app.detection.base import DetectionResult, RuleConfig, fmt_time, sort_by_time

FAILED_LOGON = 4625


def find_bursts(failures: list[dict], threshold: int, window: timedelta) -> list[list[dict]]:
    """Return lists of failures that reach the threshold inside the window."""
    bursts = []
    i = 0
    while i < len(failures):
        # Find the first index where `threshold` failures fit inside the window.
        end = i + threshold - 1
        if end >= len(failures):
            break
        if failures[end]["timestamp"] - failures[i]["timestamp"] <= window:
            burst = failures[i:end + 1]
            j = end + 1
            # Extend the burst while failures keep coming quickly.
            while j < len(failures) and failures[j]["timestamp"] - failures[j - 1]["timestamp"] <= window:
                burst.append(failures[j])
                j += 1
            bursts.append(burst)
            i = j
        else:
            i += 1
    return bursts


def detect(events: list[dict], config: RuleConfig) -> list[DetectionResult]:
    window = timedelta(minutes=config.window_minutes)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for event in events:
        if event["event_id"] == FAILED_LOGON:
            groups[(event.get("username"), event.get("source_ip"))].append(event)

    results = []
    for (username, source_ip), failures in groups.items():
        for burst in find_bursts(sort_by_time(failures), config.threshold, window):
            first, last = burst[0]["timestamp"], burst[-1]["timestamp"]
            hosts = sorted({e["hostname"] for e in burst if e.get("hostname")})
            who = username or "unknown user"
            where = source_ip or "unknown source"
            results.append(
                DetectionResult(
                    rule_id=config.id,
                    title=f"Repeated failed logins for {who} from {where}",
                    description=(
                        f"{len(burst)} failed logons (Event ID 4625) for account '{who}' from {where}. "
                        "This pattern can indicate password guessing (brute force)."
                    ),
                    severity=config.severity,
                    first_seen=first,
                    last_seen=last,
                    event_ids=[e["id"] for e in burst],
                    hostname=hosts[0] if len(hosts) == 1 else None,
                    username=username,
                    source_ip=source_ip,
                    explanation=(
                        f"{len(burst)} failed logons between {fmt_time(first)} and {fmt_time(last)}. "
                        f"The rule threshold is {config.threshold} failures within {config.window_minutes} minutes "
                        "for the same account and source IP."
                    ),
                    evidence={
                        "failed_logons": len(burst),
                        "target_hosts": hosts,
                        "threshold": config.threshold,
                        "window_minutes": config.window_minutes,
                    },
                )
            )
    return results
