"""
Developer role switcher: sign in as an admin, organiser, student or ordinary member in one click.

This is a local development tool and is OFF unless every one of these holds:
  - APP_ENV is not "production"
  - DEV_ROLE_SWITCHER=1 is set
  - the request comes from this machine (127.0.0.1 or ::1)

The demo accounts have no password, so this endpoint is the only way into them. When the switcher is off, the
accounts are disabled at startup, so a database copied from a laptop into production cannot be used to sign in.
"""

import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth.dependencies import get_optional_user
from app.auth.sessions import start_session
from app.database import get_db

DEV_DOMAIN = "dev.hiveout.test"  # .test is reserved, so mail to these addresses can never reach a real person
LOOPBACK = {"127.0.0.1", "::1", "localhost"}

# key -> (label, what it is, account name)
PERSONAS = {
    "admin": ("Admin", "Full access to the admin console", "Dev Admin"),
    "organizer": ("Organiser", "Can host fests and city events", "Dev Organiser"),
    "student": ("Student", "Verified student at IIT Bombay", "Dev Student"),
    "user": ("User", "Ordinary member, not a verified student", "Dev User"),
}


def enabled() -> bool:
    return os.getenv("APP_ENV", "development") != "production" and os.getenv("DEV_ROLE_SWITCHER") == "1"


def _guard(request: Request) -> None:
    host = request.client.host if request.client else ""
    if not enabled() or host not in LOOPBACK:
        # Same answer as for a route that does not exist
        raise HTTPException(status_code=404, detail="Not Found")


# The guard runs before anything else on every route here, so a refused caller gets a plain 404 and not even a validation error
router = APIRouter(dependencies=[Depends(_guard)])


def _email(key: str) -> str:
    return f"{key}@{DEV_DOMAIN}"


def _ensure_persona(db: Session, key: str) -> models.User:
    """Create the demo account for this persona if needed, and put it in the right state."""
    label, _, name = PERSONAS[key]
    now = datetime.utcnow()
    user = db.query(models.User).filter(models.User.email == _email(key)).first()
    if not user:
        user = models.User(name=name, first_name=name.split()[0], last_name=" ".join(name.split()[1:]), email=_email(key), hashed_password=None,
                           auth_provider=models.AuthProviderEnum.email)
        db.add(user)
        db.flush()

    # Everything the site would otherwise ask for on first sign-in, so no pop-ups get in the way
    user.is_active = True
    user.hashed_password = None
    user.date_of_birth = user.date_of_birth or datetime(2002, 1, 1).date()
    user.terms_accepted_at = user.terms_accepted_at or now
    user.interests_set = True
    user.organizer_welcome_pending = False
    user.role = {"admin": models.RoleEnum.admin, "organizer": models.RoleEnum.organizer}.get(key, models.RoleEnum.user)

    first_college = db.query(models.College).order_by(models.College.id).first()
    user.can_host_fests = key == "organizer"
    user.can_host_city_events = key == "organizer"
    if key == "student":
        user.college_id = first_college.id if first_college else None
        user.study_year = 3
        user.student_verified_until = now + timedelta(days=365)  # refreshed every time, so it never lapses
    else:
        user.student_verified_until = None
        user.study_year = None
        user.college_id = None

    if key == "organizer":
        have = {oc.college_id for oc in user.organizer_colleges}
        for college in db.query(models.College).all():
            if college.id not in have:
                db.add(models.OrganizerCollege(user_id=user.id, college_id=college.id))
    db.commit()
    db.refresh(user)
    return user


class SwitchIn(BaseModel):
    persona: str


@router.get("/status")
def status():
    return {"enabled": True, "personas": [{"key": k, "label": v[0], "about": v[1]} for k, v in PERSONAS.items()]}


@router.post("/switch", response_model=schemas.Token)
def switch(data: SwitchIn, request: Request, db: Session = Depends(get_db), current=Depends(get_optional_user)):
    if data.persona not in PERSONAS:
        raise HTTPException(status_code=400, detail="Unknown persona")
    if current is not None and getattr(current, "current_sid", None):
        # Leaving the previous sign-in behind: end it on the server so its token stops working
        db.query(models.AuthSession).filter(models.AuthSession.id == current.current_sid).update({"revoked_at": datetime.utcnow()})
        db.commit()
    user = _ensure_persona(db, data.persona)
    try:
        db.add(models.AuthEvent(at=datetime.utcnow(), portal="dev", email=user.email, user_id=user.id,
                                ip=request.client.host if request.client else None, success=True, reason="dev_switch"))
        db.commit()
    except Exception:
        db.rollback()
    return start_session(db, user, request)


def disable_dev_accounts_if_off() -> None:
    """Run at startup. Whenever the switcher is off, the demo accounts cannot be used."""
    if enabled():
        return
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        db.query(models.User).filter(models.User.email.like(f"%@{DEV_DOMAIN}")).update({"is_active": False}, synchronize_session=False)
        db.commit()
    finally:
        db.close()
