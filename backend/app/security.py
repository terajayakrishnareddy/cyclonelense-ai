import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User

ALGORITHM = "HS256"
ISSUER = "cyclonelens-api"
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/token")
_dummy_hash: str | None = None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:  # e.g. password longer than bcrypt's 72-byte limit, malformed hash
        return False


def burn_password_check(password: str) -> None:
    """Constant-ish work for unknown users so login timing does not reveal registered emails."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("not-a-real-password")
    verify_password(password, _dummy_hash)


def create_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user.id), "iss": ISSUER, "iat": now,
               "exp": now + timedelta(minutes=settings.access_token_minutes)}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM], issuer=ISSUER,
                             options={"require": ["exp", "sub"]})
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(401, "Invalid or expired access token", headers={"WWW-Authenticate": "Bearer"})
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(401, "User not found or inactive", headers={"WWW-Authenticate": "Bearer"})
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    # Role is read from the database (not the token) so revoking admin takes effect immediately.
    if user.role != "admin":
        raise HTTPException(403, "Administrator role required")
    return user


class LoginThrottle:
    """In-memory failed-login limiter (per process). Rate-limit at the reverse proxy too."""

    def __init__(self):
        self._failures: dict[tuple[str, str], deque] = defaultdict(deque)

    def _prune(self, key):
        q, cutoff = self._failures[key], time.monotonic() - settings.login_window_seconds
        while q and q[0] < cutoff:
            q.popleft()
        return q

    def check(self, email: str, ip: str) -> None:
        q = self._prune((email, ip))
        if len(q) >= settings.login_max_failures:
            retry = max(1, int(settings.login_window_seconds - (time.monotonic() - q[0])))
            raise HTTPException(429, "Too many failed login attempts. Try again later.", headers={"Retry-After": str(retry)})

    def fail(self, email: str, ip: str) -> None:
        self._failures[(email, ip)].append(time.monotonic())

    def reset(self, email: str | None = None, ip: str | None = None) -> None:
        if email is None:
            self._failures.clear()
        else:
            self._failures.pop((email, ip or ""), None)


login_throttle = LoginThrottle()
