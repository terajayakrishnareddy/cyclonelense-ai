import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..config import settings
from ..database import check_connection
from ..db_migrations import schema_status
from ..timeutil import iso_utc, utcnow

log = logging.getLogger("cyclonelens.system")
router = APIRouter()
API_VERSION = "2.1.0"


@router.get("/", include_in_schema=False)
def root():
    return {"name": settings.app_name, "docs": "/api/docs" if settings.enable_docs else None, "api_version": API_VERSION}


@router.get("/api/health", tags=["system"])
def health():
    """Liveness: the process is up. Does not touch the database (use /api/ready for that)."""
    return {"status": "ok", "service": settings.app_name, "version": API_VERSION,
            "environment": settings.environment, "timestamp": iso_utc(utcnow())}


@router.get("/api/ready", tags=["system"])
def ready():
    """Readiness: database reachable and schema migrated to the revision this code expects."""
    try:
        check_connection()
        current, head = schema_status()
    except Exception:
        log.exception("Readiness check failed")
        return JSONResponse({"status": "not_ready", "database": "unavailable"}, status_code=503)
    if current != head:
        return JSONResponse({"status": "not_ready", "database": "ok", "schema": "outdated",
                             "schema_revision": current, "expected_revision": head}, status_code=503)
    return {"status": "ready", "database": "ok", "schema_revision": current}
