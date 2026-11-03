"""Save a parsed log file and run detection on it.

Used by the upload API and by the demo-data loader, so both follow exactly
the same path: store the upload and its events, then run the rules.
"""

from sqlalchemy.orm import Session

from app.models import Alert, LogUpload, SecurityEvent
from app.services.detection_service import detect_and_save
from app.services.log_parser import ParseResult


def store_upload(db: Session, filename: str, size_bytes: int, result: ParseResult) -> tuple[LogUpload, list[Alert]]:
    upload = LogUpload(
        filename=filename,
        file_type=result.file_type,
        file_size_bytes=size_bytes,
        total_rows=result.total_rows,
        accepted_rows=len(result.events),
        rejected_rows=len(result.errors),
    )
    upload.events = [SecurityEvent(**event) for event in result.events]
    db.add(upload)
    db.commit()

    # Run the detection rules on the events from this upload.
    alerts = detect_and_save(db, upload.events)
    return upload, alerts
