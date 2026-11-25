"""
Online payments, in one place.

A paid registration made while the gateway is on is created *awaiting payment*: it holds its seat for 30 minutes, the student
pays at the gateway, and the registration is confirmed when the gateway says the money arrived (we ask the gateway ourselves, we never
trust the browser). A hold that runs out frees the seat. Money goes back through the gateway: on its own when a student cancels in time
or the committee turns someone down, and by the committee's hand at any other time. With the gateway off (no keys) none of this
happens and paid events are confirmed at once as before.
"""

import os
import re
import secrets
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import cashfree, models, notices, waitlist
from app.money import rupees, to_paise

HOLD_MINUTES = 30        # a registration waiting for payment keeps its seat this long
CHECKOUT_MINUTES = 20    # one attempt at the gateway stays open this long


def enabled() -> bool:
    return cashfree.client() is not None


def hold_until() -> datetime:
    return datetime.utcnow() + timedelta(minutes=HOLD_MINUTES)


def _money(paise: int) -> str:
    return f"₹{paise / 100:,.2f}".replace(".00", "")


# ─── paying ──────────────────────────────────────────────────────────────────

def _phone(user: models.User, given: Optional[str]) -> str:
    digits = re.sub(r"\D", "", given or user.phone or "")
    digits = digits[-10:] if len(digits) >= 10 else digits
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        raise HTTPException(status_code=400, detail="Add a mobile number (10 digits) so the payment service can send your receipt")
    return digits


def _urls(payment: models.Payment) -> tuple:
    site = os.getenv("SITE_URL", "http://localhost:3000").rstrip("/")
    api = os.getenv("PUBLIC_API_URL", "").rstrip("/")
    return f"{site}/payments/return?order_id={payment.order_id}", (f"{api}/api/payments/cashfree/webhook" if api.startswith("https://") else None)


def _open_attempt(db: Session, **match) -> Optional[models.Payment]:
    """A not-yet-finished attempt for the same thing, if the gateway still has it open."""
    gw = cashfree.client()
    cutoff = datetime.utcnow() - timedelta(minutes=CHECKOUT_MINUTES)
    for p in db.query(models.Payment).filter_by(status="created", **match).order_by(models.Payment.id.desc()).all():
        if p.created_at and p.created_at < cutoff:
            p.status = "expired"
            continue
        try:
            state = sync(db, p)
        except cashfree.GatewayError:
            continue
        if state == "created" and p.session_id:
            return p
    return None


def start_checkout(db: Session, user: models.User, fest_id: int, purpose: str, amount_paise: int, description: str, phone: Optional[str], **target) -> models.Payment:
    """Open an order at the gateway for this person to pay (or reuse the one still open). The caller commits."""
    gw = cashfree.client()
    if gw is None:
        raise HTTPException(status_code=400, detail="Online payment is not switched on for HiveOut yet")
    if amount_paise < 100:
        raise HTTPException(status_code=400, detail="There is nothing to pay")
    existing = _open_attempt(db, user_id=user.id, purpose=purpose, amount_paise=amount_paise, **target)
    if existing:
        return existing
    payment = models.Payment(order_id="hv" + secrets.token_hex(10), fest_id=fest_id, user_id=user.id, purpose=purpose, description=description[:200], amount_paise=amount_paise, status="created", **target)
    db.add(payment)
    db.flush()
    return_url, notify_url = _urls(payment)
    try:
        order = gw.create_order(payment.order_id, rupees(amount_paise), f"u{user.id}", user.name or "HiveOut user", user.email or "", _phone(user, phone), return_url, notify_url, description, CHECKOUT_MINUTES)
    except cashfree.GatewayError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    payment.session_id = order.get("payment_session_id")
    return payment


# ─── hearing back from the gateway ───────────────────────────────────────────

def sync(db: Session, payment: models.Payment) -> str:
    """Ask the gateway what became of this order and act on it. Safe to call again and again. Returns the payment's status."""
    gw = cashfree.client()
    if gw is None or payment.status in ("failed", "expired"):
        return payment.status
    if payment.status == "paid":
        if payment.applied_at is None:
            apply(db, payment)
        return "paid"
    order = gw.get_order(payment.order_id)
    state = (order.get("order_status") or "").upper()
    if state == "PAID":
        done = next((x for x in gw.get_payments(payment.order_id) if (x.get("payment_status") or "").upper() == "SUCCESS"), {})
        payment.status, payment.paid_at = "paid", datetime.utcnow()
        payment.gateway_payment_id = str(done.get("cf_payment_id") or "")[:60] or None
        group = done.get("payment_group")
        payment.method = str(group)[:40] if group else None
        apply(db, payment)
    elif state in ("EXPIRED", "TERMINATED", "TERMINATION_REQUESTED"):
        payment.status = "expired" if state == "EXPIRED" else "failed"
    return payment.status


def apply(db: Session, payment: models.Payment) -> None:
    """The money is in: confirm what it paid for. Idempotent."""
    if payment.applied_at is not None:
        return
    now = datetime.utcnow()
    if payment.purpose == "registration":
        reg = db.get(models.EventRegistration, payment.registration_id) if payment.registration_id else None
        if reg is not None and (not reg.fest_pass or reg.fest_pass.user_id != payment.user_id or reg.event_id != payment.event_id):
            reg = None   # the id now belongs to someone else's registration (ids can be reused): this one's seat is gone
        title = payment.event_title or "the event"
        if reg is not None and reg.awaiting_payment:
            reg.payment_status, reg.hold_expires_at = models.RegPaymentStatusEnum.paid, None
            notices.notify(db, payment.user_id, "payment", f"Payment received: {title}", f"We received {_money(payment.amount_paise)} for {title}. You are registered.")
        else:
            # The seat was released while they paid, or they paid twice: give the money back rather than keep it
            why = "Your seat was released before the payment arrived" if reg is None else "You had already paid for this"
            payment.applied_at = now
            refund_payment(db, payment, payment.amount_paise, why, None)
            return
    elif payment.purpose == "contingent_fee":
        db.add(models.FeePayment(fest_id=payment.fest_id, contingent_id=payment.contingent_id, amount_paise=payment.amount_paise, received_on=date.today(), method="Online",
                                 reference=(payment.gateway_payment_id or payment.order_id)[:100], note="Paid online through HiveOut", recorded_by_id=None))
        c = db.get(models.Contingent, payment.contingent_id)
        if c is not None:
            notices.notify(db, c.leader_user_id, "contingent", "We received your payment", f"Your payment of {_money(payment.amount_paise)} went through and is on your statement.")
    payment.applied_at = now


# ─── refunds ─────────────────────────────────────────────────────────────────

def refundable_paise(payment: models.Payment) -> int:
    return max((payment.amount_paise if payment.status == "paid" else 0) - payment.refunded_paise, 0)


def refund_payment(db: Session, payment: models.Payment, amount_paise: int, reason: str, by_user_id: Optional[int]) -> models.Refund:
    """Send money back through the gateway. A failure is recorded on the refund, not raised, so cancelling a registration never gets stuck on it."""
    gw = cashfree.client()
    limit = refundable_paise(payment)
    refund = models.Refund(payment_id=payment.id, ref="rf" + secrets.token_hex(8), amount_paise=amount_paise, status="pending", reason=reason[:200], by_user_id=by_user_id)
    db.add(refund)
    db.flush()
    if gw is None:
        refund.status, refund.note = "failed", "Online payment is not switched on"
    elif amount_paise < 100 or amount_paise > limit:
        refund.status, refund.note = "failed", "That amount cannot be refunded"
    else:
        try:
            out = gw.create_refund(payment.order_id, refund.ref, rupees(amount_paise), reason)
            state = (out.get("refund_status") or "").upper()
            refund.status = "done" if state == "SUCCESS" else "failed" if state in ("CANCELLED", "FAILED") else "pending"
        except cashfree.GatewayError as exc:
            refund.status, refund.note = "failed", str(exc)[:300]
    title = payment.event_title or payment.description or "your payment"
    if refund.status != "failed":
        notices.notify(db, payment.user_id, "payment", f"Refund on its way: {title}", f"{_money(amount_paise)} is being sent back to you ({reason}). It reaches your account in 5 to 7 working days.")
    return refund


def check_refunds(db: Session, payment: models.Payment) -> None:
    """Bring pending refunds up to date with the gateway."""
    gw = cashfree.client()
    if gw is None:
        return
    for r in payment.refunds:
        if r.status == "pending":
            try:
                state = (gw.get_refund(payment.order_id, r.ref).get("refund_status") or "").upper()
            except cashfree.GatewayError:
                continue
            if state == "SUCCESS":
                r.status = "done"
            elif state in ("CANCELLED", "FAILED"):
                r.status, r.note = "failed", "The payment service could not send this refund"


def payments_of(db: Session, reg: models.EventRegistration, status: str):
    """The payments made for this very registration. Ids can be reused once a registration is deleted, so the payer, the event and the time must match too."""
    q = db.query(models.Payment).filter(models.Payment.purpose == "registration", models.Payment.registration_id == reg.id, models.Payment.event_id == reg.event_id, models.Payment.status == status)
    if reg.fest_pass:
        q = q.filter(models.Payment.user_id == reg.fest_pass.user_id)
    if reg.created_at:
        q = q.filter(models.Payment.created_at >= reg.created_at.replace(tzinfo=None) - timedelta(seconds=5))
    return q


def paid_payment_for(db: Session, reg: models.EventRegistration) -> Optional[models.Payment]:
    return payments_of(db, reg, "paid").order_by(models.Payment.id.desc()).first()


def refund_for_registration(db: Session, reg: models.EventRegistration, reason: str, by_user_id: Optional[int] = None, eligible: bool = True) -> Optional[models.Refund]:
    """Give back what this registration paid online, if it paid online and may be refunded. Call it before the registration is deleted."""
    if not eligible:
        return None
    p = paid_payment_for(db, reg)
    if p is None or refundable_paise(p) <= 0:
        return None
    return refund_payment(db, p, refundable_paise(p), reason, by_user_id)


def cancel_refund_allowed(db: Session, event: models.Event) -> bool:
    """Does this fest refund a student who cancels now?"""
    from app import finance
    fest = db.get(models.Fest, event.fest_id)
    s = finance.get_settings(db, fest) if fest else None
    if s is not None and not s.refund_on_cancel:
        return False
    cutoff = timedelta(days=(s.refund_cutoff_days if s is not None else 0) or 0)
    return datetime.now() < event.date - cutoff


# ─── holds that ran out ──────────────────────────────────────────────────────

def remove_registration(db: Session, reg: models.EventRegistration, reason: str, refund: bool = True, by_user_id: Optional[int] = None, eligible: bool = True) -> List[models.EventRegistration]:
    """Take a registration away (a team's leader leaving takes the whole team). Refunds what was paid online. Returns what was removed. Does not commit."""
    team, uid = reg.team, (reg.fest_pass.user_id if reg.fest_pass else None)
    breaks_team = team is not None and team.leader_user_id == uid
    victims = list(team.registrations) if breaks_team else [reg]
    for r in victims:
        if refund:
            refund_for_registration(db, r, reason, by_user_id, eligible)
        db.delete(r)
    db.flush()
    if breaks_team:
        db.delete(team)
        db.flush()
    return victims


def release_expired(db: Session, event: Optional[models.Event] = None, fest_id: Optional[int] = None) -> int:
    """Free the seats of registrations whose payment never came. A payment made at the last moment still counts. Returns how many were released."""
    if not enabled():
        return 0
    q = db.query(models.EventRegistration).filter(models.EventRegistration.payment_status == models.RegPaymentStatusEnum.unpaid, models.EventRegistration.amount_due > 0,
                                                  models.EventRegistration.hold_expires_at.isnot(None), models.EventRegistration.hold_expires_at < datetime.utcnow())
    if event is not None:
        q = q.filter(models.EventRegistration.event_id == event.id)
    elif fest_id is not None:
        q = q.join(models.Event, models.Event.id == models.EventRegistration.event_id).filter(models.Event.fest_id == fest_id)
    released, events = 0, {}
    for reg in q.all():
        if db.get(models.EventRegistration, reg.id) is None:
            continue   # went with its team a moment ago
        for p in payments_of(db, reg, "created").all():
            try:
                sync(db, p)
            except cashfree.GatewayError:
                pass
        db.flush()
        db.refresh(reg)
        if not reg.awaiting_payment:
            continue
        who, ev = reg.fest_pass.user_id if reg.fest_pass else None, reg.event
        remove_registration(db, reg, "Your seat was released because the payment did not arrive in time")
        if who:
            notices.notify(db, who, "payment", f"Your seat in {ev.title} was released", "The payment did not arrive within 30 minutes, so the seat went back. You can register again if there is room.")
        events[ev.id] = ev
        released += 1
    for ev in events.values():
        waitlist.promote(db, ev)
    return released
