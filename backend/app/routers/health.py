"""Health check endpoint used by the frontend status indicator."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import __version__
from app.config import get_settings
from app.database import get_db
from app.models import DetectionRule, utc_now
from app.schemas import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """Confirm the API is running and the database answers a simple query."""
    try:
        db.execute(text("SELECT 1"))
        rules_loaded = db.scalar(select(func.count()).select_from(DetectionRule)) or 0
    except SQLAlchemyError:
        # Do not leak database error details to the client.
        raise HTTPException(status_code=503, detail="Database unavailable")

    return HealthResponse(
        status="ok",
        app=get_settings().app_name,
        version=__version__,
        database="connected",
        rules_loaded=rules_loaded,
        server_time=utc_now(),
    )
