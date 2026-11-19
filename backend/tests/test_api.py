import io

import pytest

from app.database import SessionLocal
from app.models import ModelRun
from conftest import make_csv, row, upload

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def load(client, admin_headers):
    rows = [row(sid="2020001N10080", name="ALPHA", basin="NI", time=f"2020-05-0{d} 00:00:00", lat=10 + d, lon=80 + d,
                wmo_wind=30 + 10 * d, wmo_pres=1000 - 5 * d) for d in range(1, 5)]
    rows += [row(sid="2021010N15130", name="BRAVO", basin="WP", time=f"2021-09-0{d} 12:00:00", lat=15, lon=130 + d, wmo_wind=100)
             for d in range(1, 3)]
    rows += [row(sid="2022020S12060", name="CHARLIE", basin="SI", time="2022-02-01 06:00:00", lat=-12, lon=60)]
    assert upload(client, admin_headers, make_csv(rows)).status_code == 202


def test_health_is_liveness_and_ready_checks_database(client):
    h = client.get("/api/health")
    assert h.status_code == 200 and h.json()["status"] == "ok"
    r = client.get("/api/ready")
    assert r.status_code == 200 and r.json()["status"] == "ready" and r.json()["database"] == "ok"


def test_ready_503_when_database_down_without_leaking_details(client, monkeypatch):
    import app.routers.system as system

    def boom():
        raise RuntimeError("password=hunter2 host=db.internal")

    monkeypatch.setattr(system, "check_connection", boom)
    r = client.get("/api/ready")
    assert r.status_code == 503 and r.json()["status"] == "not_ready" and "hunter2" not in r.text
    assert client.get("/api/health").status_code == 200  # liveness unaffected


def test_ready_503_when_schema_outdated(client, monkeypatch):
    import app.routers.system as system
    monkeypatch.setattr(system, "schema_status", lambda: ("0001_baseline", "0002_provenance"))
    r = client.get("/api/ready")
    assert r.status_code == 503 and r.json()["schema"] == "outdated"


def test_empty_database_endpoints_are_empty_not_fabricated(client):
    assert client.get("/api/cyclones").json() == []
    assert client.get("/api/storms").json() == {"total": 0, "limit": 50, "offset": 0, "items": []}
    ov = client.get("/api/analytics/overview").json()
    assert ov["observations"] == 0 and ov["storms"] == 0 and ov["demo_records"] == 0 and ov["first_observation"] is None
    assert client.get("/api/analytics/by-basin").json() == [] and client.get("/api/analytics/yearly").json() == []
    assert client.get("/api/ml/models").json() == []


def test_storms_list_filters_and_pagination(client, admin_headers):
    load(client, admin_headers)
    s = client.get("/api/storms").json()
    assert s["total"] == 3 and [x["name"] for x in s["items"]] == ["CHARLIE", "BRAVO", "ALPHA"]  # newest first
    alpha = next(x for x in s["items"] if x["name"] == "ALPHA")
    assert alpha["observations"] == 4 and alpha["max_wind_kt"] == 70 and alpha["min_pressure_hpa"] == 980
    assert alpha["start_time"] == "2020-05-01T00:00:00Z" and alpha["end_time"] == "2020-05-04T00:00:00Z"
    assert [x["name"] for x in client.get("/api/storms?basin=wp").json()["items"]] == ["BRAVO"]
    assert [x["name"] for x in client.get("/api/storms?search=alp").json()["items"]] == ["ALPHA"]
    assert [x["name"] for x in client.get("/api/storms?search=2021010N").json()["items"]] == ["BRAVO"]
    big = client.get("/api/storms?min_wind=90").json()
    assert big["total"] == 1 and big["items"][0]["name"] == "BRAVO"
    page = client.get("/api/storms?limit=2&offset=2").json()
    assert page["total"] == 3 and [x["name"] for x in page["items"]] == ["ALPHA"]
    assert client.get("/api/storms?limit=0").status_code == 422 and client.get("/api/storms?min_wind=-1").status_code == 422


def test_observations_filters(client, admin_headers):
    load(client, admin_headers)
    assert len(client.get("/api/cyclones").json()) == 7
    assert len(client.get("/api/cyclones?basin=NI").json()) == 4
    assert len(client.get("/api/cyclones?basin=All").json()) == 7
    assert len(client.get("/api/cyclones?min_wind=100").json()) == 2
    assert len(client.get("/api/cyclones?limit=3").json()) == 3
    assert client.get("/api/cyclones?limit=0").status_code == 422 and client.get("/api/cyclones?limit=10001").status_code == 422


def test_track_endpoint_is_labelled_observed(client, admin_headers):
    load(client, admin_headers)
    t = client.get("/api/cyclones/2020001N10080/track").json()
    assert t["kind"] == "observed_best_track" and t["source"] == "NOAA_IBTRACS_v04r01" and len(t["points"]) == 4
    assert [p["timestamp"] for p in t["points"]] == sorted(p["timestamp"] for p in t["points"])
    assert client.get("/api/cyclones/NOPE/track").status_code == 404


def test_analytics_match_loaded_data(client, admin_headers):
    load(client, admin_headers)
    ov = client.get("/api/analytics/overview").json()
    assert (ov["observations"], ov["storms"], ov["basins"], ov["source_records"], ov["demo_records"]) == (7, 3, 3, 7, 0)
    assert ov["observations_with_wind"] == 6 and ov["first_observation"] == "2020-05-01T00:00:00Z"
    assert ov["last_import"]["filename"] == "ibtracs.csv"
    assert client.get("/api/analytics/by-basin").json()[0] == {"basin": "NI", "count": 4}
    assert client.get("/api/analytics/yearly").json() == [
        {"year": "2020", "observations": 4}, {"year": "2021", "observations": 2}, {"year": "2022", "observations": 1}]


def test_track_baseline_is_labelled_and_deterministic(client, user_headers):
    body = {"latitude": 10, "longitude": 80, "direction_degrees": 90, "speed_kmh": 20, "hours": 24}
    r = client.post("/api/ml/predict-track", json=body, headers=user_headers)
    assert r.status_code == 200
    d = r.json()
    assert d["model_status"] == "NOT_TRAINED" and d["observed"] is False and d["kind"] == "baseline_projection"
    assert "Not an official forecast" in d["warning"] and "safety" in d["warning"]
    assert [p["hours_ahead"] for p in d["points"]] == [6, 12, 18, 24]
    assert d["endpoint"] == {"latitude": d["points"][-1]["latitude"], "longitude": d["points"][-1]["longitude"]}
    assert d["endpoint"]["longitude"] == pytest.approx(80 + 480 / 111.19 / 0.9848, abs=0.1) and abs(d["endpoint"]["latitude"] - 10) < 0.1
    assert client.post("/api/ml/predict-track", json=body, headers=user_headers).json()["endpoint"] == d["endpoint"]


def test_track_baseline_dateline_wraps(client, user_headers):
    r = client.post("/api/ml/predict-track", json={"latitude": 0, "longitude": 179.5, "direction_degrees": 90, "speed_kmh": 100, "hours": 2},
                    headers=user_headers).json()
    assert -180 <= r["endpoint"]["longitude"] < -170


@pytest.mark.parametrize("bad", [{"latitude": 91, "longitude": 0}, {"latitude": 0, "longitude": 181},
                                 {"latitude": 0, "longitude": 0, "hours": 0}, {"latitude": 0, "longitude": 0, "hours": 500},
                                 {"latitude": 0, "longitude": 0, "speed_kmh": -1}, {"latitude": 0, "longitude": 0, "direction_degrees": 360},
                                 {"latitude": "x", "longitude": 0}, {}])
def test_track_baseline_validation(client, user_headers, bad):
    assert client.post("/api/ml/predict-track", json=bad, headers=user_headers).status_code == 422


def test_prediction_history_scoped_to_user(client, user_headers, other_user_headers, admin_headers):
    body = {"latitude": 5, "longitude": 5}
    client.post("/api/ml/predict-track", json=body, headers=user_headers)
    client.post("/api/ml/predict-track", json=body, headers=user_headers)
    client.post("/api/ml/predict-track", json=body, headers=other_user_headers)
    mine = client.get("/api/predictions", headers=user_headers).json()
    assert len(mine) == 2 and mine[0]["is_baseline"] and mine[0]["input"]["latitude"] == 5 and mine[0]["created_at"].endswith("Z")
    assert len(client.get("/api/predictions", headers=other_user_headers).json()) == 1
    assert len(client.get("/api/predictions", headers=admin_headers).json()) == 3


def test_model_registry_lists_only_registered_models_and_capabilities_are_honest(client):
    assert client.get("/api/ml/models").json() == []
    with SessionLocal() as db:
        db.add(ModelRun(model_name="m", model_version="1", task="t", status="UNTRAINED", metrics_json='{"a": 1}'))
        db.commit()
    m = client.get("/api/ml/models").json()
    assert m[0]["status"] == "UNTRAINED" and m[0]["metrics"] == {"a": 1}
    caps = client.get("/api/ml/capabilities").json()
    assert caps["image_classification"]["status"] == "not_configured" and caps["track_baseline"]["status"] == "available"
    assert "Not machine learning" in caps["track_baseline"]["description"]


def img(client, headers, data, name="storm.png", ctype="image/png"):
    return client.post("/api/ml/analyze-image", headers=headers, files={"file": (name, io.BytesIO(data), ctype)})


def test_image_intake_does_not_claim_analysis(client, user_headers):
    r = img(client, user_headers, PNG)
    d = r.json()
    assert r.status_code == 200 and d["analyzed"] is False and d["stored"] is False and d["status"] == "ACCEPTED_NOT_ANALYZED"
    assert d["bytes_received"] == len(PNG) and d["detected_type"] == "image/png" and len(d["sha256"]) == 64
    assert "classification" in d["message"] and "label" not in d and "prediction" not in d
    assert img(client, user_headers, b"\xff\xd8\xff\xe0" + b"0" * 20, "a.jpg", "image/jpeg").json()["detected_type"] == "image/jpeg"
    assert img(client, user_headers, b"II*\x00" + b"0" * 20, "a.tif", "image/tiff").json()["detected_type"] == "image/tiff"


def test_image_intake_checks_content_not_declared_type(client, user_headers):
    assert img(client, user_headers, b"<html>not an image</html>", "evil.png", "image/png").status_code == 415
    assert img(client, user_headers, b"", "empty.png").status_code == 415


def test_image_intake_size_limit(client, user_headers):
    from app.config import settings
    settings.max_image_mb = 1
    try:
        assert img(client, user_headers, PNG + b"0" * (1024 * 1024)).status_code == 413
    finally:
        settings.max_image_mb = 20


def test_unhandled_errors_are_generic_and_logged(client):
    from app.main import app
    ok = {"path": "/api/_boom_test"}

    @app.get(ok["path"], include_in_schema=False)
    def boom():
        raise RuntimeError("secret stack detail /etc/passwd")

    from fastapi.testclient import TestClient
    r = TestClient(app, raise_server_exceptions=False).get(ok["path"])
    assert r.status_code == 500 and r.json()["detail"] == "Internal server error" and "passwd" not in r.text
    assert r.json()["request_id"] == r.headers["X-Request-ID"]


def test_cors_allows_only_configured_origin(client):
    ok = client.options("/api/health", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = client.options("/api/health", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers
