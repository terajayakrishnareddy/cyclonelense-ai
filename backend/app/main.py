import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .db_migrations import run_migrations
from .routers import analytics, auth, cyclones, data, ml, system

logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
log = logging.getLogger("cyclonelens")

# Endpoints that accept large uploads: reject by Content-Length before the body is parsed/spooled.
_UPLOAD_LIMITS = {"/api/data/import-ibtracs": lambda: settings.max_import_mb, "/api/ml/analyze-image": lambda: settings.max_image_mb}


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.secret_is_ephemeral:
        log.warning("SECRET_KEY is not set: using a random per-process key (logins reset on restart). Set SECRET_KEY.")
    if settings.should_auto_migrate:
        log.info("Applying database migrations")
        run_migrations()
    yield


app = FastAPI(
    title="CycloneLens AI API", version=system.API_VERSION, lifespan=lifespan,
    docs_url="/api/docs" if settings.enable_docs else None, redoc_url=None,
    openapi_url="/api/openapi.json" if settings.enable_docs else None,
    description="Research platform API. Historical observations are sourced from NOAA IBTrACS; track projections are "
                "an untrained constant-motion baseline. NOT an operational forecast or warning system.")

app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=False,
                   allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Authorization", "Content-Type"])


@app.middleware("http")
async def request_guard(request: Request, call_next):
    limit_mb = _UPLOAD_LIMITS.get(request.url.path)
    if limit_mb and request.method == "POST":
        try:
            length = int(request.headers.get("content-length", "0"))
        except ValueError:
            length = 0
        if length > (limit_mb() + 1) * 1024 * 1024:
            return JSONResponse({"detail": f"Upload exceeds the {limit_mb()} MB limit"}, status_code=413)
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    request.state.request_id = rid
    try:
        response = await call_next(request)
    except Exception:
        log.exception("Unhandled error [%s] %s %s", rid, request.method, request.url.path)
        response = JSONResponse({"detail": "Internal server error", "request_id": rid}, status_code=500)
    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    if request.url.path.startswith("/api/auth"):
        response.headers["Cache-Control"] = "no-store"
    return response


for module in (system, auth, cyclones, analytics, data, ml):
    app.include_router(module.router)
