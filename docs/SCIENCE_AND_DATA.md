# Data provenance and scientific safeguards

## Historical best-track (implemented)
NOAA NCEI IBTrACS v04r01 is the reference dataset. The importer reads the official CSV and keeps, per observation: storm ID (`SID`), name, basin, time (UTC), latitude, longitude, wind (kt), pressure (hPa), source label `NOAA_IBTRACS_v04r01`, and the id of the import run that created it. Each import run records file name, size, SHA-256, status and row counts (`GET /api/data/imports`).

**Wind/pressure rules.** The WMO-agency column (`WMO_WIND`, `WMO_PRES`) is used when it holds a plausible value; otherwise the USA-agency column (`USA_WIND`, `USA_PRES`) is used and the observation is labelled `USA` in `wind_source`/`pressure_source`. This matters: for recent provisional storms `WMO_WIND` is often blank. Agencies use different averaging periods (e.g. 1-minute vs 10-minute sustained wind), so wind values are **not strictly comparable across basins/agencies**. Plausibility limits: wind 0–300 kt, pressure 800–1100 hPa; values outside are ignored (counted in import notes), not stored.

**Rows skipped.** Alternative "spur" track rows (`TRACK_TYPE` starting with `spur`) are skipped so each storm has one main track. Rows with missing storm ID, unparsable time, missing/invalid or out-of-range coordinates, or the wrong number of columns are counted as invalid with reasons. Longitudes >180 are normalised to −180…180. Times are stored as naive UTC and always served with a `Z` suffix.

**Idempotency.** `(storm_id, timestamp)` is unique. Re-importing skips duplicates; an existing row missing wind/pressure is filled from the file, never overwritten.

Always inspect the CSV header and cite IBTrACS per NOAA's guidance. The schema can change between versions.

## Satellite data (not implemented)
No satellite or live weather provider is connected. A future pipeline must document exact product IDs, calibration/quality flags, temporal matching window and preprocessing (e.g. NOAA GOES, NASA Earthdata). The *Image intake* feature only validates file type/size; it does not store or analyse images.

## Models (not implemented)
No trained model artifact exists, so none is claimed. The model registry is empty until a real artifact with a reproducible, storm-separated evaluation is registered. See `ml/training/README.md`.

## The track baseline
Constant-motion great-circle extrapolation from a start point, direction and speed. It ignores steering flow, storm physics, land interaction and uncertainty. It is **not** a forecast, not ML, and must never be used for warnings, evacuation, navigation or other safety decisions. Every API response and UI view that shows it says so, and projections are drawn dashed and amber, distinct from observed tracks.
