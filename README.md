# CycloneLens AI — tropical cyclone research platform

React/Vite dashboard (Leaflet, Recharts) + FastAPI + SQLAlchemy/Alembic + SQLite (dev) / PostgreSQL (production), with NOAA IBTrACS historical best-track import.

> **Research use only.** This is a historical-data exploration platform. It is **not** an operational forecast, watch or warning system and must not be used for public warnings, evacuation, navigation or any safety decision.

## What works (and what does not)

| Works | Not implemented (not claimed) |
|---|---|
| Import of the official IBTrACS v04r01 CSV (background job, exact counts, idempotent, provenance) | Trained ML models (none are bundled; the model registry is empty) |
| Storm explorer, observed-track map, basin/yearly analytics | Image classification (the image page only validates PNG/JPEG/TIFF; nothing is analysed or stored) |
| Registration/login (bcrypt + JWT), admin role, per-user baseline history | Live satellite / weather feeds (all data is historical) |
| Constant-motion baseline projection, always labelled "not a forecast" | Official forecasts, uncertainty calibration |
| Alembic migrations, readiness check, production config validation, Docker/nginx deployment | Rate limiting beyond a per-process login throttle, email verification, password reset |

## Repository layout
`backend/` FastAPI app (`app/`), Alembic migrations (`migrations/`), tests (`tests/`) · `frontend/` React app, nginx config (`deploy/`) · `scripts/` env generator, backup, IBTrACS downloader · `docs/` science & data notes · `docker-compose.yml` production stack.

## Prerequisites
Python 3.11+ (tested 3.13), Node.js 20+ (tested 22), and for deployment Docker with Compose v2.

## Local development (no Docker, SQLite)
```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
cp .env.example .env                                       # optional; SECRET_KEY empty => random per-process key
uvicorn app.main:app --reload                              # migrates the SQLite DB automatically on start
python -m app.cli create-admin --email you@example.org     # prompts for a password (min 10 chars); needed to import data

# frontend (second terminal)
cd frontend
cp .env.example .env
npm ci
npm run dev                                                # http://localhost:5173, /api is proxied to http://127.0.0.1:8000
```
API docs: http://127.0.0.1:8000/api/docs. Windows shortcut: `start_windows.bat`.

An existing `cyclonelens.db` from an earlier build is upgraded in place by the migrations (no data is deleted; duplicate storm/time rows, if any, are collapsed).

## Import data
1. Download `ibtracs.ALL.list.v04r01.csv` from https://www.ncei.noaa.gov/products/international-best-track-archive (or `python scripts/download_ibtracs.py`, which prints the SHA-256). Keep the original and the retrieval date in your research log.
2. Sign in as an admin → **Data ingestion** → upload. The file is streamed to disk, validated, then imported in the background in chunks; the page shows live counts. The upload is deleted afterwards; only its name, size and SHA-256 are kept.
3. API: `POST /api/data/import-ibtracs` (admin, multipart field `file`) returns `202` + a run; poll `GET /api/data/imports/{id}`. Outcome counts: rows read, added, duplicates, enriched, invalid (by reason), spur-track skipped. Re-importing is safe.

Details of how wind/pressure are chosen and what is skipped: [docs/SCIENCE_AND_DATA.md](docs/SCIENCE_AND_DATA.md).

## Environment variables
**Backend** (`backend/.env` for dev; real environment in production)

| Variable | Default | Notes |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` enables strict validation (below) |
| `DATABASE_URL` | `sqlite:///./cyclonelens.db` | `postgresql://…` is normalised to the psycopg3 driver |
| `SECRET_KEY` | *(none)* | JWT signing key. Required in production (≥32 random chars). In dev, empty ⇒ random per process |
| `CORS_ORIGINS` | localhost:5173 | Comma-separated explicit origins. Required in production; no wildcards |
| `ALLOW_REGISTRATION` | `true` | `false` disables self-registration |
| `ACCESS_TOKEN_MINUTES` | `60` | 1–1440 |
| `MAX_IMPORT_MB` / `MAX_IMAGE_MB` | `500` / `20` | Upload limits (also enforced by Content-Length and nginx) |
| `UPLOAD_DIR` | `./uploads` | Temporary upload staging only |
| `ENABLE_DOCS` | `true` | Serves `/api/docs` |
| `AUTO_MIGRATE` | dev: on, production: off | Containers run migrations in the entrypoint instead |
| `LOGIN_MAX_FAILURES`/`LOGIN_WINDOW_SECONDS` | `5` / `900` | Per-process failed-login throttle |

**Production refuses to start** (exit code 2, listing every problem) if: `SECRET_KEY` is missing/short/placeholder-like, `CORS_ORIGINS` is empty/wildcard/not http(s), `DATABASE_URL` is SQLite, or the DB password is short/placeholder-like.

Generate a secret: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

**Frontend** (`frontend/.env`, build-time, *public*): `VITE_API_URL` (empty = same-origin `/api`), `VITE_DEV_PROXY_TARGET`, `VITE_TILE_URL`.

## Tests and builds
```bash
cd backend  && pip install -r requirements-dev.txt && python -m pytest -q
cd frontend && npm ci && npm test && npm run build
# optional: run the backend suite against PostgreSQL
TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/cyclonelens_test python -m pytest -q
```

## Docker deployment (portable, no platform assumed)
```bash
python scripts/generate_env.py --origin https://cyclones.example.org   # writes .env with fresh random secrets
docker compose up -d --build                                            # db -> api (waits for DB, migrates) -> web
docker compose exec api python -m app.cli create-admin --email you@example.org
curl http://127.0.0.1:8080/api/ready                                    # {"status":"ready",...}
```
* Services: `db` (PostgreSQL 16, volume `pgdata`), `api` (non-root, healthcheck on `/api/ready`, temp uploads in volume `uploads`), `web` (nginx serving the built assets and proxying `/api`). Only `web` is published, on `127.0.0.1:8080` by default; the DB and API are on an internal network.
* **HTTPS:** put a TLS-terminating reverse proxy (Caddy, Traefik, nginx, a cloud load balancer) in front of `web`, forward to `127.0.0.1:8080`, set `X-Forwarded-Proto`, add HSTS there, and set `CORS_ORIGINS` to the public `https://` origin. Set `WEB_BIND=0.0.0.0` only if nothing else exposes the port. Raise proxy body-size/timeouts for the large CSV upload (nginx here allows 550 MB).
* **Migrations** run automatically at container start (`python -m app.startup`); to run manually: `docker compose exec api python -c "from app.db_migrations import run_migrations; run_migrations()"`.
* **Persistence & backup:** data lives in the `pgdata` volume. Back up with `./scripts/backup_db.sh` (compressed `pg_dump`); restore with `gunzip -c file.sql.gz | docker compose exec -T db psql -U cyclonelens -d cyclonelens` into an empty database. Also back up `.env`; losing `SECRET_KEY` only invalidates sessions.
* **Updating:** `git pull && docker compose up -d --build` (migrations apply on start).
* **Tiles:** the map uses public OpenStreetMap tiles by default; for real traffic use a provider you have rights to and set `VITE_TILE_URL` (build arg) and `TILE_CSP_SOURCES` (web env) accordingly.

## API summary
Public (no login): `GET /api/health` (liveness), `/api/ready` (DB + schema), `/api/cyclones`, `/api/storms`, `/api/cyclones/{storm_id}/track`, `/api/analytics/{overview,by-basin,yearly}`, `/api/data/imports[/{id}]`, `/api/ml/models`, `/api/ml/capabilities`, `POST /api/auth/{register,login,token}`.
Login required (Bearer token): `GET /api/auth/me`, `POST /api/ml/predict-track`, `POST /api/ml/analyze-image` (intake only), `GET /api/predictions` (own; admins see all).
Admin required: `POST /api/data/import-ibtracs`. Admins are created only with the server CLI.
Errors: 401 unauthenticated, 403 wrong role/registration disabled, 409 conflict, 413 too large, 415 wrong image type, 422 validation, 429 login throttle, 503 not ready. Unexpected errors return a generic 500 with a `request_id`; details go to the server log only.

## Scientific limitations
See [docs/SCIENCE_AND_DATA.md](docs/SCIENCE_AND_DATA.md) and [ml/training/README.md](ml/training/README.md). In short: historical data only; no trained models; baseline is not a forecast; images are not analysed; wind values from different agencies are not strictly comparable.

## Known limitations / owner actions
* Login throttling is in-memory per process (use proxy-level rate limiting for public sites). No password reset or email verification.
* JWTs are stored in `sessionStorage`; there is no server-side revocation other than disabling the user or rotating `SECRET_KEY`.
* The yearly/basin analytics read the full table; very large databases may want caching.
* Owner must supply: domain + TLS, `.env` secrets, an admin account, backup schedule, and a tile provider for production traffic.

## Troubleshooting
* `FATAL: unsafe or invalid configuration` at start — fix the listed variables (see above).
* `required variable … is missing a value` from `docker compose` — run `python scripts/generate_env.py`.
* `FATAL: database not reachable` — check `DATABASE_URL`/`db` health (`docker compose logs db`); special characters in the DB password must be URL-encoded (the generator avoids them).
* `/api/ready` returns 503 `schema: outdated` — migrations have not run; restart the `api` container or run them manually.
* Frontend shows "Cannot reach the API" — in dev, start the backend and check `VITE_DEV_PROXY_TARGET`; with a separate API origin, add the frontend origin to `CORS_ORIGINS`.
* Import returns 400 — the message names the missing column or file problem; 409 means another import is running (a stalled one is auto-cleared after 10 min); 413 means the file exceeds `MAX_IMPORT_MB` (and nginx `MAX_UPLOAD_MB`).
* Blank map background — tiles are fetched from the tile server; check outbound access/CSP.

## Research report: historical tropical-cyclone analysis and responsible model development

### Executive summary

CycloneLens AI is currently a research and data-exploration platform for historical tropical-cyclone best tracks. Its implemented data path imports NOAA/NCEI's International Best Track Archive for Climate Stewardship (IBTrACS) v04r01, preserves import provenance, and supports map-based track exploration and descriptive basin/year analysis. The repository also includes a transparent constant-motion geometry baseline. It does not currently contain a trained machine-learning model, live satellite feed, operational forecast, or image-analysis pipeline. The baseline is a comparison aid and must not be interpreted as forecast guidance.

IBTrACS is a suitable starting point for a global historical study because it combines best-track information from multiple agencies. That combination also creates analytical caveats: wind averaging periods differ by reporting agency, some recent data are provisional, and historical track records have known uncertainties. Consequently, research using this app should document the downloaded version and retrieval date, retain agency/source fields, define its sample carefully, and report results by basin and forecast lead time. These points follow the NOAA/NCEI dataset and technical documentation.

### Research question and scope

**Research question:** How well do simple historical track baselines describe subsequent storm motion across basins and lead times, and what additional evidence would be required before a machine-learning model could be evaluated responsibly?

This is a proposed research question, not a result produced by the current software. The implemented project can support exploration of historical positions and selected intensity fields. It cannot yet train or validate a forecast model. The near-term research scope should therefore be descriptive analysis and a reproducible evaluation design, with any future predictive experiment explicitly separated from operational warning services.

### Data and provenance

The current importer targets the IBTrACS v04r01 all-storm CSV. It records storm identifier, name, basin, UTC observation time, location, selected wind and pressure values, source labels, and import-run provenance. The importer ignores spur-track rows, validates coordinates and times, and uses a unique storm/time key to make repeat imports safe. These implementation choices aid traceability; they do not remove uncertainty inherent in best-track records.

NOAA/NCEI describes IBTrACS as a global archive that merges storm records from multiple agencies. Its documentation states that wind averaging periods vary across agencies and that no adjustment is made to make all wind values equivalent. The technical documentation also discusses provisional records, position/intensity uncertainty, and interpolation. As a result:

- Treat `wind_speed_kt` as an agency-reported value with a source label, not a perfectly uniform global measurement. Avoid comparing raw wind values across agencies without a defensible harmonization method.
- Record the retrieval date, file version, file checksum, and subset used. Recent/provisional observations may later be revised.
- Avoid treating interpolated observations as independent measurements. For temporal modeling, document the sampling interval and any resampling or filtering.
- Keep storm identity intact when building samples. The same storm must not leak between training and evaluation sets.
- Cite both the IBTrACS dataset and its foundational archive paper when publishing results (see References).

### Proposed analysis and evaluation plan

1. **Freeze the dataset.** Download one identified IBTrACS release, store its retrieval date and SHA-256, check its header and documentation, and record all filtering choices. The importer retains the file checksum and source version for each run.
2. **Audit coverage and quality.** Summarize observations and unique storms by basin, year, source, and track status. Report missingness for position, wind, and pressure; flag provisional records when the source field permits. Examine time-step irregularities before making fixed-window sequences.
3. **Define prediction targets before fitting.** For track work, specify the initial observation, forecast lead times, eligible storm phases, and how track gaps or changing storm status are handled. For intensity work, specify the chosen agency field and averaging-period policy. Do not combine incomparable source values silently.
4. **Establish simple baselines.** Compare persistence (the storm remains at its latest location) and the included constant-motion great-circle extrapolation at stated lead times. The included baseline accepts a start point, bearing, speed, and horizon; it does not infer future steering or storm physics. A future model must demonstrate a measurable improvement over appropriate baselines.
5. **Split by storm, then evaluate out of sample.** Assign complete storm IDs to train, validation, or test groups; where the research question concerns future performance, prefer a chronological holdout as an additional check. Never randomly split adjacent observations or image frames from one storm across these groups.
6. **Report interpretable metrics and uncertainty.** For track positions, report great-circle distance error in nautical miles or kilometres at each lead time, sample counts, and uncertainty intervals. Break down results by basin and relevant period. For intensity, report errors in stated units and by source/averaging-period group. Compare against the same eligible cases and lead times for every baseline. A probabilistic model also needs calibration and interval-coverage checks.
7. **Keep claims bounded.** Historical hindcasts do not establish operational skill. Operational forecasts require current inputs, prospective verification, uncertainty communication, robust handling of missing or changing data, and review by the responsible forecasting institutions.

The National Hurricane Center describes track forecast verification against final best-track positions, with position error based on great-circle distance, and publishes verification procedures and error summaries. Its forecast cone is based on historical official forecast errors. Those official products provide context for evaluation practice; CycloneLens does not reproduce or replace them.

### Current implementation versus research requirements

| Research need | Current project status |
|---|---|
| Versioned global historical best-track input | Implemented for IBTrACS v04r01 CSV import; each run records provenance and a checksum. |
| Exploratory track maps and basin/year summaries | Implemented in the web application. |
| Simple transparent track comparison | Implemented as constant-motion great-circle geometry; labeled as a non-forecast baseline. |
| Reproducible trained model and model artifact | Not implemented; no trained artifact is bundled. |
| Satellite imagery acquisition, time matching, and image analysis | Not implemented; image intake validates file type/size only. |
| Storm-separated training and independent evaluation | Recommended future requirement; not performed by this application. |
| Operational forecast, warning, or decision support | Not implemented and outside the platform's stated purpose. |

### Limitations and responsible use

Best-track data are retrospective analyses, not error-free ground truth. Source practices, observation availability, and analysis methods vary across time and agencies. NOAA/NCEI documentation identifies provisional data and uncertainty considerations, and warns that wind averaging periods vary. Historical coverage and measurement practices also change over time, so apparent trends or cross-basin differences need careful interpretation.

The constant-motion baseline ignores environmental steering, storm structure and intensity evolution, land interaction, and forecast uncertainty. It is neither a trained ML model nor an official forecast. CycloneLens is for historical research and education only. Do not use it for warnings, evacuation, navigation, or any safety decision; consult the relevant national meteorological service.

### References and research resources

1. NOAA National Centers for Environmental Information (NCEI), [International Best Track Archive for Climate Stewardship (IBTrACS)](https://www.ncei.noaa.gov/products/international-best-track-archive). Dataset landing page, documentation, version information, and recommended citation. Dataset DOI: [10.25921/82ty-9e16](https://doi.org/10.25921/82ty-9e16).
2. Gahtan, J., K. R. Knapp, C. J. Schreck III, H. J. Diamond, and J. P. Kossin (2024), [International Best Track Archive for Climate Stewardship (IBTrACS) Project, Version 4.01](https://doi.org/10.25921/82ty-9e16), NOAA NCEI. Cite the subset and access date used in any resulting work.
3. Knapp, K. R., M. C. Kruk, D. H. Levinson, H. J. Diamond, and C. J. Neumann (2010), "The International Best Track Archive for Climate Stewardship (IBTrACS): Unifying tropical cyclone best track data," *Bulletin of the American Meteorological Society*, 91, 363-376. [doi:10.1175/2009BAMS2755.1](https://doi.org/10.1175/2009BAMS2755.1).
4. NOAA/NCEI, [IBTrACS v04r01 Technical Details](https://www.ncei.noaa.gov/sites/default/files/2025-04/IBTrACS_version4r01_Technical_Details.pdf) and [v04r01 column documentation](https://www.ncei.noaa.gov/sites/default/files/2025-09/IBTrACS_v04r01_column_documentation.pdf). Consult these for variable definitions, provenance, quality caveats, and wind-period differences.
5. NOAA National Hurricane Center, [Forecast Verification](https://www.nhc.noaa.gov/verification/) and [Definition of the NHC Track Forecast Cone](https://www.nhc.noaa.gov/aboutcone.shtml). These describe official verification practice and uncertainty communication for NHC products.

For implementation-specific import rules and the model development plan, see [docs/SCIENCE_AND_DATA.md](docs/SCIENCE_AND_DATA.md) and [ml/training/README.md](ml/training/README.md).
