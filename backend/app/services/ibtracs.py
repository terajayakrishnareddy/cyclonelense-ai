"""NOAA/NCEI IBTrACS best-track CSV import.

Design:
* Streams the file row by row (csv module) - memory stays flat for the ~300 MB ALL file.
* Every data row is accounted for: seen = added + duplicate + invalid + skipped_spur.
* Committed per chunk, so a failure midway never reports rows that were rolled back;
  earlier chunks stay (the import is idempotent, re-running resumes safely).
* Idempotent: (storm_id, timestamp) is unique; duplicates are skipped, and an existing
  row with missing wind/pressure is enriched when the file has a value.
* Provenance: every row is tagged with the source/version and the ImportRun id; wind and
  pressure record whether they came from the WMO_* or the USA_* (fallback) columns.
"""
import csv
import json
import logging
import math
from collections import Counter
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, update, bindparam
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ..models import CycloneObservation, ImportRun
from ..timeutil import utcnow

log = logging.getLogger("cyclonelens.import")

SOURCE_LABEL = "NOAA_IBTRACS_v04r01"
IBTRACS_CSV = ("https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/"
               "v04r01/access/csv/ibtracs.ALL.list.v04r01.csv")
REQUIRED = ["SID", "NAME", "ISO_TIME", "LAT", "LON", "BASIN"]
OPTIONAL = ["WMO_WIND", "WMO_PRES", "USA_WIND", "USA_PRES", "TRACK_TYPE"]
MAX_REASON_KEYS = 20


class ImportFileError(ValueError):
    """The file cannot be imported at all (bad type/header). Message is safe to show users."""


def _open(path: str):
    return open(path, "r", encoding="utf-8-sig", errors="replace", newline="")


def validate_header(path: str) -> list[str]:
    """Cheap pre-flight check used by the API before a job is queued."""
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        raise ImportFileError("The uploaded file is empty.")
    with p.open("rb") as fh:
        if b"\x00" in fh.read(8192):
            raise ImportFileError("The file looks binary, not CSV. Upload the IBTrACS .csv file.")
    with _open(path) as fh:
        try:
            header = next(csv.reader(fh))
        except StopIteration:
            raise ImportFileError("The uploaded file is empty.")
    header = [h.strip() for h in header]
    missing = [c for c in REQUIRED if c not in header]
    if missing:
        raise ImportFileError(f"Not an IBTrACS CSV: required column(s) missing: {', '.join(missing)}.")
    return header


def _num(raw: str) -> float | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        v = float(raw)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def _time(raw: str) -> datetime | None:
    raw = raw.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            pass
    try:
        dt = datetime.fromisoformat(raw)
        return dt.replace(tzinfo=None) if dt.tzinfo is None else dt.astimezone(None).replace(tzinfo=None)
    except ValueError:
        return None


def _pick(row, idx, wmo_col, usa_col, lo, hi):
    """WMO value if plausible, else USA fallback; returns (value, label, out_of_range_flag)."""
    out_of_range = False
    for col, label in ((wmo_col, "WMO"), (usa_col, "USA")):
        i = idx.get(col)
        if i is None:
            continue
        v = _num(row[i])
        if v is None:
            continue
        if lo <= v <= hi:
            return v, label, out_of_range
        out_of_range = True
    return None, None, out_of_range


def parse_row(row: list[str], idx: dict[str, int]):
    """Returns (record, None) or (None, reason). reason 'spur_track' means intentionally skipped."""
    tt = idx.get("TRACK_TYPE")
    if tt is not None and row[tt].strip().lower().startswith("spur"):
        return None, "spur_track"
    sid = row[idx["SID"]].strip()
    if not sid or len(sid) > 80:
        return None, "missing_or_invalid_storm_id"
    ts = _time(row[idx["ISO_TIME"]])
    if ts is None:
        return None, "invalid_time"
    lat, lon = _num(row[idx["LAT"]]), _num(row[idx["LON"]])
    if lat is None or lon is None:
        return None, "invalid_coordinates"
    if not (-90 <= lat <= 90 and -180 <= lon <= 360):
        return None, "coordinates_out_of_range"
    if lon > 180:
        lon -= 360
    wind, wind_src, w_bad = _pick(row, idx, "WMO_WIND", "USA_WIND", 0, 300)
    pres, pres_src, p_bad = _pick(row, idx, "WMO_PRES", "USA_PRES", 800, 1100)
    return {
        "storm_id": sid, "name": (row[idx["NAME"]].strip() or "UNNAMED")[:100],
        "basin": (row[idx["BASIN"]].strip() or "Unknown")[:40], "timestamp": ts,
        "latitude": lat, "longitude": lon, "wind_speed_kt": wind, "pressure_hpa": pres,
        "wind_source": wind_src, "pressure_source": pres_src,
        "status": "HISTORICAL", "source": SOURCE_LABEL, "is_demo": False,
    }, ("out_of_range_value_ignored" if (w_bad or p_bad) else None)


def _insert_ignore(db: Session, rows: list[dict]) -> None:
    dialect = db.get_bind().dialect.name
    table = CycloneObservation.__table__
    if dialect == "postgresql":
        stmt = pg_insert(table).on_conflict_do_nothing()
    elif dialect == "sqlite":
        stmt = sqlite_insert(table).on_conflict_do_nothing()
    else:  # pragma: no cover - only sqlite/postgresql are supported
        db.execute(table.insert(), rows)
        return
    db.execute(stmt, rows)


def _existing(db: Session, sids: list[str]) -> dict[tuple, tuple]:
    found = {}
    for i in range(0, len(sids), 500):
        q = select(CycloneObservation.storm_id, CycloneObservation.timestamp, CycloneObservation.id,
                   CycloneObservation.wind_speed_kt, CycloneObservation.pressure_hpa
                   ).where(CycloneObservation.storm_id.in_(sids[i:i + 500]))
        for sid, ts, oid, w, p in db.execute(q):
            found[(sid, ts)] = (oid, w, p)
    return found


class Tally:
    """Counts parsed since the last commit stay 'pending' and are folded in only after the commit succeeds."""

    def __init__(self):
        self.totals, self.invalid, self.notes = Counter(), Counter(), Counter()
        self.p_totals, self.p_invalid, self.p_notes = Counter(), Counter(), Counter()

    def commit(self, written: Counter):
        self.totals.update(self.p_totals); self.totals.update(written)
        self.invalid.update(self.p_invalid); self.notes.update(self.p_notes)
        self.p_totals.clear(); self.p_invalid.clear(); self.p_notes.clear()


def _write_chunk(db: Session, batch: list[dict], run: ImportRun, seen_keys: set) -> Counter:
    """Write one chunk (insert new, enrich sparse existing). Returns its counts; commits."""
    out = Counter()
    existing = _existing(db, sorted({r["storm_id"] for r in batch}))
    new_rows, updates = [], []
    for r in batch:
        key = (r["storm_id"], r["timestamp"])
        if key in seen_keys:
            out["rows_duplicate"] += 1
            continue
        seen_keys.add(key)
        ex = existing.get(key)
        if ex is None:
            r["import_run_id"] = run.id
            new_rows.append(r)
            out["rows_added"] += 1
            continue
        out["rows_duplicate"] += 1
        oid, w, p = ex
        vals = {}
        if w is None and r["wind_speed_kt"] is not None:
            vals.update(wind_speed_kt=r["wind_speed_kt"], wind_source=r["wind_source"])
        if p is None and r["pressure_hpa"] is not None:
            vals.update(pressure_hpa=r["pressure_hpa"], pressure_source=r["pressure_source"])
        if vals:
            updates.append((oid, vals))
    if new_rows:
        _insert_ignore(db, new_rows)
    for oid, vals in updates:  # enrichment is rare; per-row updates keep the logic obvious
        db.execute(update(CycloneObservation).where(CycloneObservation.id == oid).values(**vals))
        out["rows_enriched"] += 1
    return out


def _save_progress(db: Session, run: ImportRun, t: Tally):
    for k in ("rows_seen", "rows_added", "rows_duplicate", "rows_enriched", "rows_invalid", "rows_skipped_spur"):
        setattr(run, k, t.totals.get(k, 0))
    run.invalid_reasons_json = json.dumps({"invalid_rows": dict(t.invalid.most_common(MAX_REASON_KEYS)),
                                           "notes": dict(t.notes)})
    run.updated_at = utcnow()
    db.add(run)
    db.commit()


def _commit_chunk(db: Session, run: ImportRun, batch: list[dict], seen_keys: set, t: Tally):
    written = _write_chunk(db, batch, run, seen_keys) if batch else Counter()
    db.flush()
    t.commit(written)
    _save_progress(db, run, t)  # commits the chunk and the run counters atomically


def run_import(db: Session, run: ImportRun, path: str, chunk_rows: int = 5000) -> ImportRun:
    """Execute the import for an existing ImportRun row. Never raises: failures are recorded on the run."""
    t, seen_keys, batch = Tally(), set(), []
    try:
        header = validate_header(path)
        idx = {name: i for i, name in enumerate(header) if name in REQUIRED + OPTIONAL}
        width = len(header)
        with _open(path) as fh:
            reader = csv.reader(fh)
            next(reader)  # header
            first = True
            for row in reader:
                if first:
                    first = False
                    # IBTrACS has a units row directly under the header ("degrees_north" under LAT). Only skip it
                    # when it really is a units row, so files without one lose no data.
                    if len(row) == width and row[idx["LAT"]].strip().lower().startswith("degrees"):
                        continue
                if not row:
                    continue
                t.p_totals["rows_seen"] += 1
                if len(row) != width:
                    t.p_invalid["malformed_row_wrong_column_count"] += 1
                    t.p_totals["rows_invalid"] += 1
                    continue
                rec, reason = parse_row(row, idx)
                if rec is None:
                    if reason == "spur_track":
                        t.p_totals["rows_skipped_spur"] += 1
                    else:
                        t.p_invalid[reason] += 1
                        t.p_totals["rows_invalid"] += 1
                    continue
                if reason:  # an out-of-range wind/pressure value was ignored; the row itself is kept
                    t.p_notes[reason] += 1
                batch.append(rec)
                if len(batch) >= chunk_rows:
                    _commit_chunk(db, run, batch, seen_keys, t)
                    batch = []
        _commit_chunk(db, run, batch, seen_keys, t)
        run.status, run.error_message = "completed", None
    except ImportFileError as exc:
        db.rollback()
        run.status, run.error_message = "failed", str(exc)
    except Exception as exc:
        db.rollback()
        log.exception("IBTrACS import %s failed", run.id)
        run.status = "failed"
        run.error_message = ("Import stopped because of an internal error. Counts shown are only for chunks that were "
                             "committed; re-running the same file is safe (duplicates are skipped). "
                             f"See server logs. [{type(exc).__name__}]")
    finally:
        run.finished_at = utcnow()
        try:
            _save_progress(db, run, t)
        except Exception:
            log.exception("Could not persist final import status for run %s", run.id)
            db.rollback()
    return run
