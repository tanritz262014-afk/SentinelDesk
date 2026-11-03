"""Unit tests for app/services/log_parser.py (no database or API involved)."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from app.services.log_parser import LogValidationError, parse_log_file, safe_filename

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"
MAX_BYTES = 2 * 1024 * 1024
MAX_EVENTS = 10000


def parse(filename: str, content, max_bytes=MAX_BYTES, max_events=MAX_EVENTS):
    if isinstance(content, (list, dict)):
        content = json.dumps(content)
    if isinstance(content, str):
        content = content.encode("utf-8")
    return parse_log_file(filename, content, max_bytes=max_bytes, max_events=max_events)


VALID_EVENT = {"timestamp": "2026-10-01T09:15:02Z", "event_id": 4625, "username": "j.doe", "source_ip": "203.0.113.45"}


# ----- Happy paths -----

def test_parses_json_list():
    result = parse("logs.json", [VALID_EVENT])
    assert result.file_type == "json"
    assert result.total_rows == 1
    event = result.events[0]
    assert event["event_id"] == 4625
    assert event["event_category"] == "Authentication Failure"
    assert event["timestamp"] == datetime(2026, 10, 1, 9, 15, 2)
    assert json.loads(event["raw_data"]) == VALID_EVENT


def test_parses_json_object_with_events_key():
    result = parse("logs.json", {"description": "demo", "events": [VALID_EVENT, VALID_EVENT]})
    assert len(result.events) == 2


def test_parses_csv_with_bom_and_alias_headers():
    # Excel on Windows adds a BOM; other tools use names like EventID / IpAddress.
    csv_text = "\ufeffTimeCreated,EventID,Computer,TargetUserName,IpAddress\n" \
               "2026-10-01 09:15:02,4624,WS-01,j.doe,10.0.0.5\n"
    result = parse("export.csv", csv_text)
    event = result.events[0]
    assert event["event_id"] == 4624
    assert event["hostname"] == "WS-01"
    assert event["username"] == "j.doe"
    assert event["source_ip"] == "10.0.0.5"


def test_timestamp_with_offset_is_converted_to_utc():
    result = parse("logs.json", [{**VALID_EVENT, "timestamp": "2026-10-01T14:45:02+05:30"}])
    assert result.events[0]["timestamp"] == datetime(2026, 10, 1, 9, 15, 2)


def test_text_is_trimmed_and_blank_becomes_none():
    result = parse("logs.json", [{**VALID_EVENT, "username": "  j.doe  ", "hostname": "   "}])
    assert result.events[0]["username"] == "j.doe"
    assert result.events[0]["hostname"] is None


def test_dash_ip_means_no_ip():
    result = parse("logs.json", [{**VALID_EVENT, "source_ip": "-"}])
    assert result.events[0]["source_ip"] is None


def test_unknown_event_id_is_accepted_as_other():
    result = parse("logs.json", [{**VALID_EVENT, "event_id": 4634}])
    assert result.events[0]["event_category"] == "Other"


def test_command_text_is_stored_as_plain_text_only():
    command = "powershell.exe -nop -w hidden -c Remove-Item C:\\important"
    result = parse("logs.json", [{**VALID_EVENT, "event_id": 7045, "service_path": command}])
    # The parser just keeps the text; nothing is executed.
    assert result.events[0]["service_path"] == command


# ----- File-level rejections -----

@pytest.mark.parametrize("filename", ["malware.exe", "notes.txt", "logs", "logs.json.exe", "archive.zip"])
def test_rejects_unsupported_extensions(filename):
    with pytest.raises(LogValidationError) as exc:
        parse(filename, [VALID_EVENT])
    assert exc.value.status_code == 415


def test_extension_check_is_case_insensitive():
    assert parse("LOGS.JSON", [VALID_EVENT]).file_type == "json"


def test_rejects_empty_file():
    with pytest.raises(LogValidationError, match="empty"):
        parse("logs.json", b"")


def test_rejects_file_over_size_limit():
    with pytest.raises(LogValidationError) as exc:
        parse("logs.json", [VALID_EVENT], max_bytes=10)
    assert exc.value.status_code == 413


def test_rejects_too_many_events():
    with pytest.raises(LogValidationError) as exc:
        parse("logs.json", [VALID_EVENT] * 3, max_events=2)
    assert exc.value.status_code == 413


def test_rejects_non_utf8():
    with pytest.raises(LogValidationError, match="UTF-8"):
        parse("logs.csv", "timestamp,event_id\n".encode("utf-8") + b"\xff\xfe\xfa")


def test_rejects_binary_content():
    with pytest.raises(LogValidationError, match="binary"):
        parse("logs.json", b"MZ\x90\x00\x03\x00\x00\x00")


def test_rejects_broken_json():
    with pytest.raises(LogValidationError, match="Invalid JSON"):
        parse("logs.json", '[{"timestamp": "2026-10-01T09:15:02Z",')


def test_rejects_json_that_is_not_a_list():
    with pytest.raises(LogValidationError, match="list of events"):
        parse("logs.json", {"timestamp": "x"})


def test_rejects_empty_event_list():
    with pytest.raises(LogValidationError, match="no events"):
        parse("logs.json", [])


def test_rejects_csv_without_required_columns():
    with pytest.raises(LogValidationError, match="event_id"):
        parse("logs.csv", "timestamp,username\n2026-10-01T09:15:02Z,j.doe\n")


def test_rejects_file_when_no_row_is_valid():
    with pytest.raises(LogValidationError) as exc:
        parse("logs.json", [{"event_id": 4625}])
    assert exc.value.status_code == 422
    assert exc.value.errors[0].message == "timestamp is required"


# ----- Row-level rejections -----

@pytest.mark.parametrize(
    "bad_fields, expected_message",
    [
        ({"timestamp": None}, "timestamp is required"),
        ({"timestamp": "yesterday"}, "not a valid ISO 8601"),
        ({"event_id": None}, "event_id is required"),
        ({"event_id": "abc"}, "must be a whole number"),
        ({"event_id": 4625.5}, "must be a whole number"),
        ({"event_id": True}, "must be a whole number"),
        ({"event_id": 70000}, "between 1 and 65535"),
        ({"source_ip": "999.1.1.1"}, "not a valid IP address"),
        ({"hostname": {"nested": "object"}}, "hostname must be plain text"),
        ({"username": "x" * 300}, "longer than 255"),
    ],
)
def test_invalid_rows_are_reported_and_valid_rows_kept(bad_fields, expected_message):
    result = parse("logs.json", [VALID_EVENT, {**VALID_EVENT, **bad_fields}])
    assert len(result.events) == 1
    assert len(result.errors) == 1
    assert result.errors[0].row == 2
    assert expected_message in result.errors[0].message


def test_non_object_json_row_is_rejected():
    result = parse("logs.json", [VALID_EVENT, "not an object", 42])
    assert [e.row for e in result.errors] == [2, 3]


def test_csv_row_numbers_match_file_lines():
    csv_text = "timestamp,event_id\n2026-10-01T09:15:02Z,4625\nbad-date,4625\n"
    result = parse("logs.csv", csv_text)
    assert result.errors[0].row == 3


def test_csv_row_with_extra_columns_is_rejected():
    csv_text = "timestamp,event_id\n2026-10-01T09:15:02Z,4625\n2026-10-01T09:16:00Z,4625,extra\n"
    result = parse("logs.csv", csv_text)
    assert len(result.events) == 1
    assert result.errors[0].message == "too many columns in this row"


# ----- Filenames -----

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("../../etc/passwd.json", "passwd.json"),
        ("..\\..\\Windows\\evil.csv", "evil.csv"),
        ("my logs (1).json", "my logs _1_.json"),
        ("", ""),
        (None, ""),
    ],
)
def test_safe_filename(raw, expected):
    assert safe_filename(raw) == expected


# ----- Bundled sample files -----

@pytest.mark.parametrize(
    "filename, accepted, rejected",
    [
        ("suspicious_events.json", 12, 0),
        ("normal_events.json", 13, 0),
        ("mixed_events.csv", 11, 0),
        ("invalid_events.json", 2, 6),
    ],
)
def test_sample_files_parse_as_documented(filename, accepted, rejected):
    result = parse(filename, (SAMPLE_DIR / filename).read_bytes())
    assert len(result.events) == accepted
    assert len(result.errors) == rejected
