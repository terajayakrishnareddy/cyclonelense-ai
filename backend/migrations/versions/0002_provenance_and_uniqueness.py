"""Import provenance, wind/pressure source labels, per-user predictions, unique storm/time.

Existing duplicate (storm_id, timestamp) rows (if any) are collapsed to the
oldest row before the unique index is created.

Revision ID: 0002_provenance
Revises: 0001_baseline
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_provenance"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("size_bytes", sa.BigInteger, nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("rows_seen", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rows_added", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rows_duplicate", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rows_enriched", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rows_invalid", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rows_skipped_spur", sa.Integer, nullable=False, server_default="0"),
        sa.Column("invalid_reasons_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", name="fk_import_runs_user_id"), nullable=True),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("finished_at", sa.DateTime, nullable=True),
    )

    op.execute(
        "DELETE FROM cyclone_observations WHERE id NOT IN "
        "(SELECT MIN(id) FROM cyclone_observations GROUP BY storm_id, timestamp)"
    )
    with op.batch_alter_table("cyclone_observations") as batch:
        batch.add_column(sa.Column("wind_source", sa.String(10), nullable=True))
        batch.add_column(sa.Column("pressure_source", sa.String(10), nullable=True))
        batch.add_column(sa.Column("import_run_id", sa.Integer, nullable=True))
        batch.create_foreign_key("fk_obs_import_run", "import_runs", ["import_run_id"], ["id"])
        batch.drop_index("ix_storm_time")
        batch.create_index("uq_storm_time", ["storm_id", "timestamp"], unique=True)

    with op.batch_alter_table("predictions") as batch:
        batch.add_column(sa.Column("user_id", sa.Integer, nullable=True))
        batch.create_foreign_key("fk_predictions_user_id", "users", ["user_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("predictions") as batch:
        batch.drop_constraint("fk_predictions_user_id", type_="foreignkey")
        batch.drop_column("user_id")
    with op.batch_alter_table("cyclone_observations") as batch:
        batch.drop_index("uq_storm_time")
        batch.create_index("ix_storm_time", ["storm_id", "timestamp"])
        batch.drop_constraint("fk_obs_import_run", type_="foreignkey")
        batch.drop_column("import_run_id")
        batch.drop_column("pressure_source")
        batch.drop_column("wind_source")
    op.drop_table("import_runs")
