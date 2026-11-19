"""Server-side administration.

    python -m app.cli create-admin --email you@example.org      (prompts for a password, or set ADMIN_PASSWORD)
"""
import argparse
import getpass
import os
import sys

from sqlalchemy import func

from .database import SessionLocal
from .db_migrations import run_migrations
from .models import User
from .schemas import RegisterRequest
from .security import hash_password


def create_admin(email: str, password: str) -> str:
    RegisterRequest(email=email, password=password)  # same validation as public registration
    run_migrations()
    with SessionLocal() as db:
        user = db.query(User).filter(func.lower(User.email) == email.lower()).first()
        if user:
            user.role, user.is_active, user.hashed_password = "admin", True, hash_password(password)
            action = "updated (promoted to admin, password reset)"
        else:
            db.add(User(email=email.lower(), hashed_password=hash_password(password), role="admin"))
            action = "created"
        db.commit()
    return action


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    ca = sub.add_parser("create-admin", help="Create an administrator (or promote an existing user)")
    ca.add_argument("--email", required=True)
    args = parser.parse_args(argv)
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Admin password (min 10 chars): ")
    try:
        print(f"Admin {args.email} {create_admin(args.email, password)}.")
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
