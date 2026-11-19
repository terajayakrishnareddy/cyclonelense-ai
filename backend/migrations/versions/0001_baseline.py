"""Baseline schema (the original create_all() schema).

Idempotent on purpose: databases created by earlier builds via
Base.metadata.create_all() already contain these tables and are adopted as-is
(no data is touched); fresh databases get them created.

Revision ID: 0001_baseline
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())

    if not insp.has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("hashed_password", sa.String(255), nullable=False),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("is_active", sa.Boolean, nullable=False),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    if not insp.has_table("cyclone_observations"):
        op.create_table(
            "cyclone_observations",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("storm_id", sa.String(80), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("basin", sa.String(40), nullable=False),
            sa.Column("timestamp", sa.DateTime, nullable=False),
            sa.Column("latitude", sa.Float, nullable=False),
            sa.Column("longitude", sa.Float, nullable=False),
            sa.Column("wind_speed_kt", sa.Float, nullable=True),
            sa.Column("pressure_hpa", sa.Float, nullable=True),
            sa.Column("status", sa.String(40), nullable=False),
            sa.Column("source", sa.String(80), nullable=False),
            sa.Column("is_demo", sa.Boolean, nullable=False),
        )
        op.create_index("ix_cyclone_observations_id", "cyclone_observations", ["id"])
        op.create_index("ix_cyclone_observations_storm_id", "cyclone_observations", ["storm_id"])
        op.create_index("ix_cyclone_observations_name", "cyclone_observations", ["name"])
        op.create_index("ix_cyclone_observations_basin", "cyclone_observations", ["basin"])
        op.create_index("ix_cyclone_observations_timestamp", "cyclone_observations", ["timestamp"])
        op.create_index("ix_storm_time", "cyclone_observations", ["storm_id", "timestamp"])

    if not insp.has_table("model_runs"):
        op.create_table(
            "model_runs",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("model_name", sa.String(120), nullable=False),
            sa.Column("model_version", sa.String(80), nullable=False),
            sa.Column("task", sa.String(80), nullable=False),
            sa.Column("status", sa.String(40), nullable=False),
            sa.Column("metrics_json", sa.Text, nullable=False),
            sa.Column("artifact_path", sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )

    if not insp.has_table("predictions"):
        op.create_table(
            "predictions",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("model_run_id", sa.Integer, sa.ForeignKey("model_runs.id"), nullable=True),
            sa.Column("task", sa.String(80), nullable=False),
            sa.Column("input_summary", sa.Text, nullable=False),
            sa.Column("output_json", sa.Text, nullable=False),
            sa.Column("is_baseline", sa.Boolean, nullable=False),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )


def downgrade() -> None:
    raise NotImplementedError("The baseline migration is not reversible; restore from a backup instead.")
