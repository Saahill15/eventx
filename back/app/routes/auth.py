import time
from datetime import datetime
from typing import List
from collections import defaultdict, deque
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from app.database import get_db
from app import models, schemas
from app.auth.dependencies import get_current_user
from app.auth.sessions import start_session, revoke_user_sessions

router = APIRouter()
pwd = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__truncate_error=False,  # truncate >72 bytes to avoid backend ValueError
)

# ─── Failed-login throttle ────────────────────────────────────────────────────
# In-memory and per process: slows password guessing without extra infrastructure.
MAX_FAILED_LOGINS = 10
LOGIN_WINDOW_SECONDS = 300
_failed_logins = defaultdict(deque)

# The admin sign-in is stricter: fewer tries, a longer lock
MAX_FAILED_ADMIN_LOGINS = 5
ADMIN_LOGIN_WINDOW_SECONDS = 900

def _throttle_key(request: Request, email: str) -> str:
    client = request.client.host if request.client else "unknown"
    return f"{client}|{email}"

def _recent_failures(key: str, window: int = LOGIN_WINDOW_SECONDS) -> deque:
    attempts = _failed_logins[key]
    cutoff = time.monotonic() - window
    while attempts and attempts[0] < cutoff:
        attempts.popleft()
    return attempts

def reset_login_throttle():
    _failed_logins.clear()


def _audit(db: Session, request: Request, portal: str, email: str, user, success: bool, reason: str) -> None:
    """Record a sign-in attempt. Failures to record must never block signing in."""
    try:
        db.add(models.AuthEvent(
            at=datetime.utcnow(), portal=portal, email=(email or "")[:255], user_id=user.id if user else None,
            ip=request.client.host if request.client else None, success=success, reason=reason,
        ))
        db.commit()
    except Exception:
        db.rollback()


def _find_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(func.lower(models.User.email) == email.lower()).first()



@router.post("/signup", response_model=schemas.Token)
def signup(data: schemas.SignupEmail, request: Request, db: Session = Depends(get_db)):
    if _find_user_by_email(db, data.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = models.User(
        name=f"{data.first_name} {data.last_name}",
        first_name=data.first_name,
        last_name=data.last_name,
        email=data.email,
        date_of_birth=data.date_of_birth,
        hashed_password=pwd.hash(data.password),
        auth_provider=models.AuthProviderEnum.email,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return start_session(db, user, request)

@router.post("/login", response_model=schemas.Token)
def login(data: schemas.LoginEmail, request: Request, db: Session = Depends(get_db)):
    key = _throttle_key(request, data.email)
    failures = _recent_failures(key)
    any_ip = _recent_failures(f"*|{data.email.lower()}")  # guessing from many addresses is counted too
    if len(failures) >= MAX_FAILED_LOGINS or len(any_ip) >= MAX_FAILED_LOGINS * 3:
        _audit(db, request, "public", data.email, None, False, "locked")
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in a few minutes.")

    user = _find_user_by_email(db, data.email)
    if not user or not user.hashed_password or not pwd.verify(data.password, user.hashed_password):
        failures.append(time.monotonic())
        any_ip.append(time.monotonic())
        _audit(db, request, "public", data.email, user, False, "bad_credentials")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.role == models.RoleEnum.admin:
        # Admins sign in on their own page, so their password only ever goes through the stricter admin endpoint
        _audit(db, request, "public", data.email, user, False, "admin_on_public_page")
        raise HTTPException(status_code=403, detail="This is an admin account. Please use the admin sign-in.")
    if user.is_active is False:
        _audit(db, request, "public", data.email, user, False, "disabled")
        raise HTTPException(status_code=403, detail="Account disabled")

    failures.clear()
    _audit(db, request, "public", data.email, user, True, "ok")
    return start_session(db, user, request)


@router.post("/admin/login", response_model=schemas.Token)
def admin_login(data: schemas.LoginEmail, request: Request, db: Session = Depends(get_db)):
    """Sign-in for admin accounts only. Stricter limits than the public one, and every attempt is logged."""
    key = "admin|" + _throttle_key(request, data.email)
    failures = _recent_failures(key, ADMIN_LOGIN_WINDOW_SECONDS)
    any_ip = _recent_failures(f"admin|*|{data.email.lower()}", ADMIN_LOGIN_WINDOW_SECONDS)
    if len(failures) >= MAX_FAILED_ADMIN_LOGINS or len(any_ip) >= MAX_FAILED_ADMIN_LOGINS * 2:
        _audit(db, request, "admin", data.email, None, False, "locked")
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")

    user = _find_user_by_email(db, data.email)
    password_ok = bool(user and user.hashed_password and pwd.verify(data.password, user.hashed_password))
    if not password_ok or user.role != models.RoleEnum.admin:
        failures.append(time.monotonic())
        any_ip.append(time.monotonic())
        # The answer is the same whether the email is unknown, the password is wrong or the account is not an admin
        _audit(db, request, "admin", data.email, user, False, "bad_credentials" if not password_ok else "not_admin")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.is_active is False:
        _audit(db, request, "admin", data.email, user, False, "disabled")
        raise HTTPException(status_code=403, detail="Account disabled")

    failures.clear()
    _audit(db, request, "admin", data.email, user, True, "ok")
    return start_session(db, user, request)


@router.post("/logout")
def logout(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """End this sign-in on the server, so the token stops working even if someone copied it."""
    db.query(models.AuthSession).filter(models.AuthSession.id == user.current_sid).update({"revoked_at": datetime.utcnow()})
    db.commit()
    return {"message": "Signed out"}


@router.post("/logout-all")
def logout_all(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Sign out of every device, this one included."""
    revoke_user_sessions(db, user.id)
    db.commit()
    return {"message": "Signed out everywhere"}


@router.get("/sessions", response_model=List[schemas.SessionOut])
def my_sessions(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    rows = (
        db.query(models.AuthSession)
        .filter(models.AuthSession.user_id == user.id, models.AuthSession.revoked_at.is_(None), models.AuthSession.expires_at > datetime.utcnow())
        .order_by(models.AuthSession.last_seen_at.desc())
        .all()
    )
    return [schemas.SessionOut(id=r.id, created_at=r.created_at, last_seen_at=r.last_seen_at, ip=r.ip, user_agent=r.user_agent, current=r.id == user.current_sid) for r in rows]


@router.delete("/sessions/{session_id}")
def end_session(session_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    row = db.query(models.AuthSession).filter(models.AuthSession.id == session_id, models.AuthSession.user_id == user.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    row.revoked_at = datetime.utcnow()
    db.commit()
    return {"message": "Session ended"}
