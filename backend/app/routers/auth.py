from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import User
from ..schemas import RegisterRequest, LoginRequest
from ..security import (hash_password, verify_password, burn_password_check, create_token, current_user,
                        login_throttle)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "role": u.role}


def _authenticate(email: str, password: str, request: Request, db: Session) -> User:
    email, ip = email.lower(), (request.client.host if request.client else "unknown")
    login_throttle.check(email, ip)
    user = db.query(User).filter(func.lower(User.email) == email).first()
    if not user or not user.is_active:
        burn_password_check(password)
        ok = False
    else:
        ok = verify_password(password, user.hashed_password)
    if not ok:
        login_throttle.fail(email, ip)
        raise HTTPException(401, "Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    login_throttle.reset(email, ip)
    return user


@router.post("/register", status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """Creates a 'researcher' account. Administrators are created only with the server CLI."""
    if not settings.allow_registration:
        raise HTTPException(403, "Self-registration is disabled on this server")
    email = body.email.lower()
    if db.query(User).filter(func.lower(User.email) == email).first():
        raise HTTPException(409, "Email already registered")
    user = User(email=email, hashed_password=hash_password(body.password), role="researcher")
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email already registered")
    db.refresh(user)
    return _user_out(user)


@router.post("/login")
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = _authenticate(body.email, body.password, request, db)
    return {"access_token": create_token(user), "token_type": "bearer",
            "expires_in": settings.access_token_minutes * 60, "user": _user_out(user)}


@router.post("/token", include_in_schema=True, summary="OAuth2 form login (used by the /docs Authorize button)")
def token(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = _authenticate(form.username, form.password, request, db)
    return {"access_token": create_token(user), "token_type": "bearer"}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return _user_out(user)
