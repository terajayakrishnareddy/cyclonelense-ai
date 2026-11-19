from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CycloneObservation as Obs
from ..schemas import ObservationOut
from ..timeutil import iso_utc

router = APIRouter(prefix="/api", tags=["historical data"])


def _filters(q, basin, search, min_wind):
    if basin and basin.lower() != "all":
        q = q.where(func.lower(Obs.basin) == basin.lower())
    if search:
        like = f"%{search.strip()}%"
        q = q.where(Obs.name.ilike(like) | Obs.storm_id.ilike(like))
    if min_wind is not None:
        q = q.where(Obs.wind_speed_kt >= min_wind)
    return q


@router.get("/cyclones", response_model=list[ObservationOut])
def list_observations(basin: str | None = None, search: str | None = None,
                      min_wind: float | None = Query(default=None, ge=0),
                      limit: int = Query(default=1000, ge=1, le=10000), db: Session = Depends(get_db)):
    """Individual historical observations (most recent first). Observed data only."""
    q = _filters(select(Obs), basin, search, min_wind)
    return db.scalars(q.order_by(Obs.timestamp.desc(), Obs.id.desc()).limit(limit)).all()


@router.get("/storms")
def list_storms(basin: str | None = None, search: str | None = None,
                min_wind: float | None = Query(default=None, ge=0, description="Storm's peak wind (kt) at least this"),
                limit: int = Query(default=50, ge=1, le=500), offset: int = Query(default=0, ge=0),
                db: Session = Depends(get_db)):
    """One row per storm (aggregated from observations) - the unit the explorer and map work with."""
    base = _filters(select(Obs.storm_id), basin, search, None)
    having = []
    if min_wind is not None:
        having.append(func.max(Obs.wind_speed_kt) >= min_wind)
    grouped = base.group_by(Obs.storm_id)
    for h in having:
        grouped = grouped.having(h)
    total = db.scalar(select(func.count()).select_from(grouped.subquery()))
    q = _filters(select(
        Obs.storm_id, func.max(Obs.name).label("name"), func.max(Obs.basin).label("basin"),
        func.min(Obs.timestamp).label("start_time"), func.max(Obs.timestamp).label("end_time"),
        func.count(Obs.id).label("observations"), func.max(Obs.wind_speed_kt).label("max_wind_kt"),
        func.min(Obs.pressure_hpa).label("min_pressure_hpa"), func.max(Obs.source).label("source"),
    ), basin, search, None).group_by(Obs.storm_id)
    for h in having:
        q = q.having(h)
    rows = db.execute(q.order_by(func.min(Obs.timestamp).desc(), Obs.storm_id).limit(limit).offset(offset)).all()
    return {"total": total or 0, "limit": limit, "offset": offset,
            "items": [{"storm_id": r.storm_id, "name": r.name, "basin": r.basin, "start_time": iso_utc(r.start_time),
                       "end_time": iso_utc(r.end_time), "observations": r.observations, "max_wind_kt": r.max_wind_kt,
                       "min_pressure_hpa": r.min_pressure_hpa, "source": r.source} for r in rows]}


@router.get("/cyclones/{storm_id}/track")
def storm_track(storm_id: str, db: Session = Depends(get_db)):
    """The observed best track of one storm (never a projection)."""
    rows = db.scalars(select(Obs).where(Obs.storm_id == storm_id).order_by(Obs.timestamp)).all()
    if not rows:
        raise HTTPException(404, "Storm ID not found")
    return {"storm_id": storm_id, "name": rows[0].name, "basin": rows[0].basin, "kind": "observed_best_track",
            "source": rows[0].source,
            "points": [{"timestamp": iso_utc(r.timestamp), "latitude": r.latitude, "longitude": r.longitude,
                        "wind_speed_kt": r.wind_speed_kt, "pressure_hpa": r.pressure_hpa,
                        "wind_source": r.wind_source, "pressure_source": r.pressure_source} for r in rows]}
