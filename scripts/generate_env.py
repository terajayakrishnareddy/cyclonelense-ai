"""Create a root .env with freshly generated secrets for the Docker deployment.

    python scripts/generate_env.py --origin https://cyclones.example.org
"""
import argparse
import os
import secrets
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--origin", default="http://localhost:8080", help="public origin of the site (used for CORS)")
    ap.add_argument("--force", action="store_true", help="overwrite an existing .env")
    args = ap.parse_args()
    target = ROOT / ".env"
    if target.exists() and not args.force:
        print(f"{target} already exists; refusing to overwrite (use --force).", file=sys.stderr)
        return 1
    alphabet = string.ascii_letters + string.digits
    values = {
        "POSTGRES_DB": "cyclonelens", "POSTGRES_USER": "cyclonelens",
        "POSTGRES_PASSWORD": "".join(secrets.choice(alphabet) for _ in range(32)),
        "SECRET_KEY": secrets.token_urlsafe(48), "CORS_ORIGINS": args.origin.rstrip("/"),
        "WEB_BIND": "127.0.0.1", "WEB_PORT": "8080", "ALLOW_REGISTRATION": "true",
        "ACCESS_TOKEN_MINUTES": "60", "ENABLE_DOCS": "true", "MAX_IMPORT_MB": "500", "LOG_LEVEL": "INFO",
    }
    target.write_text("".join(f"{k}={v}\n" for k, v in values.items()))
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    print(f"Wrote {target} with new secrets. Back it up securely; never commit it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
