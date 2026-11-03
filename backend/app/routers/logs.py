"""Log upload endpoints."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import LogUpload
from app.schemas import AlertBrief, LogUploadOut, UploadResult
from app.services.ingest_service import store_upload
from app.services.log_parser import (
    MAX_REPORTED_ERRORS,
    LogValidationError,
    parse_log_file,
    safe_filename,
)

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.post("/upload", response_model=UploadResult, status_code=status.HTTP_201_CREATED)
def upload_log_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a JSON or CSV security log. Valid rows are stored; invalid rows are reported."""
    settings = get_settings()

    filename = safe_filename(file.filename)
    if not filename:
        raise HTTPException(status_code=400, detail="The uploaded file has no name.")

    # Read at most one byte more than the limit, so a huge file is never fully loaded.
    content = file.file.read(settings.max_upload_bytes + 1)

    try:
        result = parse_log_file(
            filename,
            content,
            max_bytes=settings.max_upload_bytes,
            max_events=settings.max_events_per_file,
        )
    except LogValidationError as exc:
        body = {"detail": exc.message}
        if exc.errors:
            body["errors"] = [vars(e) for e in exc.errors[:MAX_REPORTED_ERRORS]]
        return JSONResponse(status_code=exc.status_code, content=body)

    upload, alerts = store_upload(db, filename, len(content), result)

    return UploadResult(
        upload_id=upload.id,
        filename=upload.filename,
        file_type=upload.file_type,
        total_rows=upload.total_rows,
        accepted_rows=upload.accepted_rows,
        rejected_rows=upload.rejected_rows,
        errors=[vars(e) for e in result.errors[:MAX_REPORTED_ERRORS]],
        errors_truncated=len(result.errors) > MAX_REPORTED_ERRORS,
        alerts_generated=len(alerts),
        alerts=[AlertBrief(id=a.id, rule_id=a.rule_id, title=a.title, severity=a.severity) for a in alerts],
    )


@router.get("/uploads", response_model=list[LogUploadOut])
def list_uploads(db: Session = Depends(get_db)):
    """List uploaded files, newest first."""
    return db.scalars(select(LogUpload).order_by(LogUpload.uploaded_at.desc(), LogUpload.id.desc())).all()
