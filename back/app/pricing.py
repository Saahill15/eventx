"""
What a ticket costs a particular person, and whether they can buy it right now.

An event either sells one kind of ticket at its own price, or several kinds (tiers: Early bird, Regular, VIP) each with a price, a
number of seats and a sale window. A promo code may then take money off. Everything is worked out here, once, so registering,
joining a team, the waitlist and the price shown on the page always agree.
"""

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.money import rupees

ACTIVE_STATUSES = (models.RegApprovalStatusEnum.pending, models.RegApprovalStatusEnum.approved)


@dataclass
class Quote:
    tier: Optional[models.TicketTier]
    base_paise: int
    discount_paise: int
    promo: Optional[models.PromoCode]

    @property
    def total_paise(self) -> int:
        return max(self.base_paise - self.discount_paise, 0)


def tiers_of(db: Session, event_id: int, only_active: bool = True) -> List[models.TicketTier]:
    q = db.query(models.TicketTier).filter(models.TicketTier.event_id == event_id)
    if only_active:
        q = q.filter(models.TicketTier.active.is_(True))
    return q.order_by(models.TicketTier.position, models.TicketTier.id).all()


def sold(db: Session, tier_id: int) -> int:
    return db.query(models.EventRegistration).filter(models.EventRegistration.ticket_tier_id == tier_id, models.EventRegistration.approval_status.in_(ACTIVE_STATUSES)).count()


def tier_status(tier: models.TicketTier, n_sold: int, today: date) -> str:
    if not tier.active:
        return "off"
    if tier.sales_open_on and today < tier.sales_open_on:
        return "not_yet"
    if tier.sales_close_on and today > tier.sales_close_on:
        return "ended"
    if tier.quantity is not None and n_sold >= tier.quantity:
        return "sold_out"
    return "on_sale"


def tier_out(db: Session, tier: models.TicketTier, staff: bool = False, today: Optional[date] = None) -> schemas.TierOut:
    n = sold(db, tier.id)
    return schemas.TierOut(
        id=tier.id, event_id=tier.event_id, name=tier.name, description=tier.description, price=rupees(tier.price_paise),
        student_price=None if tier.student_price_paise is None else rupees(tier.student_price_paise), quantity=tier.quantity,
        remaining=None if tier.quantity is None else max(tier.quantity - n, 0), sold=n if staff else None,
        sales_open_on=tier.sales_open_on, sales_close_on=tier.sales_close_on, active=tier.active, status=tier_status(tier, n, today or date.today()), position=tier.position,
    )


def sync_event_price(db: Session, event: models.Event) -> None:
    """An event that sells tiers shows its lowest price on cards and lists, and counts as paid when any tier costs something."""
    tiers = tiers_of(db, event.id)
    if not tiers:
        event.price_is_from = False
        return
    lowest = min(t.price_paise for t in tiers)
    event.price = rupees(lowest)
    event.is_free = all(t.price_paise == 0 for t in tiers)
    event.is_paid = bool(event.requires_registration) and not event.is_free
    event.price_is_from = any(t.price_paise != lowest for t in tiers)
    event.student_price = None


# ─── promo codes ─────────────────────────────────────────────────────────────

def find_promo(db: Session, fest_id: int, code: str) -> Optional[models.PromoCode]:
    return db.query(models.PromoCode).filter(models.PromoCode.fest_id == fest_id, models.PromoCode.code == code.strip().upper()).first()


def promo_uses(db: Session, promo_id: int) -> int:
    return db.query(models.EventRegistration).filter(models.EventRegistration.promo_code_id == promo_id, models.EventRegistration.approval_status.in_(ACTIVE_STATUSES)).count()


def promo_uses_by(db: Session, promo_id: int, user_id: int) -> int:
    return (
        db.query(models.EventRegistration).join(models.FestPass, models.FestPass.id == models.EventRegistration.fest_pass_id)
        .filter(models.EventRegistration.promo_code_id == promo_id, models.EventRegistration.approval_status.in_(ACTIVE_STATUSES), models.FestPass.user_id == user_id).count()
    )


def promo_status(db: Session, p: models.PromoCode, today: date) -> str:
    if not p.active:
        return "off"
    if p.valid_from and today < p.valid_from:
        return "not_yet"
    if p.valid_until and today > p.valid_until:
        return "expired"
    if p.max_uses is not None and promo_uses(db, p.id) >= p.max_uses:
        return "used_up"
    return "live"


def _discount(p: models.PromoCode, base: int) -> int:
    if p.kind == "percent":
        return base * int(p.value) // 100
    return min(int(p.value), base)


def check_promo(db: Session, event: models.Event, user: models.User, code: str, base: int, today: date) -> models.PromoCode:
    """The promo code, if this person may use it on this event now. Otherwise a plain reason why not."""
    p = find_promo(db, event.fest_id, code)
    if not p or not p.active:
        raise HTTPException(status_code=400, detail="That code is not valid")
    if base <= 0:
        raise HTTPException(status_code=400, detail="This ticket is free, so a code is not needed")
    if p.valid_from and today < p.valid_from:
        raise HTTPException(status_code=400, detail=f"That code can be used from {p.valid_from.strftime('%d %b %Y').lstrip('0')}")
    if p.valid_until and today > p.valid_until:
        raise HTTPException(status_code=400, detail="That code has expired")
    if p.event_ids is not None and event.id not in p.event_ids:
        raise HTTPException(status_code=400, detail="That code does not work for this event")
    if p.students_only and not user.is_student_verified:
        raise HTTPException(status_code=400, detail="That code is for verified students")
    if p.max_uses is not None and promo_uses(db, p.id) >= p.max_uses:
        raise HTTPException(status_code=400, detail="That code has been used up")
    if promo_uses_by(db, p.id, user.id) >= p.per_user_limit:
        raise HTTPException(status_code=400, detail="You have already used that code" if p.per_user_limit == 1 else f"You can use that code {p.per_user_limit} times, and you have")
    return p


# ─── the quote ───────────────────────────────────────────────────────────────

def quote(db: Session, event: models.Event, user: models.User, tier_id: Optional[int], code: Optional[str], today: Optional[date] = None) -> Quote:
    """The price this person would pay, or a plain reason they cannot buy. Does not change anything."""
    today = today or date.today()
    tiers = tiers_of(db, event.id)
    tier = None
    if tiers:
        if tier_id is None:
            raise HTTPException(status_code=400, detail="Choose which ticket you want")
        tier = next((t for t in tiers if t.id == tier_id), None)
        if tier is None:
            raise HTTPException(status_code=400, detail="That ticket is not on offer for this event")
        status = tier_status(tier, sold(db, tier.id), today)
        if status != "on_sale":
            raise HTTPException(status_code=400, detail={"not_yet": f"{tier.name} tickets are not on sale yet", "ended": f"{tier.name} tickets are no longer on sale", "sold_out": f"{tier.name} tickets are sold out"}.get(status, "That ticket is not available"))
        base = tier.student_price_paise if (user.is_student_verified and tier.student_price_paise is not None) else tier.price_paise
    elif tier_id is not None:
        raise HTTPException(status_code=400, detail="This event does not sell different tickets")
    else:
        if event.is_paid:
            base = int(round((event.student_price if (user.is_student_verified and event.student_price is not None) else (event.price or 0.0)) * 100))
        else:
            base = 0
    promo = None
    discount = 0
    if code and code.strip():
        promo = check_promo(db, event, user, code, base, today)
        discount = _discount(promo, base)
    return Quote(tier=tier, base_paise=base, discount_paise=discount, promo=promo)


def quote_out(q: Quote) -> schemas.QuoteOut:
    return schemas.QuoteOut(
        tier_id=q.tier.id if q.tier else None, tier_name=q.tier.name if q.tier else None, price=rupees(q.base_paise), discount=rupees(q.discount_paise), total=rupees(q.total_paise),
        promo_description=(q.promo.description or f"{q.promo.code}") if q.promo else None, free=q.total_paise == 0,
    )
