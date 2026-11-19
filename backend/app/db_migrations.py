"""Programmatic access to Alembic: run migrations and report schema status."""
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from .database import engine

_BACKEND_DIR = Path(__file__).resolve().parents[1]


def _config() -> Config:
    return Config(str(_BACKEND_DIR / "alembic.ini"))


def run_migrations() -> None:
    command.upgrade(_config(), "head")


def schema_status() -> tuple[str | None, str]:
    """(current revision in the database, head revision shipped with this code)."""
    head = ScriptDirectory.from_config(_config()).get_current_head()
    with engine.connect() as conn:
        current = MigrationContext.configure(conn).get_current_revision()
    return current, head
