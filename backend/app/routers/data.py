import hashlib
import json
import logging
import uuid
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db, SessionLocal
from ..models import ImportRun, User
from ..security import current_user
from ..services.ibtracs import run_import, validate_header, ImportFileError, SOURCE_LABEL
from ..timeutil import iso_utc, utcnow

log = logging.getLogger("cyclonelens.data")
router = APIRouter(prefix="/api/data", tags=["data import"])
STALE_AFTER = timedelta(minutes=10)  # a 'running' import with no progress for this long is considered crashed


def import_out(r: ImportRun) -> dict:
    detail = json.loads(r.invalid_reasons_json or "{}")
    return {"id": r.id, "source": r.source, "filename": r.filename, "sha256": r.sha256, "size_bytes": r.size_bytes,
            "status": r.status, "rows_seen": r.rows_seen, "rows_added": r.rows_added,
            "rows_duplicate": r.rows_duplicate, "rows_enriched": r.rows_enriched, "rows_invalid": r.rows_invalid,
            "rows_skipped_spur": r.rows_skipped_spur, "invalid_reasons": detail.get("invalid_rows", {}),
            "notes": detail.get("notes", {}), "error": r.error_message,
            "started_at": iso_utc(r.started_at), "finished_at": iso_utc(r.finished_at)}


def _job(run_id: int, path: str, chunk_rows: int):
    try:
        with SessionLocal() as db:
            run = db.get(ImportRun, run_id)
            run_import(db, run, path, chunk_rows)
    finally:
        Path(path).unlink(missing_ok=True)  # uploaded file is never kept; only its hash/metadata are recorded


@router.post("/import-ibtracs", status_code=202)
async def import_ibtracs(background: BackgroundTasks, file: UploadFile = File(...),
                         admin: User = Depends(current_user), db: Session = Depends(get_db)):
    """Queue an import of an official IBTrACS CSV (administrators only). Poll GET /api/data/imports/{id}."""
    name = Path(file.filename or "").name
    if not name.lower().endswith(".csv"):
        raise HTTPException(400, "Please upload the official IBTrACS CSV file (.csv).")

    for r in db.scalars(select(ImportRun).where(ImportRun.status == "running")):
        if utcnow() - r.updated_at > STALE_AFTER:
            r.status, r.error_message, r.finished_at = "failed", "Import was interrupted (no progress; server restarted?).", utcnow()
    db.commit()
    if db.scalar(select(ImportRun.id).where(ImportRun.status == "running").limit(1)):
        raise HTTPException(409, "Another import is already running. Wait for it to finish.")

    tmp_dir = Path(settings.upload_dir) / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    path = tmp_dir / f"{uuid.uuid4().hex}.csv"
    limit, size, digest = settings.max_import_mb * 1024 * 1024, 0, hashlib.sha256()
    try:
        with path.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, f"File exceeds the {settings.max_import_mb} MB upload limit")
                digest.update(chunk)
                await run_in_threadpool(out.write, chunk)
        try:
            validate_header(str(path))
        except ImportFileError as exc:
            raise HTTPException(400, str(exc))
    except BaseException:
        path.unlink(missing_ok=True)
        raise

    run = ImportRun(source=SOURCE_LABEL, filename=name[:255], sha256=digest.hexdigest(), size_bytes=size,
                    status="running", user_id=admin.id)
    db.add(run)
    db.commit()
    db.refresh(run)
    background.add_task(_job, run.id, str(path), settings.import_chunk_rows)
    log.info("Import %s queued by user %s (%s, %d bytes)", run.id, admin.id, name, size)
    return import_out(run)


@router.get("/imports")
def list_imports(db: Session = Depends(get_db)):
    """Import history (provenance of the data in this database)."""
    return [import_out(r) for r in db.scalars(select(ImportRun).order_by(ImportRun.id.desc()).limit(20))]


@router.get("/imports/{run_id}")
def get_import(run_id: int, db: Session = Depends(get_db)):
    run = db.get(ImportRun, run_id)
    if not run:
        raise HTTPException(404, "Import not found")
    return import_out(run)
