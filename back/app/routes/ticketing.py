"""
Ticket tiers, promo codes and price quotes.

An event that takes registrations can sell one kind of ticket at its own price, or several (tiers: Early bird, Regular, VIP), each
with a price, a student price, a number of seats and a sale window. A promo code takes a percentage or a fixed amount off a paid
ticket. Everything the committee sets here is theirs: nothing is fixed.

  GET    /api/events/{id}/tiers                  the event's tickets, with what is left (public for visible events)
  POST   /api/events/{id}/tiers                  add one (director or core team); PATCH|DELETE /api/ticket-tiers/{id}
  POST   /api/fest-events/{id}/quote             what this person would pay for a ticket with a code, without registering
  GET|POST /api/fests/{slug}/promo-codes         the fest's codes (committee); PATCH|DELETE .../promo-codes/{id}
"""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, pricing, schemas
from app.auth.dependencies import get_current_user, get_optional_user
from app.database import get_db
from app.money import rupees, to_paise
from app.permissions import can_view_event, is_fest_staff

tiers_router = APIRouter()
promo_router = APIRouter()
quote_router = APIRouter()
MAX_TIERS, MAX_PROMOS = 12, 200


# ─── tiers ────────────────────────────────────────────────────────────────────

def _event(db: Session, event_id: int) -> models.Event:
    e = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not e or e.event_type != models.EventTypeEnum.fest:
        raise HTTPException(status_code=404, detail="Event not found")
    return e


def _staff(db: Session, event: models.Event, user) -> None:
    if not is_fest_staff(db, event.fest_id, user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can change tickets")


@tiers_router.get("/events/{event_id}/tiers", response_model=List[schemas.TierOut])
def list_tiers(event_id: int, db: Session = Depends(get_db), user=Depends(get_optional_user)):
    event = _event(db, event_id)
    if not can_view_event(db, event, user):
        raise HTTPException(status_code=404, detail="Event not found")
    staff = is_fest_staff(db, event.fest_id, user)
    # Tiers that are switched off are only for the committee
    return [pricing.tier_out(db, t, staff=staff) for t in pricing.tiers_of(db, event.id, only_active=not staff)]


@tiers_router.post("/events/{event_id}/tiers", response_model=schemas.TierOut, status_code=status.HTTP_201_CREATED)
def add_tier(event_id: int, data: schemas.TierIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    event = _event(db, event_id)
    _staff(db, event, user)
    if not event.requires_registration:
        raise HTTPException(status_code=400, detail="Turn on registration for this event first: tickets are for events people register for")
    existing = pricing.tiers_of(db, event.id, only_active=False)
    if len(existing) >= MAX_TIERS:
        raise HTTPException(status_code=400, detail=f"An event can have at most {MAX_TIERS} kinds of ticket")
    if any(t.name.lower() == data.name.lower() for t in existing):
        raise HTTPException(status_code=400, detail="This event already has a ticket with that name")
    t = models.TicketTier(
        fest_id=event.fest_id, event_id=event.id, name=data.name, description=data.description or None, price_paise=to_paise(data.price),
        student_price_paise=None if data.student_price is None else to_paise(data.student_price), quantity=data.quantity, sales_open_on=data.sales_open_on,
        sales_close_on=data.sales_close_on, position=len(existing), active=data.active,
    )
    db.add(t)
    db.flush()
    pricing.sync_event_price(db, event)
    db.commit()
    db.refresh(t)
    return pricing.tier_out(db, t, staff=True)


def _tier(db: Session, tier_id: int) -> models.TicketTier:
    t = db.query(models.TicketTier).filter(models.TicketTier.id == tier_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return t


@tiers_router.patch("/ticket-tiers/{tier_id}", response_model=schemas.TierOut)
def update_tier(tier_id: int, data: schemas.TierUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    t = _tier(db, tier_id)
    event = _event(db, t.event_id)
    _staff(db, event, user)
    u = data.model_dump(exclude_unset=True)
    n_sold = pricing.sold(db, t.id)
    if u.get("quantity") is not None and u["quantity"] < n_sold:
        raise HTTPException(status_code=400, detail=f"{n_sold} are already sold, so there cannot be fewer than that")
    if u.get("name") is not None and any(o.id != t.id and o.name.lower() == u["name"].lower() for o in pricing.tiers_of(db, event.id, only_active=False)):
        raise HTTPException(status_code=400, detail="This event already has a ticket with that name")
    price = to_paise(u["price"]) if u.get("price") is not None else t.price_paise
    student = (None if u["student_price"] is None else to_paise(u["student_price"])) if "student_price" in u else t.student_price_paise
    if student is not None and student >= price:
        raise HTTPException(status_code=400, detail="The student price must be lower than the price")
    opens = u["sales_open_on"] if "sales_open_on" in u else t.sales_open_on
    closes = u["sales_close_on"] if "sales_close_on" in u else t.sales_close_on
    if opens and closes and closes < opens:
        raise HTTPException(status_code=400, detail="Sales cannot close before they open")
    for field in ("name", "active"):
        if u.get(field) is not None:
            setattr(t, field, u[field])
    if "description" in u:
        t.description = u["description"] or None
    if "quantity" in u:
        t.quantity = u["quantity"]
    t.price_paise, t.student_price_paise, t.sales_open_on, t.sales_close_on = price, student, opens, closes
    db.flush()
    pricing.sync_event_price(db, event)
    db.commit()
    return pricing.tier_out(db, t, staff=True)


@tiers_router.delete("/ticket-tiers/{tier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tier(tier_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    t = _tier(db, tier_id)
    event = _event(db, t.event_id)
    _staff(db, event, user)
    if db.query(models.EventRegistration.id).filter(models.EventRegistration.ticket_tier_id == t.id).first():
        raise HTTPException(status_code=400, detail="Tickets of this kind have been sold. Switch it off instead, so nobody else can buy it.")
    db.query(models.WaitlistEntry).filter(models.WaitlistEntry.ticket_tier_id == t.id).update({"ticket_tier_id": None}, synchronize_session=False)
    db.delete(t)
    db.flush()
    pricing.sync_event_price(db, event)
    db.commit()


# ─── quote ────────────────────────────────────────────────────────────────────

@quote_router.post("/{event_id}/quote", response_model=schemas.QuoteOut)
def get_quote(event_id: int, data: schemas.QuoteIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """What this person would pay, with their ticket choice and code. Nothing is booked."""
    event = _event(db, event_id)
    if event.status != models.StatusEnum.approved or not event.requires_registration:
        raise HTTPException(status_code=404, detail="Event not found")
    return pricing.quote_out(pricing.quote(db, event, user, data.ticket_tier_id, data.promo_code))


# ─── promo codes ──────────────────────────────────────────────────────────────

def _fest(db: Session, slug: str) -> models.Fest:
    f = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not f:
        raise HTTPException(status_code=404, detail="Fest not found")
    return f


def _promo_staff(db: Session, fest: models.Fest, user) -> None:
    if not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can change promo codes")


def promo_out(db: Session, p: models.PromoCode) -> schemas.PromoOut:
    regs = db.query(models.EventRegistration).filter(models.EventRegistration.promo_code_id == p.id, models.EventRegistration.approval_status.in_(pricing.ACTIVE_STATUSES)).all()
    return schemas.PromoOut(
        id=p.id, code=p.code, description=p.description, kind=p.kind, value=float(p.value) if p.kind == "percent" else rupees(p.value), event_ids=p.event_ids, max_uses=p.max_uses,
        per_user_limit=p.per_user_limit, valid_from=p.valid_from, valid_until=p.valid_until, students_only=bool(p.students_only), active=bool(p.active),
        used=len(regs), discount_given=rupees(sum(r.discount_paise or 0 for r in regs)), status=pricing.promo_status(db, p, date.today()),
    )


def _events_ok(db: Session, fest: models.Fest, ids: Optional[List[int]]) -> Optional[List[int]]:
    if ids is None:
        return None
    ids = sorted(set(ids))
    found = {e.id for e in db.query(models.Event).filter(models.Event.fest_id == fest.id, models.Event.id.in_(ids or [0])).all()}
    if set(ids) - found:
        raise HTTPException(status_code=400, detail="One of those events is not part of this fest")
    return ids or None


@promo_router.get("/{slug}/promo-codes", response_model=List[schemas.PromoOut])
def list_promos(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _promo_staff(db, fest, user)
    return [promo_out(db, p) for p in db.query(models.PromoCode).filter(models.PromoCode.fest_id == fest.id).order_by(models.PromoCode.id).all()]


@promo_router.post("/{slug}/promo-codes", response_model=schemas.PromoOut, status_code=status.HTTP_201_CREATED)
def add_promo(slug: str, data: schemas.PromoIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _promo_staff(db, fest, user)
    if db.query(models.PromoCode).filter(models.PromoCode.fest_id == fest.id).count() >= MAX_PROMOS:
        raise HTTPException(status_code=400, detail=f"A fest can have at most {MAX_PROMOS} promo codes")
    if pricing.find_promo(db, fest.id, data.code):
        raise HTTPException(status_code=400, detail="This fest already has that code")
    if data.kind == "percent" and data.value != int(data.value):
        raise HTTPException(status_code=400, detail="A percentage must be a whole number")
    p = models.PromoCode(
        fest_id=fest.id, code=data.code, description=data.description or None, kind=data.kind, value=int(data.value) if data.kind == "percent" else to_paise(data.value),
        event_ids=_events_ok(db, fest, data.event_ids), max_uses=data.max_uses, per_user_limit=data.per_user_limit, valid_from=data.valid_from, valid_until=data.valid_until,
        students_only=data.students_only, active=data.active,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return promo_out(db, p)


def _promo(db: Session, fest: models.Fest, promo_id: int) -> models.PromoCode:
    p = db.query(models.PromoCode).filter(models.PromoCode.id == promo_id, models.PromoCode.fest_id == fest.id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Code not found")
    return p


@promo_router.patch("/{slug}/promo-codes/{promo_id}", response_model=schemas.PromoOut)
def update_promo(slug: str, promo_id: int, data: schemas.PromoUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _promo_staff(db, fest, user)
    p = _promo(db, fest, promo_id)
    u = data.model_dump(exclude_unset=True)
    if u.get("value") is not None:
        if p.kind == "percent":
            if u["value"] != int(u["value"]) or not 0 < u["value"] <= 100:
                raise HTTPException(status_code=400, detail="A percentage must be a whole number from 1 to 100")
            p.value = int(u["value"])
        else:
            p.value = to_paise(u["value"])
    if "event_ids" in u:
        p.event_ids = _events_ok(db, fest, u["event_ids"])
    for field in ("max_uses", "valid_from", "valid_until"):
        if field in u:
            setattr(p, field, u[field])
    for field in ("per_user_limit", "students_only", "active"):
        if u.get(field) is not None:
            setattr(p, field, u[field])
    if "description" in u:
        p.description = u["description"] or None
    if p.valid_from and p.valid_until and p.valid_until < p.valid_from:
        db.rollback()
        raise HTTPException(status_code=400, detail="A code cannot expire before it starts")
    db.commit()
    return promo_out(db, p)


@promo_router.delete("/{slug}/promo-codes/{promo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_promo(slug: str, promo_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _promo_staff(db, fest, user)
    p = _promo(db, fest, promo_id)
    if db.query(models.EventRegistration.id).filter(models.EventRegistration.promo_code_id == p.id).first():
        raise HTTPException(status_code=400, detail="This code has been used. Switch it off instead, so it stays on record.")
    db.delete(p)
    db.commit()
