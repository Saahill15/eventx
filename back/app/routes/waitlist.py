"""
Waiting lists for full events.

  GET    /api/fest-events/{id}/waitlist           can I queue, how long is it, and where am I
  POST   /api/fest-events/{id}/waitlist           join the queue (needs an entry pass; the event must be full)
  DELETE /api/fest-events/{id}/waitlist           leave it
  GET    /api/fests/{slug}/waitlist               every queue of the fest (committee), optionally one event
  POST   /api/fests/{slug}/waitlist/{id}/admit    let someone in now, even past the seat limit
  DELETE /api/fests/{slug}/waitlist/{id}          take someone off, with an optional reason
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, notices, pricing, schemas, waitlist as wl
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.permissions import is_fest_staff
from app.routes.event_questions import validate_answers
from app.routes.fest_events import _approved_pass, _existing_registration, _open_fest_event

event_router = APIRouter()
fest_router = APIRouter()


def _event(db: Session, event_id: int) -> models.Event:
    e = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not e or e.status != models.StatusEnum.approved or e.event_type != models.EventTypeEnum.fest or not e.requires_registration:
        raise HTTPException(status_code=404, detail="Event not found")
    return e


def _mine(db: Session, event_id: int, user_id: int) -> Optional[models.WaitlistEntry]:
    return db.query(models.WaitlistEntry).filter(models.WaitlistEntry.event_id == event_id, models.WaitlistEntry.user_id == user_id).order_by(models.WaitlistEntry.id.desc()).first()


def _status(db: Session, event: models.Event, user: models.User) -> schemas.WaitlistStatus:
    queue = wl.waiting(db, event.id)
    full = wl.is_full(db, event)
    mine = _mine(db, event.id, user.id)
    out_mine = None
    if mine and mine.status in ("waiting", "promoted", "removed"):
        out_mine = schemas.WaitlistMine(position=wl.position_of(db, mine) or 0, status=mine.status, note=mine.note)
    full_list = event.waitlist_limit is not None and len(queue) >= event.waitlist_limit
    return schemas.WaitlistStatus(enabled=bool(event.waitlist_enabled), full=full, waiting=len(queue), limit=event.waitlist_limit, open=bool(event.waitlist_enabled) and full and not full_list, mine=out_mine)


@event_router.get("/{event_id}/waitlist", response_model=schemas.WaitlistStatus)
def waitlist_status(event_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return _status(db, _event(db, event_id), user)


@event_router.post("/{event_id}/waitlist", response_model=schemas.WaitlistStatus, status_code=status.HTTP_201_CREATED)
def join(event_id: int, data: schemas.WaitlistJoin, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    event = _open_fest_event(db, event_id, user)   # the usual rules: it must be taking registrations, and you must be allowed to register
    if not event.waitlist_enabled:
        raise HTTPException(status_code=400, detail="This event has no waiting list")
    if not wl.is_full(db, event):
        raise HTTPException(status_code=400, detail="There are still seats: register directly")
    fest_pass = _approved_pass(db, event, user)
    if _existing_registration(db, fest_pass, event.id):
        raise HTTPException(status_code=400, detail="You are already registered for this event")
    mine = _mine(db, event.id, user.id)
    if mine and mine.status == "waiting":
        raise HTTPException(status_code=400, detail="You are already on the waiting list")
    if event.waitlist_limit is not None and len(wl.waiting(db, event.id)) >= event.waitlist_limit:
        raise HTTPException(status_code=400, detail="The waiting list is full")
    answers = validate_answers(event, data.answers)
    team_name = None
    if event.is_team_event:
        team_name = (data.team_name or "").strip()
        if not team_name:
            raise HTTPException(status_code=400, detail="Give your team a name")
        if db.query(models.Team).filter(models.Team.event_id == event.id, func.lower(models.Team.name) == team_name.lower()).first():
            raise HTTPException(status_code=400, detail="A team with that name already exists for this event")
    # The ticket and code are checked now so a mistake shows straight away. They are checked again when a seat opens
    if event.is_paid or pricing.tiers_of(db, event.id) or (data.promo_code and data.promo_code.strip()):
        pricing.quote(db, event, user, data.ticket_tier_id, data.promo_code)
    db.add(models.WaitlistEntry(
        event_id=event.id, user_id=user.id, ticket_tier_id=data.ticket_tier_id, promo_code=(data.promo_code or "").strip().upper() or None, team_name=team_name,
        answers=[{"question_id": q.id, "value": v} for q, v in answers] or None,
    ))
    db.commit()
    return _status(db, event, user)


@event_router.delete("/{event_id}/waitlist", response_model=schemas.WaitlistStatus)
def leave(event_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    event = _event(db, event_id)
    mine = _mine(db, event_id, user.id)
    if not mine or mine.status != "waiting":
        raise HTTPException(status_code=404, detail="You are not on the waiting list")
    mine.status = "left"
    db.commit()
    return _status(db, event, user)


# ─── the committee's side ─────────────────────────────────────────────────────

def _fest(db: Session, slug: str) -> models.Fest:
    f = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not f:
        raise HTTPException(status_code=404, detail="Fest not found")
    return f


def _staff(db: Session, fest: models.Fest, user) -> None:
    if not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can do that")


def _row(db: Session, e: models.WaitlistEntry) -> schemas.WaitlistRow:
    tier = db.query(models.TicketTier).filter(models.TicketTier.id == e.ticket_tier_id).first() if e.ticket_tier_id else None
    return schemas.WaitlistRow(id=e.id, event_id=e.event_id, event_title=e.event.title, user_name=e.user.name if e.user else None, user_email=e.user.email if e.user else None,
                               position=wl.position_of(db, e), status=e.status, team_name=e.team_name, ticket_tier_name=tier.name if tier else None, promo_code=e.promo_code,
                               note=e.note, created_at=e.created_at, promoted_at=e.promoted_at)


@fest_router.get("/{slug}/waitlist", response_model=List[schemas.WaitlistRow])
def list_waitlists(slug: str, event_id: Optional[int] = None, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    q = db.query(models.WaitlistEntry).join(models.Event, models.Event.id == models.WaitlistEntry.event_id).filter(models.Event.fest_id == fest.id)
    if event_id is not None:
        q = q.filter(models.WaitlistEntry.event_id == event_id)
    return [_row(db, e) for e in q.order_by(models.WaitlistEntry.event_id, models.WaitlistEntry.created_at, models.WaitlistEntry.id).all()]


def _entry(db: Session, fest: models.Fest, entry_id: int) -> models.WaitlistEntry:
    e = db.query(models.WaitlistEntry).join(models.Event, models.Event.id == models.WaitlistEntry.event_id).filter(models.WaitlistEntry.id == entry_id, models.Event.fest_id == fest.id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Not found")
    return e


@fest_router.post("/{slug}/waitlist/{entry_id}/admit", response_model=schemas.WaitlistRow)
def admit(slug: str, entry_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Let this person in now, even if the event is at its limit (the committee can always make room)."""
    fest = _fest(db, slug)
    _staff(db, fest, user)
    e = _entry(db, fest, entry_id)
    if e.status != "waiting":
        raise HTTPException(status_code=400, detail="This person is no longer waiting")
    if not wl.promote_one(db, e.event, e):
        db.commit()
        raise HTTPException(status_code=400, detail=f"They could not be admitted: {e.note}")
    db.commit()
    db.refresh(e)
    return _row(db, e)


@fest_router.delete("/{slug}/waitlist/{entry_id}", response_model=schemas.WaitlistRow)
def remove(slug: str, entry_id: int, reason: Optional[str] = Query(default=None, max_length=300), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    e = _entry(db, fest, entry_id)
    if e.status != "waiting":
        raise HTTPException(status_code=400, detail="This person is no longer waiting")
    e.status, e.note = "removed", (reason or "").strip() or None
    notices.notify(db, e.user_id, "waitlist", f"You were taken off the waiting list for {e.event.title}", "The committee removed you from the waiting list." + (f" Reason: {e.note}" if e.note else ""))
    db.commit()
    db.refresh(e)
    return _row(db, e)
