import hashlib

import pytest

from app.database import SessionLocal
from app.models import CycloneObservation, ImportRun
from app.services import ibtracs
from conftest import FIXTURES, make_csv, row, upload, HEADER


def run_of(client, resp):
    assert resp.status_code == 202, resp.text
    r = client.get(f"/api/data/imports/{resp.json()['id']}")  # background task already finished in TestClient
    assert r.status_code == 200
    return r.json()


def accounted(r):
    return r["rows_added"] + r["rows_duplicate"] + r["rows_invalid"] + r["rows_skipped_spur"]


def test_import_real_ibtracs_sample(client, admin_headers):
    content = (FIXTURES / "ibtracs_sample.csv").read_bytes()
    r = run_of(client, upload(client, admin_headers, content, "ibtracs_sample.csv"))
    assert r["status"] == "completed" and r["error"] is None
    assert r["rows_seen"] == 139 == accounted(r) and r["rows_added"] == 139
    assert r["sha256"] == hashlib.sha256(content).hexdigest() and r["size_bytes"] == len(content)
    assert r["source"] == "NOAA_IBTRACS_v04r01" and r["filename"] == "ibtracs_sample.csv"
    storms = client.get("/api/storms").json()
    assert storms["total"] == 3
    obs = client.get("/api/cyclones?limit=5").json()
    # WMO_WIND is blank for these provisional storms -> USA fallback, labelled as such, never silently WMO
    assert all(o["wind_speed_kt"] is not None and o["wind_source"] == "USA" and o["source"] == "NOAA_IBTRACS_v04r01" for o in obs)
    assert obs[0]["timestamp"].endswith("Z")


def test_reimport_is_idempotent(client, admin_headers):
    content = make_csv([row(time=f"2020-01-01 {h:02d}:00:00", lat=10 + h / 10, wmo_wind=30 + h) for h in range(0, 24, 6)])
    first = run_of(client, upload(client, admin_headers, content))
    second = run_of(client, upload(client, admin_headers, content))
    assert (first["rows_added"], first["rows_duplicate"]) == (4, 0)
    assert (second["rows_added"], second["rows_duplicate"], second["rows_enriched"]) == (0, 4, 0)
    assert second["status"] == "completed" and second["rows_seen"] == 4
    with SessionLocal() as db:
        assert db.query(CycloneObservation).count() == 4


def test_duplicates_within_one_file_counted(client, admin_headers):
    r = run_of(client, upload(client, admin_headers, make_csv([row(), row(lat=11)])))
    assert (r["rows_added"], r["rows_duplicate"]) == (1, 1) and accounted(r) == r["rows_seen"] == 2


def test_wmo_preferred_over_usa_and_usa_used_as_fallback(client, admin_headers):
    csv = make_csv([row(time="2020-01-01 00:00:00", wmo_wind=50, wmo_pres=990, usa_wind=60, usa_pres=985),
                    row(time="2020-01-01 06:00:00", usa_wind=45, usa_pres=1000),
                    row(time="2020-01-01 12:00:00")])
    run_of(client, upload(client, admin_headers, csv))
    pts = client.get("/api/cyclones/2020001N10080/track").json()["points"]
    assert (pts[0]["wind_speed_kt"], pts[0]["wind_source"], pts[0]["pressure_hpa"], pts[0]["pressure_source"]) == (50, "WMO", 990, "WMO")
    assert (pts[1]["wind_speed_kt"], pts[1]["wind_source"]) == (45, "USA")
    assert pts[2]["wind_speed_kt"] is None and pts[2]["wind_source"] is None


def test_reimport_enriches_missing_values_only(client, admin_headers):
    run_of(client, upload(client, admin_headers, make_csv([row(), row(time="2020-01-01 06:00:00", wmo_wind=40)])))
    r = run_of(client, upload(client, admin_headers, make_csv([row(usa_wind=35), row(time="2020-01-01 06:00:00", usa_wind=99)])))
    assert r["rows_enriched"] == 1 and r["rows_added"] == 0
    pts = client.get("/api/cyclones/2020001N10080/track").json()["points"]
    assert pts[0]["wind_speed_kt"] == 35 and pts[1]["wind_speed_kt"] == 40  # existing value never overwritten


def test_malformed_rows_reported_not_fatal(client, admin_headers):
    rows = [row(),                                              # good
            row(time="2020-01-01 06:00:00", lat="abc"),         # bad coordinates
            row(time="2020-01-01 12:00:00", lat=95),            # out of range
            row(time="not-a-time"),                             # bad time
            row(sid=" ", time="2020-01-02 00:00:00"),           # missing storm id
            "2020001N10080,too,few,columns",                    # wrong column count
            row(time="2020-01-03 00:00:00", track="spur-sa"),   # spur track: deliberately skipped
            row(time="2020-01-04 00:00:00", lon=190),           # lon > 180 normalised
            row(time="2020-01-05 00:00:00", wmo_wind=9999, usa_wind=40)]   # absurd WMO value ignored -> USA
    r = run_of(client, upload(client, admin_headers, make_csv(rows)))
    assert r["status"] == "completed" and r["rows_seen"] == 9 == accounted(r)
    assert (r["rows_added"], r["rows_invalid"], r["rows_skipped_spur"]) == (3, 5, 1)
    assert r["invalid_reasons"] == {"invalid_coordinates": 1, "coordinates_out_of_range": 1, "invalid_time": 1,
                                    "missing_or_invalid_storm_id": 1, "malformed_row_wrong_column_count": 1}
    assert r["notes"] == {"out_of_range_value_ignored": 1}
    pts = {p["timestamp"]: p for p in client.get("/api/cyclones/2020001N10080/track").json()["points"]}
    assert pts["2020-01-04T00:00:00Z"]["longitude"] == -170
    assert pts["2020-01-05T00:00:00Z"]["wind_speed_kt"] == 40


def test_units_row_skipped_but_file_without_units_row_keeps_first_row(client, admin_headers):
    with_units = run_of(client, upload(client, admin_headers, make_csv([row()], units=True)))
    assert with_units["rows_seen"] == 1 and with_units["rows_invalid"] == 0
    without = run_of(client, upload(client, admin_headers, make_csv([row(sid="2021001N10080", time="2021-01-01 00:00:00")], units=False)))
    assert without["rows_seen"] == 1 and without["rows_added"] == 1


@pytest.mark.parametrize("name,content,fragment", [
    ("data.txt", b"x", ".csv"),
    ("empty.csv", b"", "empty"),
    ("bin.csv", b"SID,NAME\x00\x01\x02", "binary"),
    ("cols.csv", b"A,B,C\n1,2,3\n", "required column"),
    ("partial.csv", (HEADER.replace("LAT,", "") + "\n").encode(), "LAT"),
])
def test_invalid_files_rejected_with_clear_400(client, admin_headers, name, content, fragment):
    r = upload(client, admin_headers, content, name)
    assert r.status_code == 400 and fragment in r.json()["detail"]
    with SessionLocal() as db:
        assert db.query(ImportRun).count() == 0  # nothing queued, nothing recorded as success


def test_header_only_file_completes_with_zero_rows(client, admin_headers):
    r = run_of(client, upload(client, admin_headers, make_csv([])))
    assert r["status"] == "completed" and r["rows_seen"] == 0 and r["rows_added"] == 0


def test_oversized_upload_rejected(client, admin_headers):
    from app.config import settings
    settings.max_import_mb = 1
    big = make_csv([row()]) + b"#" * (1024 * 1024 + 10)
    assert upload(client, admin_headers, big).status_code == 413
    huge = client.post("/api/data/import-ibtracs", headers={**admin_headers, "Content-Length": str(50 * 1024 * 1024)},
                       files={"file": ("a.csv", b"x", "text/csv")})
    assert huge.status_code == 413


def test_upload_never_left_on_disk(client, admin_headers, tmp_path):
    from app.config import settings
    run_of(client, upload(client, admin_headers, make_csv([row()])))
    upload_tmp = settings.upload_dir + "/tmp"
    import os
    assert not os.path.isdir(upload_tmp) or os.listdir(upload_tmp) == []


def test_concurrent_import_blocked_and_stale_run_recovered(client, admin_headers):
    from app.timeutil import utcnow
    from datetime import timedelta
    with SessionLocal() as db:
        db.add(ImportRun(source="x", filename="running.csv", status="running"))
        db.commit()
    assert upload(client, admin_headers, make_csv([row()])).status_code == 409
    with SessionLocal() as db:
        run = db.query(ImportRun).one()
        run.updated_at = utcnow() - timedelta(hours=1)
        db.commit()
    r = run_of(client, upload(client, admin_headers, make_csv([row()])))
    assert r["status"] == "completed"
    with SessionLocal() as db:
        stale = db.query(ImportRun).filter(ImportRun.filename == "running.csv").one()
        assert stale.status == "failed" and "interrupted" in stale.error_message


def test_partial_failure_reports_only_committed_rows(client, admin_headers, monkeypatch):
    from app.config import settings
    settings.import_chunk_rows = 2
    calls = {"n": 0}
    real = ibtracs._insert_ignore

    def flaky(db, rows):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("disk exploded: secret-internal-detail")
        return real(db, rows)

    monkeypatch.setattr(ibtracs, "_insert_ignore", flaky)
    content = make_csv([row(time=f"2020-01-01 {h:02d}:00:00") for h in range(0, 10)])
    r = run_of(client, upload(client, admin_headers, content))
    assert r["status"] == "failed"
    assert "secret-internal-detail" not in str(r) and "RuntimeError" in r["error"]  # type only, no internals
    with SessionLocal() as db:
        stored = db.query(CycloneObservation).count()
    assert stored == r["rows_added"] == 2 and r["rows_seen"] == 2  # only the committed chunk is reported
    # Re-running the same file after the fault resumes safely
    monkeypatch.setattr(ibtracs, "_insert_ignore", real)
    again = run_of(client, upload(client, admin_headers, content))
    assert again["status"] == "completed" and again["rows_added"] == 8 and again["rows_duplicate"] == 2


def test_import_history_lists_runs_newest_first(client, admin_headers):
    run_of(client, upload(client, admin_headers, make_csv([row()]), "one.csv"))
    run_of(client, upload(client, admin_headers, make_csv([row()]), "two.csv"))
    names = [r["filename"] for r in client.get("/api/data/imports").json()]
    assert names == ["two.csv", "one.csv"]
    assert client.get("/api/data/imports/9999").status_code == 404
