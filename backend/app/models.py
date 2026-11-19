from datetime import datetime

from sqlalchemy import String, Float, DateTime, Boolean, ForeignKey, Integer, Text, Index, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base
from .timeutil import utcnow


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="researcher")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ImportRun(Base):
    """One IBTrACS file import: provenance + accurate outcome counts."""
    __tablename__ = "import_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(80))
    filename: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | completed | failed
    rows_seen: Mapped[int] = mapped_column(Integer, default=0)
    rows_added: Mapped[int] = mapped_column(Integer, default=0)
    rows_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    rows_enriched: Mapped[int] = mapped_column(Integer, default=0)
    rows_invalid: Mapped[int] = mapped_column(Integer, default=0)
    rows_skipped_spur: Mapped[int] = mapped_column(Integer, default=0)
    invalid_reasons_json: Mapped[str] = mapped_column(Text, default="{}")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", name="fk_import_runs_user_id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)  # heartbeat, used to detect crashed imports
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CycloneObservation(Base):
    __tablename__ = "cyclone_observations"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    storm_id: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    basin: Mapped[str] = mapped_column(String(40), index=True, default="Unknown")
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)  # naive UTC
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    wind_speed_kt: Mapped[float | None] = mapped_column(Float, nullable=True)
    pressure_hpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Which IBTrACS column the value came from: "WMO" (WMO_WIND/PRES) or "USA" (USA_WIND/PRES fallback).
    wind_source: Mapped[str | None] = mapped_column(String(10), nullable=True)
    pressure_source: Mapped[str | None] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="HISTORICAL")
    source: Mapped[str] = mapped_column(String(80), default="unknown")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    import_run_id: Mapped[int | None] = mapped_column(ForeignKey("import_runs.id", name="fk_obs_import_run"), nullable=True)
    __table_args__ = (Index("uq_storm_time", "storm_id", "timestamp", unique=True),)


class ModelRun(Base):
    __tablename__ = "model_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    model_name: Mapped[str] = mapped_column(String(120))
    model_version: Mapped[str] = mapped_column(String(80))
    task: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), default="UNTRAINED")
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")
    artifact_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Prediction(Base):
    __tablename__ = "predictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    model_run_id: Mapped[int | None] = mapped_column(ForeignKey("model_runs.id"), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", name="fk_predictions_user_id"), nullable=True)
    task: Mapped[str] = mapped_column(String(80))
    input_summary: Mapped[str] = mapped_column(Text)
    output_json: Mapped[str] = mapped_column(Text)
    is_baseline: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
