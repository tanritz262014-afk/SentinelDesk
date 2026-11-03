"""FastAPI application entry point.

Run with:  uvicorn app.main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.routers import alerts, dashboard, events, health, incidents, logs, rules
from app.seed import seed_detection_rules

logger = logging.getLogger("sentineldesk")


def init_database() -> None:
    """Create any missing tables and insert the default detection rules."""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        added = seed_detection_rules(db)
    if added:
        logger.info("Seeded %d default detection rules", added)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Runs once when the server starts.
    init_database()
    yield


settings = get_settings()

app = FastAPI(
    title=f"{settings.app_name} API",
    description="Mini SOC monitoring and incident response platform (learning project).",
    version=__version__,
    lifespan=lifespan,
)

# CORS: only the listed frontend origins may call this API from a browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
    expose_headers=["Content-Disposition"],  # lets the browser read report filenames
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Log unexpected errors on the server, but return a generic message (no stack trace)."""
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(health.router)
app.include_router(logs.router)
app.include_router(events.router)
app.include_router(rules.router)
app.include_router(alerts.router)
app.include_router(incidents.router)
app.include_router(dashboard.router)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"message": f"{settings.app_name} API is running. Open /docs for the API documentation."}
