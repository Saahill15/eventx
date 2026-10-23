import hashlib
import secrets
import time
from datetime import datetime, timedelta
from typing import List
from collections import defaultdict, deque
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from app.database import get_db
from app import models, schemas
from app.auth.dependencies import get_current_user
from app.auth import google
from app.auth.sessions import start_session, revoke_user_sessions
from app.notify import send_password_reset, show_links_in_responses, site_url

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
        terms_accepted_at=datetime.utcnow(),
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


# ─── Password reset ───────────────────────────────────────────────────────────
RESET_LINK_MINUTES = 30
MAX_RESET_REQUESTS = 3          # per email, per 15 minutes
MAX_RESET_REQUESTS_PER_IP = 10
RESET_WINDOW_SECONDS = 900


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _live_reset(db: Session, token: str):
    row = db.query(models.PasswordReset).filter(models.PasswordReset.token_hash == _token_hash(token)).first()
    if not row or row.used_at is not None or row.expires_at < datetime.utcnow():
        return None
    return row


@router.post("/password/forgot", response_model=schemas.ForgotPasswordOut)
def forgot_password(data: schemas.ForgotPassword, request: Request, db: Session = Depends(get_db)):
    """
    Send a link to choose a new password. The answer is the same whether or not the email has an account,
    so this cannot be used to find out who is registered.
    """
    ip = request.client.host if request.client else "unknown"
    by_email = _recent_failures(f"reset|{data.email}", RESET_WINDOW_SECONDS)
    by_ip = _recent_failures(f"reset-ip|{ip}", RESET_WINDOW_SECONDS)
    if len(by_email) >= MAX_RESET_REQUESTS or len(by_ip) >= MAX_RESET_REQUESTS_PER_IP:
        raise HTTPException(status_code=429, detail="Too many requests. Try again in 15 minutes.")
    by_email.append(time.monotonic())
    by_ip.append(time.monotonic())

    out = schemas.ForgotPasswordOut(message=f"If an account exists for {data.email}, we have sent it a link to choose a new password. The link works for {RESET_LINK_MINUTES} minutes.")
    user = _find_user_by_email(db, data.email)
    if not user or user.is_active is False:
        _audit(db, request, "reset", data.email, user, False, "reset_unknown" if not user else "disabled")
        return out

    now = datetime.utcnow()
    # Only the newest link works
    db.query(models.PasswordReset).filter(models.PasswordReset.user_id == user.id, models.PasswordReset.used_at.is_(None)).update({"used_at": now})
    token = secrets.token_urlsafe(32)
    db.add(models.PasswordReset(user_id=user.id, token_hash=_token_hash(token), created_at=now, expires_at=now + timedelta(minutes=RESET_LINK_MINUTES), ip=ip))
    db.commit()
    link = f"{site_url()}/reset-password?token={token}"
    send_password_reset(user.email, link)
    _audit(db, request, "reset", data.email, user, True, "reset_requested")
    if show_links_in_responses():
        out.dev_link = link
    return out


@router.get("/password/reset/check")
def check_reset_link(token: str, db: Session = Depends(get_db)):
    """Is this link still usable? Lets the page say so before the person types a new password."""
    return {"valid": _live_reset(db, token) is not None}


@router.post("/password/reset")
def reset_password(data: schemas.ResetPassword, request: Request, db: Session = Depends(get_db)):
    row = _live_reset(db, data.token)
    if not row:
        raise HTTPException(status_code=400, detail="This link is invalid or has expired. Ask for a new one.")
    user = db.query(models.User).filter(models.User.id == row.user_id).first()
    if not user or user.is_active is False:
        raise HTTPException(status_code=403, detail="Account disabled")
    now = datetime.utcnow()
    user.hashed_password = pwd.hash(data.new_password)
    row.used_at = now
    db.query(models.PasswordReset).filter(models.PasswordReset.user_id == user.id, models.PasswordReset.used_at.is_(None)).update({"used_at": now})
    revoke_user_sessions(db, user.id)  # anyone signed in with the old password is signed out
    db.commit()
    # A forgotten password usually came with failed tries: let them sign in straight away
    for key in [k for k in _failed_logins if k.endswith(f"|{(user.email or '').lower()}")]:
        _failed_logins.pop(key, None)
    _audit(db, request, "reset", user.email, user, True, "password_reset")
    return {"message": "Your password has been changed. Sign in with the new one.", "admin": user.role == models.RoleEnum.admin}


# ─── Google sign-in ───────────────────────────────────────────────────────────
MAX_GOOGLE_FAILURES_PER_IP = 20


@router.post("/google", response_model=schemas.Token)
def google_sign_in(data: schemas.GoogleSignIn, request: Request, db: Session = Depends(get_db)):
    """
    Sign in, or sign up, with a Google account. An existing account with the same verified email is linked to it.
    A brand new account still has to add a date of birth and accept the terms (profile_complete is false until then).
    """
    ip_failures = _recent_failures(f"google|{request.client.host if request.client else 'unknown'}")
    if len(ip_failures) >= MAX_GOOGLE_FAILURES_PER_IP:
        raise HTTPException(status_code=429, detail="Too many attempts. Try again in a few minutes.")
    try:
        claims = google.verify(data.credential)
    except google.GoogleNotConfigured:
        raise HTTPException(status_code=503, detail="Google sign-in is not set up yet.")
    except google.GoogleTokenInvalid:
        ip_failures.append(time.monotonic())
        _audit(db, request, "google", None, None, False, "bad_credentials")
        raise HTTPException(status_code=401, detail="Google sign-in failed. Please try again.")

    sub, email = claims["sub"], claims["email"].lower()
    user = db.query(models.User).filter(models.User.google_sub == sub).first() or _find_user_by_email(db, email)
    if user and user.role == models.RoleEnum.admin:
        _audit(db, request, "google", email, user, False, "admin_on_public_page")
        raise HTTPException(status_code=403, detail="This is an admin account. Please use the admin sign-in.")
    if user and user.is_active is False:
        _audit(db, request, "google", email, user, False, "disabled")
        raise HTTPException(status_code=403, detail="Account disabled")
    if user and user.google_sub and user.google_sub != sub:
        _audit(db, request, "google", email, user, False, "other_google_account")
        raise HTTPException(status_code=409, detail="This email is already linked to a different Google account.")

    notice = None
    if user is None:
        first = (claims.get("given_name") or "").strip()[:100] or email.split("@")[0][:100]
        last = (claims.get("family_name") or "").strip()[:100]
        user = models.User(
            name=f"{first} {last}".strip(), first_name=first, last_name=last or None, email=email,
            google_sub=sub, auth_provider=models.AuthProviderEnum.google,
        )
        db.add(user)
        reason = "signed_up"
    elif not user.google_sub:
        # First time this account meets Google. Emails are not verified at sign-up, so someone else may have registered this
        # address with a password before its owner did. Google has just proved who owns it: the old password and sessions end.
        user.google_sub = sub
        if user.hashed_password:
            user.hashed_password = None
            notice = "Your Google account is now linked. For your safety the old password was turned off. Use Forgot password to set a new one."
        revoke_user_sessions(db, user.id)
        reason = "linked"
    else:
        reason = "ok"
    db.commit()
    db.refresh(user)
    _audit(db, request, "google", email, user, True, reason)
    return {**start_session(db, user, request), "notice": notice}
