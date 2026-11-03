"""Shared building blocks for detection rules.

Rules work on plain Python dictionaries (one per event) and return
DetectionResult objects. They never touch the database or the web layer,
which keeps them small and easy to unit-test.

Each event dictionary has these keys:
    id, timestamp (datetime), event_id (int), hostname, username,
    source_ip, service_name, service_path, extra (dict of raw fields)
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RuleConfig:
    """Tunable settings for one rule (loaded from the detection_rules table)."""

    id: str
    enabled: bool = True
    severity: str = "Medium"
    threshold: int = 1
    window_minutes: int = 0


@dataclass
class DetectionResult:
    """One alert produced by a rule, before it is saved to the database."""

    rule_id: str
    title: str
    description: str
    severity: str
    first_seen: datetime
    last_seen: datetime
    event_ids: list[int]
    explanation: str
    hostname: str | None = None
    username: str | None = None
    source_ip: str | None = None
    evidence: dict = field(default_factory=dict)


def fmt_time(value: datetime) -> str:
    """Format a timestamp for alert text, e.g. 2026-10-01 09:15:02 UTC."""
    return value.strftime("%Y-%m-%d %H:%M:%S UTC")


def sort_by_time(events: list[dict]) -> list[dict]:
    return sorted(events, key=lambda e: (e["timestamp"], e.get("id") or 0))
