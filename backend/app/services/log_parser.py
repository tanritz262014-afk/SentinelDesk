"""Read and validate uploaded security log files (JSON or CSV).

Safety rules followed here:
- The file is only ever treated as text data. It is parsed with Python's
  built-in json and csv modules and is never executed or saved as a file.
- File-level problems (wrong type, too big, not UTF-8, broken JSON) reject the
  whole file with LogValidationError.
- Row-level problems (missing timestamp, bad IP, ...) reject only that row.
  The row number and reason are reported back so the analyst can fix it.
"""

import csv
import io
import ipaddress
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import PurePath

from app.detection.event_catalog import get_category

ALLOWED_EXTENSIONS = {".json", ".csv"}
REQUIRED_FIELDS = ("timestamp", "event_id")
MAX_REPORTED_ERRORS = 100

# Maximum length for each text field. Longer values reject the row.
TEXT_FIELD_LIMITS = {
    "hostname": 255,
    "username": 255,
    "logon_type": 20,
    "service_name": 255,
    "service_path": 1024,
    "message": 2000,
}

# Different tools export the same field under different names.
# Keys are matched after lower-casing and replacing spaces/dashes with "_".
FIELD_ALIASES = {
    "time": "timestamp",
    "timecreated": "timestamp",
    "time_created": "timestamp",
    "eventid": "event_id",
    "event_code": "event_id",
    "computer": "hostname",
    "computername": "hostname",
    "host": "hostname",
    "user": "username",
    "targetusername": "username",
    "target_username": "username",
    "ipaddress": "source_ip",
    "ip_address": "source_ip",
    "src_ip": "source_ip",
    "logontype": "logon_type",
    "servicename": "service_name",
    "imagepath": "service_path",
    "image_path": "service_path",
    "servicefilename": "service_path",
}


class LogValidationError(Exception):
    """The whole file was rejected. `errors` may hold row-level details."""

    def __init__(self, message: str, status_code: int = 400, errors: list | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.errors = errors or []


class RowValidationError(Exception):
    """One row is invalid. The message explains why."""


@dataclass
class RowError:
    row: int
    message: str


@dataclass
class ParseResult:
    file_type: str
    total_rows: int
    events: list[dict] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)


# ---------------------------------------------------------------------------
# File-level checks
# ---------------------------------------------------------------------------

def safe_filename(filename: str | None) -> str:
    """Keep only the base name and safe characters (blocks '../../' tricks)."""
    name = PurePath((filename or "").replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip()
    return name[:255]


def get_file_type(filename: str) -> str:
    extension = PurePath(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise LogValidationError(
            f"Unsupported file type '{extension or 'none'}'. Only .json and .csv files are accepted.",
            status_code=415,
        )
    return extension.lstrip(".")


def decode_text(content: bytes) -> str:
    if b"\x00" in content:
        raise LogValidationError("The file looks like binary data, not a text log file.")
    try:
        # utf-8-sig also removes the BOM that Excel adds to CSV files on Windows.
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise LogValidationError("The file is not valid UTF-8 text.")


# ---------------------------------------------------------------------------
# Row-level checks
# ---------------------------------------------------------------------------

def normalize_key(key: str) -> str:
    cleaned = key.strip().lower().replace(" ", "_").replace("-", "_")
    return FIELD_ALIASES.get(cleaned, cleaned)


def clean_text(value) -> str | None:
    """Turn a value into trimmed text. Empty values become None."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise RowValidationError("must be plain text")
    text = str(value).strip()
    return text or None


def parse_timestamp(value) -> datetime:
    text = clean_text(value)
    if text is None:
        raise RowValidationError("timestamp is required")
    try:
        # Accepts ISO 8601, e.g. 2026-10-01T09:15:02Z or 2026-10-01 09:15:02+05:30
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise RowValidationError(f"timestamp '{text[:40]}' is not a valid ISO 8601 date/time")
    if parsed.tzinfo is not None:
        # Store everything in UTC so events from different time zones line up.
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    # Times without a time zone are assumed to already be UTC.
    return parsed


def parse_event_id(value) -> int:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise RowValidationError("event_id is required")
    if isinstance(value, bool):
        raise RowValidationError("event_id must be a whole number")
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and value.strip().isdigit():
        number = int(value.strip())
    else:
        raise RowValidationError(f"event_id '{str(value)[:20]}' must be a whole number")
    if not 1 <= number <= 65535:
        raise RowValidationError("event_id must be between 1 and 65535")
    return number


def parse_ip(value) -> str | None:
    text = clean_text(value)
    # Windows writes "-" when there is no IP address.
    if text is None or text == "-":
        return None
    try:
        return str(ipaddress.ip_address(text))
    except ValueError:
        raise RowValidationError(f"source_ip '{text[:45]}' is not a valid IP address")


def validate_row(raw_row: dict) -> dict:
    """Check one log row and return a normalized event dictionary."""
    row = {normalize_key(str(k)): v for k, v in raw_row.items() if k is not None}

    event = {
        "timestamp": parse_timestamp(row.get("timestamp")),
        "event_id": parse_event_id(row.get("event_id")),
        "source_ip": parse_ip(row.get("source_ip")),
    }
    for name, max_length in TEXT_FIELD_LIMITS.items():
        try:
            text = clean_text(row.get(name))
        except RowValidationError as exc:
            raise RowValidationError(f"{name} {exc}")
        if text is not None and len(text) > max_length:
            raise RowValidationError(f"{name} is longer than {max_length} characters")
        event[name] = text

    event["event_category"] = get_category(event["event_id"])
    # Keep the original row (as text) so analysts can see exactly what was uploaded.
    event["raw_data"] = json.dumps(raw_row, ensure_ascii=False, default=str)
    return event


# ---------------------------------------------------------------------------
# Format readers: each returns a list of (row_number, row_dict_or_other)
# ---------------------------------------------------------------------------

def read_json_rows(text: str) -> list[tuple[int, object]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LogValidationError(f"Invalid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno}).")

    if isinstance(data, dict) and isinstance(data.get("events"), list):
        data = data["events"]
    if not isinstance(data, list):
        raise LogValidationError('JSON must be a list of events, or an object like {"events": [...]}.')
    return [(index, item) for index, item in enumerate(data, start=1)]


def read_csv_rows(text: str) -> list[tuple[int, object]]:
    reader = csv.DictReader(io.StringIO(text, newline=""))
    try:
        header = reader.fieldnames
        if not header:
            raise LogValidationError("The CSV file has no header row.")
        normalized_header = {normalize_key(column) for column in header if column}
        missing = [name for name in REQUIRED_FIELDS if name not in normalized_header]
        if missing:
            raise LogValidationError(f"The CSV header is missing required column(s): {', '.join(missing)}.")

        rows = []
        for row in reader:
            # DictReader stores extra cells under the key None.
            if None in row:
                rows.append((reader.line_num, "too many columns in this row"))
            else:
                rows.append((reader.line_num, row))
        return rows
    except csv.Error as exc:
        raise LogValidationError(f"Invalid CSV: {exc}.")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def parse_log_file(filename: str, content: bytes, max_bytes: int, max_events: int) -> ParseResult:
    """Validate an uploaded log file and return the normalized events.

    Raises LogValidationError if the file as a whole cannot be accepted.
    """
    file_type = get_file_type(filename)

    if len(content) == 0:
        raise LogValidationError("The file is empty.")
    if len(content) > max_bytes:
        raise LogValidationError(
            f"The file is larger than the {max_bytes // (1024 * 1024)} MB limit.", status_code=413
        )

    text = decode_text(content)
    rows = read_json_rows(text) if file_type == "json" else read_csv_rows(text)

    if not rows:
        raise LogValidationError("The file contains no events.")
    if len(rows) > max_events:
        raise LogValidationError(
            f"The file has {len(rows)} events; the limit is {max_events} per file.", status_code=413
        )

    result = ParseResult(file_type=file_type, total_rows=len(rows))
    for row_number, row in rows:
        if isinstance(row, str):  # a problem already found by the reader
            result.errors.append(RowError(row_number, row))
            continue
        if not isinstance(row, dict):
            result.errors.append(RowError(row_number, "each event must be a JSON object"))
            continue
        try:
            result.events.append(validate_row(row))
        except RowValidationError as exc:
            result.errors.append(RowError(row_number, str(exc)))

    if not result.events:
        raise LogValidationError(
            "No valid events were found in the file.", status_code=422, errors=result.errors
        )
    return result
