"""Container start-up: validate config, wait for the database, apply migrations.

Run as ``python -m app.startup`` before the server. Exits non-zero with a clear message on
unsafe configuration or an unreachable database, so the container fails visibly instead of limping.
"""
import os
import sys
import time


def main() -> int:
    try:
        from .config import settings
    except Exception as exc:  # pydantic ValidationError with our readable list of problems
        lines = [ln for ln in str(exc).splitlines() if ln.startswith(" - ")] or [str(exc)]
        print("FATAL: unsafe or invalid configuration:\n" + "\n".join(lines), file=sys.stderr)
        return 2
    from .database import check_connection
    deadline = time.monotonic() + int(os.environ.get("DB_WAIT_SECONDS", "60"))
    while True:
        try:
            check_connection()
            break
        except Exception as exc:
            if time.monotonic() > deadline:
                print(f"FATAL: database not reachable ({type(exc).__name__}). Check DATABASE_URL and that the database is running.", file=sys.stderr)
                return 3
            print("Waiting for database...", flush=True)
            time.sleep(2)
    if os.environ.get("RUN_MIGRATIONS", "true").lower() == "true":
        from .db_migrations import run_migrations
        print(f"Applying migrations ({settings.environment})...", flush=True)
        run_migrations()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
