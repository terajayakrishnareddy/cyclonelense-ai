"""Schema evolution: fresh install, and upgrading a database created by the original build."""
import sqlalchemy as sa
from alembic import command
from sqlalchemy import create_engine, inspect, text

import app.database as database
from app.db_migrations import _config, run_migrations, schema_status


def use_engine(monkeypatch, url):
    eng = create_engine(url)
    monkeypatch.setattr(database, "engine", eng)  # migrations/env.py reads app.database.engine at run time
    import app.db_migrations as dm
    monkeypatch.setattr(dm, "engine", eng)
    return eng


def test_fresh_database_reaches_head_with_expected_schema(tmp_path, monkeypatch):
    eng = use_engine(monkeypatch, f"sqlite:///{tmp_path}/fresh.db")
    run_migrations()
    insp = inspect(eng)
    assert {"users", "cyclone_observations", "import_runs", "model_runs", "predictions"} <= set(insp.get_table_names())
    idx = {i["name"]: i for i in insp.get_indexes("cyclone_observations")}
    assert idx["uq_storm_time"]["unique"] and "ix_storm_time" not in idx
    assert {"wind_source", "pressure_source", "import_run_id"} <= {c["name"] for c in insp.get_columns("cyclone_observations")}
    current, head = schema_status()
    assert current == head


def test_models_and_migrations_agree(tmp_path, monkeypatch):
    """Alembic autogenerate must find no drift between ORM models and migrated schema."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from app.database import Base
    import app.models  # noqa: F401
    eng = use_engine(monkeypatch, f"sqlite:///{tmp_path}/drift.db")
    run_migrations()
    with eng.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], diff


def test_legacy_database_upgrades_in_place_without_data_loss(tmp_path, monkeypatch):
    eng = use_engine(monkeypatch, f"sqlite:///{tmp_path}/legacy.db")
    command.upgrade(_config(), "0001_baseline")          # == schema produced by the original create_all()
    with eng.begin() as c:
        c.execute(text("DROP TABLE alembic_version"))     # legacy DBs have no alembic bookkeeping
        for i, ts in enumerate(["2020-01-01 00:00:00", "2020-01-01 06:00:00", "2020-01-01 06:00:00"]):  # one duplicate
            c.execute(text("INSERT INTO cyclone_observations (storm_id,name,basin,timestamp,latitude,longitude,status,source,is_demo)"
                           " VALUES ('S1','N','NI',:ts,10,80,'HISTORICAL','NOAA_IBTRACS_v04r01',0)"), {"ts": ts})
        c.execute(text("INSERT INTO predictions (task,input_summary,output_json,is_baseline,created_at) VALUES ('t','{}','{}',1,'2020-01-01')"))
    run_migrations()
    with eng.connect() as c:
        assert c.execute(text("SELECT count(*) FROM cyclone_observations")).scalar() == 2   # duplicate collapsed, rest kept
        assert c.execute(text("SELECT count(*) FROM predictions")).scalar() == 1            # legacy history kept
        assert c.execute(text("SELECT user_id FROM predictions")).scalar() is None
    assert schema_status()[0] == schema_status()[1]
    run_migrations()  # re-running at head is a no-op


def test_downgrade_then_upgrade_roundtrip(tmp_path, monkeypatch):
    use_engine(monkeypatch, f"sqlite:///{tmp_path}/rt.db")
    run_migrations()
    command.downgrade(_config(), "0001_baseline")
    run_migrations()
    assert schema_status()[0] == schema_status()[1]
