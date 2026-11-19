import os
import tempfile
from pathlib import Path

# Configure BEFORE the app is imported. Tests never touch a developer's real database.
_TMP = tempfile.mkdtemp(prefix="cyclonelens-tests-")
os.environ.update(ENVIRONMENT="test", DATABASE_URL=os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_TMP}/test.db", SECRET_KEY="test-only-key-" + "x7Qp9" * 8,
                  UPLOAD_DIR=f"{_TMP}/uploads", LOG_LEVEL="WARNING", ALLOW_REGISTRATION="true",
                  MAX_IMPORT_MB="500", MAX_IMAGE_MB="20", LOGIN_MAX_FAILURES="5")

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import CycloneObservation, ImportRun, ModelRun, Prediction, User
from app.security import login_throttle, hash_password

FIXTURES = Path(__file__).parent / "fixtures"
PASSWORD = "correct-horse-battery"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:  # runs the lifespan => applies Alembic migrations
        yield c


@pytest.fixture(autouse=True)
def clean_db(client):
    yield
    with SessionLocal() as db:
        for model in (Prediction, ModelRun, CycloneObservation, ImportRun, User):
            db.query(model).delete()
        db.commit()
    login_throttle.reset()
    settings.allow_registration = True
    settings.max_import_mb = 500
    settings.import_chunk_rows = 5000


def _make_user(email: str, role: str) -> dict:
    with SessionLocal() as db:
        db.add(User(email=email, hashed_password=hash_password(PASSWORD), role=role))
        db.commit()
    return {"email": email, "password": PASSWORD}


def _headers(client, creds) -> dict:
    r = client.post("/api/auth/login", json=creds)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def user_headers(client):
    return _headers(client, _make_user("researcher@example.org", "researcher"))


@pytest.fixture
def other_user_headers(client):
    return _headers(client, _make_user("other@example.org", "researcher"))


@pytest.fixture
def admin_headers(client):
    return _headers(client, _make_user("admin@example.org", "admin"))


HEADER = "SID,SEASON,NUMBER,BASIN,SUBBASIN,NAME,ISO_TIME,NATURE,LAT,LON,WMO_WIND,WMO_PRES,USA_WIND,USA_PRES,TRACK_TYPE"
UNITS = " ,Year, , , , , , ,degrees_north,degrees_east,kts,mb,kts,mb, "


def make_csv(rows, units=True, header=HEADER) -> bytes:
    """rows: list of dicts with keys sid,basin,name,time,lat,lon,wmo_wind,wmo_pres,usa_wind,usa_pres,track."""
    lines = [header]
    if units:
        lines.append(UNITS)
    for r in rows:
        if isinstance(r, str):
            lines.append(r)
            continue
        lines.append(",".join(str(r.get(k, "")) for k in
                              ("sid", "season", "number", "basin", "sub", "name", "time", "nature", "lat", "lon",
                               "wmo_wind", "wmo_pres", "usa_wind", "usa_pres", "track")))
    return ("\n".join(lines) + "\n").encode()


def row(sid="2020001N10080", name="TESTONE", time="2020-01-01 00:00:00", lat=10.0, lon=80.0, basin="NI", **kw):
    return {"sid": sid, "season": 2020, "number": 1, "basin": basin, "sub": "BB", "name": name, "time": time,
            "nature": "TS", "lat": lat, "lon": lon, "track": "main", **kw}


def upload(client, headers, content: bytes, name="ibtracs.csv"):
    return client.post("/api/data/import-ibtracs", headers=headers, files={"file": (name, content, "text/csv")})
