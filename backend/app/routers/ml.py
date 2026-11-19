import hashlib
import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import ModelRun, Prediction, User
from ..schemas import TrackRequest
from ..security import current_user
from ..services.baseline import constant_motion_track, RESEARCH_DISCLAIMER
from ..timeutil import iso_utc

router = APIRouter(prefix="/api", tags=["models (research)"])

_SIGNATURES = (("image/png", b"\x89PNG\r\n\x1a\n"), ("image/jpeg", b"\xff\xd8\xff"),
               ("image/tiff", b"II*\x00"), ("image/tiff", b"MM\x00*"))

CAPABILITIES = {
    "track_baseline": {"status": "available", "description": "Constant-motion geometric extrapolation. Not machine learning, not a forecast."},
    "image_intake": {"status": "available", "description": "Validates and counts an uploaded image. Nothing is analysed or stored."},
    "image_classification": {"status": "not_configured", "description": "No trained model or storm-matched image dataset is installed."},
    "ml_track_forecast": {"status": "not_configured", "description": "No trained track model is installed."},
    "intensity_forecast": {"status": "not_configured", "description": "No intensity model is installed."},
    "uncertainty_calibration": {"status": "not_configured", "description": "Not implemented."},
    "live_satellite_ingestion": {"status": "not_configured", "description": "No satellite or live weather provider is connected."},
}


@router.post("/ml/predict-track")
def baseline_track(req: TrackRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Constant-motion baseline projection (login required; saved to the user's history)."""
    points = constant_motion_track(req.latitude, req.longitude, req.direction_degrees, req.speed_kmh, req.hours)
    result = {"kind": "baseline_projection", "observed": False, "is_baseline": True,
              "method": "constant-motion geometric baseline", "model_status": "NOT_TRAINED",
              "warning": RESEARCH_DISCLAIMER,
              "start": {"latitude": req.latitude, "longitude": req.longitude},
              "endpoint": {"latitude": points[-1]["latitude"], "longitude": points[-1]["longitude"]},
              "points": points, "hours": req.hours}
    row = Prediction(task="track_baseline", user_id=user.id, input_summary=req.model_dump_json(),
                     output_json=json.dumps(result), is_baseline=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {**result, "prediction_id": row.id}


@router.post("/ml/analyze-image")
async def image_intake(file: UploadFile = File(...), user: User = Depends(current_user)):
    """Image INTAKE only: validates format and size. The image is NOT analysed, classified or stored."""
    limit = settings.max_image_mb * 1024 * 1024
    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data += chunk
        if len(data) > limit:
            raise HTTPException(413, f"Maximum upload size is {settings.max_image_mb} MB")
    detected = next((mime for mime, sig in _SIGNATURES if data.startswith(sig)), None)
    if not data or detected is None:
        raise HTTPException(415, "Only PNG, JPEG or TIFF images are accepted (file content did not match).")
    return {"status": "ACCEPTED_NOT_ANALYZED", "analyzed": False, "stored": False,
            "filename": Path(file.filename or "image").name[:255], "detected_type": detected,
            "bytes_received": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "message": "Image format and size were validated. No classification was performed: no trained, validated "
                       "model is installed. The file was not stored."}


@router.get("/ml/capabilities")
def capabilities():
    return CAPABILITIES


@router.get("/ml/models")
def models(db: Session = Depends(get_db)):
    """Registered trained models. Empty until a real artifact with evaluation is registered."""
    rows = db.scalars(select(ModelRun).order_by(ModelRun.created_at.desc())).all()
    return [{"id": m.id, "name": m.model_name, "version": m.model_version, "task": m.task, "status": m.status,
             "metrics": json.loads(m.metrics_json or "{}"), "created_at": iso_utc(m.created_at)} for m in rows]


@router.get("/predictions")
def predictions(limit: int = 50, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Baseline projection history: your own, or everyone's for administrators."""
    limit = max(1, min(limit, 200))
    q = select(Prediction).order_by(Prediction.created_at.desc(), Prediction.id.desc()).limit(limit)
    if user.role != "admin":
        q = q.where(Prediction.user_id == user.id)
    return [{"id": p.id, "task": p.task, "input": json.loads(p.input_summary or "{}"), "output": json.loads(p.output_json),
             "is_baseline": p.is_baseline, "created_at": iso_utc(p.created_at)} for p in db.scalars(q)]
