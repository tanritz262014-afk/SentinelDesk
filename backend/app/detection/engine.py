"""Runs all enabled detection rules over a list of events."""

from app.detection.base import DetectionResult, RuleConfig
from app.detection.rules import brute_force, service_installed, success_after_failures, user_created

# Rule ID -> function that implements it
RULE_FUNCTIONS = {
    "R001": brute_force.detect,
    "R002": success_after_failures.detect,
    "R003": user_created.detect,
    "R004": service_installed.detect,
}

# Extra facts about each rule, used by the API and the UI.
RULE_METADATA = {
    "R001": {"category": "Authentication", "uses_threshold": True, "uses_window": True},
    "R002": {"category": "Authentication", "uses_threshold": True, "uses_window": True},
    "R003": {"category": "Account Management", "uses_threshold": False, "uses_window": False},
    "R004": {"category": "Service Installation", "uses_threshold": False, "uses_window": False},
}


def run_detection(events: list[dict], configs: list[RuleConfig]) -> list[DetectionResult]:
    """Run every enabled rule and return all results, oldest first."""
    results: list[DetectionResult] = []
    for config in configs:
        detect = RULE_FUNCTIONS.get(config.id)
        if detect is None or not config.enabled:
            continue
        results.extend(detect(events, config))
    return sorted(results, key=lambda r: (r.first_seen, r.rule_id))
