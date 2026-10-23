"""
Sign-in sessions.

Every login creates a row in auth_sessions and a JWT that names it (claim "sid"). Each request checks the
signature AND the row, so a session ends when any of these happens:
  - the user signs out, or an admin signs them out, suspends them or changes their role
  - the password is changed (all other sessions)
  - they are inactive for longer than their role's idle timeout
  - the session reaches its maximum age

Admin sessions are deliberately short: 15 minutes idle, 8 hours at most. Everything is overridable with env vars.
"""

import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app import models
from app.auth.jwt import create_token, EXPIRE_MIN

ADMIN_IDLE_MINUTES = int(os.getenv("ADMIN_IDLE_MINUTES", 15))
ADMIN_MAX_HOURS = int(os.getenv("ADMIN_SESSION_HOURS", 8))
ORGANIZER_IDLE_MINUTES = int(os.getenv("ORGANIZER_IDLE_MINUTES", 120))
ORGANIZER_MAX_HOURS = int(os.getenv("ORGANIZER_SESSION_HOURS", 72))
USER_IDLE_MINUTES = int(os.getenv("USER_IDLE_MINUTES", EXPIRE_MIN))

TOUCH_EVERY = timedelta(seconds=30)  # how often "last seen" is written, so reads stay cheap


def policy(role) -> Tuple[timedelta, timedelta]:
    """(idle timeout, maximum age) for someone with this role."""
    role = getattr(role, "value", role)
    if role == "admin":
        return timedelta(minutes=ADMIN_IDLE_MINUTES), timedelta(hours=ADMIN_MAX_HOURS)
    if role == "organizer":
        return timedelta(minutes=ORGANIZER_IDLE_MINUTES), timedelta(hours=ORGANIZER_MAX_HOURS)
    return timedelta(minutes=USER_IDLE_MINUTES), timedelta(minutes=EXPIRE_MIN)


def _expired() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your session has ended. Please sign in again.")


def start_session(db: Session, user: models.User, request: Optional[Request] = None) -> dict:
    """Open a session for the user and return the token response."""
    now = datetime.utcnow()
    idle, max_age = policy(user.role)
    db.query(models.AuthSession).filter(models.AuthSession.expires_at < now - timedelta(days=1)).delete()
    session = models.AuthSession(
        id=str(uuid.uuid4()), user_id=user.id, created_at=now, last_seen_at=now, expires_at=now + max_age,
        ip=(request.client.host if request and request.client else None),
        user_agent=((request.headers.get("user-agent") or "")[:200] if request else None) or None,
    )
    db.add(session)
    db.commit()
    token = create_token({"sub": str(user.id), "sid": session.id}, expires_in=max_age)
    return {
        "access_token": token, "token_type": "bearer", "role": user.role, "interests_set": user.interests_set, "profile_complete": user.profile_complete,
        "expires_in": int(max_age.total_seconds()), "idle_timeout_seconds": int(idle.total_seconds()),
    }


def check_session(db: Session, sid: Optional[str], user: models.User) -> models.AuthSession:
    """Raise 401 unless the session is live. Records activity."""
    session = db.query(models.AuthSession).filter(models.AuthSession.id == sid, models.AuthSession.user_id == user.id).first() if sid else None
    if not session or session.revoked_at is not None:
        raise _expired()
    now = datetime.utcnow()
    # Judged by the role the person has NOW, so a freshly promoted admin gets the strict limits at once
    idle, max_age = policy(user.role)
    if now > session.expires_at or now > session.created_at + max_age or now - session.last_seen_at > idle:
        session.revoked_at = now
        db.commit()
        raise _expired()
    if now - session.last_seen_at > TOUCH_EVERY:
        session.last_seen_at = now
        db.commit()
    return session


def revoke_user_sessions(db: Session, user_id: int, except_sid: Optional[str] = None) -> int:
    """End all of a user's live sessions (optionally keeping one). The caller commits."""
    q = db.query(models.AuthSession).filter(models.AuthSession.user_id == user_id, models.AuthSession.revoked_at.is_(None))
    if except_sid:
        q = q.filter(models.AuthSession.id != except_sid)
    return q.update({"revoked_at": datetime.utcnow()}, synchronize_session=False)
