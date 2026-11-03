"""Unit tests for the detection rules (pure Python, no database).

Each rule is tested with:
- suspicious data that MUST raise an alert
- normal data that must NOT raise an alert
- edge cases around the threshold and the time window
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.detection.base import RuleConfig
from app.detection.engine import run_detection
from app.detection.rules import brute_force, service_installed, success_after_failures, user_created
from app.seed import DEFAULT_RULES
from app.services.log_parser import parse_log_file

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"
BASE_TIME = datetime(2026, 10, 1, 9, 0, 0)

R001 = RuleConfig("R001", severity="High", threshold=5, window_minutes=5)
R002 = RuleConfig("R002", severity="Critical", threshold=5, window_minutes=10)
R003 = RuleConfig("R003", severity="Medium")
R004 = RuleConfig("R004", severity="Medium")


def default_configs() -> list[RuleConfig]:
    return [
        RuleConfig(r["id"], True, r["severity"], r["threshold"], r["window_minutes"])
        for r in DEFAULT_RULES
    ]


def make_event(event_pk, seconds, event_id, username="j.doe", ip="203.0.113.45", **extra):
    return {
        "id": event_pk,
        "timestamp": BASE_TIME + timedelta(seconds=seconds),
        "event_id": event_id,
        "hostname": extra.pop("hostname", "SRV-01"),
        "username": username,
        "source_ip": ip,
        "logon_type": "3",
        "service_name": extra.pop("service_name", None),
        "service_path": extra.pop("service_path", None),
        "extra": extra,
    }


def failures(count, every_seconds=10, start_pk=1, start_seconds=0, **kwargs):
    return [make_event(start_pk + i, start_seconds + i * every_seconds, 4625, **kwargs) for i in range(count)]


def load_sample(filename: str) -> list[dict]:
    """Parse a sample file and give each event a fake primary key."""
    result = parse_log_file(filename, (SAMPLE_DIR / filename).read_bytes(), 2 * 1024 * 1024, 10000)
    events = []
    for pk, event in enumerate(result.events, start=1):
        events.append({**event, "id": pk, "extra": json.loads(event["raw_data"])})
    return events


# ---------------- R001 Repeated failed logins ----------------

def test_r001_alerts_at_exact_threshold():
    results = brute_force.detect(failures(5), R001)
    assert len(results) == 1
    assert results[0].event_ids == [1, 2, 3, 4, 5]
    assert results[0].severity == "High"


def test_r001_no_alert_below_threshold():
    assert brute_force.detect(failures(4), R001) == []


def test_r001_no_alert_when_failures_are_spread_out():
    # 5 failures, but 2 minutes apart -> 8 minutes total, longer than the 5-minute window.
    assert brute_force.detect(failures(5, every_seconds=120), R001) == []


def test_r001_window_boundary_is_inclusive():
    # 5 failures exactly 5 minutes from first to last -> alert.
    assert len(brute_force.detect(failures(5, every_seconds=75), R001)) == 1


def test_r001_does_not_merge_different_users_or_ips():
    events = failures(3, username="alice") + failures(3, start_pk=10, username="bob")
    events += failures(3, start_pk=20, ip="198.51.100.7")
    assert brute_force.detect(events, R001) == []


def test_r001_long_burst_is_one_alert():
    results = brute_force.detect(failures(20, every_seconds=15), R001)
    assert len(results) == 1
    assert results[0].event_ids == list(range(1, 21))


def test_r001_two_separate_bursts_are_two_alerts():
    events = failures(5) + failures(5, start_pk=100, start_seconds=3600)
    assert len(brute_force.detect(events, R001)) == 2


def test_r001_respects_custom_threshold():
    strict = RuleConfig("R001", severity="High", threshold=3, window_minutes=5)
    assert len(brute_force.detect(failures(3), strict)) == 1


def test_r001_explanation_mentions_counts_and_threshold():
    result = brute_force.detect(failures(6), R001)[0]
    assert "6 failed logons" in result.explanation
    assert "threshold is 5 failures within 5 minutes" in result.explanation


# ---------------- R002 Success after failures ----------------

def test_r002_alerts_on_success_after_failures():
    events = failures(5) + [make_event(99, 60, 4624)]
    results = success_after_failures.detect(events, R002)
    assert len(results) == 1
    assert results[0].severity == "Critical"
    assert results[0].event_ids == [1, 2, 3, 4, 5, 99]


def test_r002_no_alert_with_too_few_failures():
    events = failures(4) + [make_event(99, 60, 4624)]
    assert success_after_failures.detect(events, R002) == []


def test_r002_ignores_failures_outside_window():
    events = failures(5) + [make_event(99, 11 * 60, 4624)]  # success 11 minutes later
    assert success_after_failures.detect(events, R002) == []


def test_r002_ignores_success_from_other_ip():
    events = failures(5) + [make_event(99, 60, 4624, ip="10.0.0.5")]
    assert success_after_failures.detect(events, R002) == []


def test_r002_only_first_success_alerts():
    events = failures(5) + [make_event(98, 60, 4624), make_event(99, 70, 4624)]
    assert len(success_after_failures.detect(events, R002)) == 1


# ---------------- R003 User created ----------------

def test_r003_alerts_for_each_account_creation():
    events = [make_event(1, 0, 4720, username="new.user", subject_username="it.admin"), make_event(2, 5, 4624)]
    results = user_created.detect(events, R003)
    assert len(results) == 1
    assert "by 'it.admin'" in results[0].description


def test_r003_ignores_other_events():
    assert user_created.detect(failures(10), R003) == []


# ---------------- R004 Service installed ----------------

@pytest.mark.parametrize(
    "path, expected_severity",
    [
        ("C:\\Program Files\\BackupAgent\\agent.exe", "Medium"),
        ("C:\\Windows\\System32\\svchost.exe -k netsvcs", "Medium"),
        ("C:\\Users\\Public\\Downloads\\x.exe", "High"),
        ("C:\\Users\\bob\\AppData\\Roaming\\x.exe", "High"),
        ("c:\\windows\\temp\\x.exe", "High"),
        (None, "Medium"),
    ],
)
def test_r004_severity_depends_on_path(path, expected_severity):
    results = service_installed.detect([make_event(1, 0, 7045, service_name="Svc", service_path=path)], R004)
    assert len(results) == 1
    assert results[0].severity == expected_severity


# ---------------- Engine with the bundled sample files ----------------

def test_suspicious_sample_triggers_all_four_rules():
    results = run_detection(load_sample("suspicious_events.json"), default_configs())
    assert sorted(r.rule_id for r in results) == ["R001", "R002", "R003", "R004"]
    r004 = next(r for r in results if r.rule_id == "R004")
    assert r004.severity == "High"


def test_normal_sample_triggers_no_alerts():
    assert run_detection(load_sample("normal_events.json"), default_configs()) == []


def test_mixed_csv_sample_alerts():
    results = run_detection(load_sample("mixed_events.csv"), default_configs())
    by_rule = {r.rule_id: r for r in results}
    assert sorted(by_rule) == ["R001", "R004"]
    assert by_rule["R001"].username == "test.user"
    assert by_rule["R004"].severity == "Medium"  # Program Files path


def test_disabled_rule_produces_no_alerts():
    configs = default_configs()
    for config in configs:
        if config.id == "R003":
            config.enabled = False
    results = run_detection(load_sample("suspicious_events.json"), configs)
    assert "R003" not in {r.rule_id for r in results}


def test_every_new_result_is_never_marked_confirmed():
    # Results carry no verdict; the service always saves them as "Suspected".
    results = run_detection(load_sample("suspicious_events.json"), default_configs())
    assert all(not hasattr(r, "verdict") for r in results)
