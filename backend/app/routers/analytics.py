from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CycloneObservation as Obs, ImportRun
from ..timeutil import iso_utc

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    total = db.scalar(select(func.count(Obs.id))) or 0
    last_import = db.scalar(select(ImportRun).where(ImportRun.status == "completed").order_by(ImportRun.id.desc()).limit(1))
    return {
        "observations": total,
        "storms": db.scalar(select(func.count(func.distinct(Obs.storm_id)))) or 0,
        "basins": db.scalar(select(func.count(func.distinct(Obs.basin)))) or 0,
        "demo_records": db.scalar(select(func.count(Obs.id)).where(Obs.is_demo.is_(True))) or 0,
        "source_records": db.scalar(select(func.count(Obs.id)).where(Obs.source == "NOAA_IBTRACS_v04r01")) or 0,
        "mean_wind_kt": round(db.scalar(select(func.avg(Obs.wind_speed_kt))) or 0, 1),
        "observations_with_wind": db.scalar(select(func.count(Obs.id)).where(Obs.wind_speed_kt.is_not(None))) or 0,
        "first_observation": iso_utc(db.scalar(select(func.min(Obs.timestamp)))),
        "last_observation": iso_utc(db.scalar(select(func.max(Obs.timestamp)))),
        "last_import": None if not last_import else {"id": last_import.id, "filename": last_import.filename,
                                                     "finished_at": iso_utc(last_import.finished_at)},
    }


@router.get("/by-basin")
def by_basin(db: Session = Depends(get_db)):
    rows = db.execute(select(Obs.basin, func.count(Obs.id).label("n")).group_by(Obs.basin).order_by(func.count(Obs.id).desc())).all()
    return [{"basin": b, "count": n} for b, n in rows]


@router.get("/yearly")
def yearly(db: Session = Depends(get_db)):
    year = func.extract("year", Obs.timestamp)
    rows = db.execute(select(year.label("y"), func.count(Obs.id)).group_by(year).order_by(year)).all()
    return [{"year": str(int(y)), "observations": n} for y, n in rows]
