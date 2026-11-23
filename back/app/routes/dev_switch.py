"""
Developer role switcher: sign in as an admin, organiser, student or ordinary member in one click.

This is a local development tool and is OFF unless every one of these holds:
  - APP_ENV is not "production"
  - DEV_ROLE_SWITCHER=1 is set
  - the request comes from this machine (127.0.0.1 or ::1)

The demo accounts have no password, so this endpoint is the only way into them. Wherever the switcher is off, the
authentication layer refuses these accounts (see app/auth/dependencies.py), so a database copied from a laptop into
production cannot be used to sign in.

Each demo account is given its starting role and permissions ONCE, when it is first created. After that the switcher only
signs in: whatever you change in the admin panel (remove the organiser role, change permissions or colleges, suspend the
account) stays exactly as you left it.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth.dependencies import get_optional_user
from app.auth.sessions import start_session
from app.database import get_db
from app.dev_mode import DEV_DOMAIN, enabled

LOOPBACK = {"127.0.0.1", "::1", "localhost"}

# key -> (label, what it is, account name)
PERSONAS = {
    "admin": ("Admin", "Full access to the admin console", "Dev Admin"),
    "organizer": ("Organiser", "Can host fests and city events", "Dev Organiser"),
    "student": ("Student", "Verified student at IIT Bombay", "Dev Student"),
    "user": ("User", "Ordinary member, not a verified student", "Dev User"),
}


def _guard(request: Request) -> None:
    host = request.client.host if request.client else ""
    if not enabled() or host not in LOOPBACK:
        # Same answer as for a route that does not exist
        raise HTTPException(status_code=404, detail="Not Found")


# The guard runs before anything else on every route here, so a refused caller gets a plain 404 and not even a validation error
router = APIRouter(dependencies=[Depends(_guard)])


def _email(key: str) -> str:
    return f"{key}@{DEV_DOMAIN}"


def _create_persona(db: Session, key: str) -> models.User:
    """Make the demo account with its starting state. Only ever called when it does not exist yet."""
    _, _, name = PERSONAS[key]
    now = datetime.utcnow()
    first_college = db.query(models.College).order_by(models.College.id).first()
    user = models.User(
        name=name, first_name=name.split()[0], last_name=" ".join(name.split()[1:]), email=_email(key), hashed_password=None,
        auth_provider=models.AuthProviderEnum.email, is_active=True,
        # Everything the site would otherwise ask for on first sign-in, so no pop-ups get in the way
        date_of_birth=datetime(2002, 1, 1).date(), terms_accepted_at=now, interests_set=True, organizer_welcome_pending=False,
        role={"admin": models.RoleEnum.admin, "organizer": models.RoleEnum.organizer}.get(key, models.RoleEnum.user),
        can_host_fests=key == "organizer", can_host_city_events=key == "organizer",
    )
    if key == "student":
        user.college_id = first_college.id if first_college else None
        user.study_year = 3
        user.student_verified_until = now + timedelta(days=365)
    db.add(user)
    db.flush()
    if key == "organizer":
        # Partner colleges only: the admin panel refuses to link an organiser to any other
        for college in db.query(models.College).filter(models.College.partner_status == "partner").all():
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
    user = db.query(models.User).filter(models.User.email == _email(data.persona)).first()
    if user is None:
        user = _create_persona(db, data.persona)
    elif user.is_active is False:
        # Suspended in the admin panel: leave it that way, so that can be tested too
        raise HTTPException(status_code=403, detail=f"The {PERSONAS[data.persona][0]} demo account is suspended in the admin panel.")

    if current is not None and getattr(current, "current_sid", None):
        # Leaving the previous sign-in behind: end it on the server so its token stops working
        db.query(models.AuthSession).filter(models.AuthSession.id == current.current_sid).update({"revoked_at": datetime.utcnow()})
        db.commit()
    try:
        db.add(models.AuthEvent(at=datetime.utcnow(), portal="dev", email=user.email, user_id=user.id,
                                ip=request.client.host if request.client else None, success=True, reason="dev_switch"))
        db.commit()
    except Exception:
        db.rollback()
    return start_session(db, user, request)
