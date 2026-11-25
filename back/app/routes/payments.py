"""
Paying online (Cashfree) and getting money back.

  GET   /api/payments/config                                  is online payment switched on? (public)
  POST  /api/payments/registrations/{registration_id}/checkout   open a payment for a registration that is waiting for money
  POST  /api/payments/contingents/{contingent_id}/checkout       open a payment towards a visiting college's fees (its leaders)
  POST  /api/payments/orders/{order_id}/verify                ask the gateway what became of an order, and act on it (the payer)
  POST  /api/payments/cashfree/webhook                        the gateway telling us (public, checked by its signature)
  GET   /api/payments/mine                                    the payer's own payments, with any refunds
  GET   /api/fests/{slug}/payments?status=                    every online payment of a fest (director or core team)
  POST  /api/fests/{slug}/payments/{id}/refund                send money back (director or core team)
  POST  /api/fests/{slug}/payments/{id}/refresh               bring one payment and its refunds up to date with the gateway
"""

import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import cashfree, contingent_money, models, payments, schemas
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.money import rupees, to_paise
from app.permissions import is_fest_staff
from app.routes.contingents import _role

router = APIRouter()
fest_router = APIRouter()


def _out(p: models.Payment) -> schemas.PaymentOut:
    return schemas.PaymentOut(
        id=p.id, order_id=p.order_id, purpose=p.purpose, description=p.description, user_name=p.user_name, user_email=p.user_email, event_id=p.event_id, event_title=p.event_title,
        contingent_id=p.contingent_id, amount=rupees(p.amount_paise), status=p.status, method=p.method, paid_at=p.paid_at, created_at=p.created_at,
        refunded=rupees(p.refunded_paise), refundable=rupees(payments.refundable_paise(p)),
        refunds=[schemas.RefundOut(id=r.id, amount=rupees(r.amount_paise), status=r.status, reason=r.reason, note=r.note, created_at=r.created_at) for r in p.refunds],
    )


def _result(db: Session, p: models.Payment) -> schemas.PaymentResult:
    fest = db.get(models.Fest, p.fest_id)
    return schemas.PaymentResult(status=p.status, purpose=p.purpose, amount=rupees(p.amount_paise), description=p.description, event_id=p.event_id, event_title=p.event_title,
                                 fest_slug=fest.slug if fest else None, registration_id=p.registration_id, contingent_id=p.contingent_id)


def _checkout_out(p: models.Payment) -> schemas.CheckoutOut:
    gw = cashfree.client()
    return schemas.CheckoutOut(order_id=p.order_id, payment_session_id=p.session_id or "", env=gw.env if gw else "sandbox", amount=rupees(p.amount_paise))


@router.get("/config", response_model=schemas.PaymentConfig)
def config():
    gw = cashfree.client()
    return schemas.PaymentConfig(enabled=gw is not None, env=gw.env if gw else None)


@router.post("/registrations/{registration_id}/checkout", response_model=schemas.CheckoutOut)
def pay_for_registration(registration_id: int, data: Optional[schemas.CheckoutIn] = None, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    reg = db.get(models.EventRegistration, registration_id)
    if not reg or not reg.fest_pass or reg.fest_pass.user_id != user.id:
        raise HTTPException(status_code=404, detail="Registration not found")
    payments.release_expired(db, reg.event)
    reg = db.get(models.EventRegistration, registration_id)
    if reg is None:
        db.commit()
        raise HTTPException(status_code=400, detail="Your seat was released because the payment did not arrive in time. Register again if there is room")
    if reg.approval_status == models.RegApprovalStatusEnum.rejected:
        raise HTTPException(status_code=400, detail="This registration was not approved")
    if not reg.awaiting_payment:
        raise HTTPException(status_code=400, detail="There is nothing to pay for this registration")
    event = reg.event
    payment = payments.start_checkout(db, user, event.fest_id, "registration", to_paise(reg.amount_due), f"{event.title}"[:200], data.phone if data else None, event_id=event.id, registration_id=reg.id)
    reg.hold_expires_at = max(reg.hold_expires_at or datetime.utcnow(), payments.hold_until())
    db.commit()
    return _checkout_out(payment)


@router.post("/contingents/{contingent_id}/checkout", response_model=schemas.CheckoutOut)
def pay_fees(contingent_id: int, data: Optional[schemas.FeeCheckoutIn] = None, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    c = db.get(models.Contingent, contingent_id)
    if not c or not _role(c, user):
        raise HTTPException(status_code=404, detail="Contingent not found")
    fest = db.get(models.Fest, c.fest_id)
    st = contingent_money.statement(db, fest, c)
    owed = to_paise(st.balance)
    if owed < 100:
        raise HTTPException(status_code=400, detail="Nothing is owed right now")
    amount = to_paise(data.amount) if data and data.amount else owed
    if amount > owed:
        raise HTTPException(status_code=400, detail=f"That is more than the {st.balance:,.2f} still owed")
    payment = payments.start_checkout(db, user, fest.id, "contingent_fee", amount, f"Fees for {contingent_money.label(c)}"[:200], data.phone if data else None, contingent_id=c.id)
    db.commit()
    return _checkout_out(payment)


def _mine(db: Session, order_id: str, user: models.User) -> models.Payment:
    p = db.query(models.Payment).filter(models.Payment.order_id == order_id, models.Payment.user_id == user.id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    return p


@router.post("/orders/{order_id}/verify", response_model=schemas.PaymentResult)
def verify(order_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    p = _mine(db, order_id, user)
    try:
        payments.sync(db, p)
    except cashfree.GatewayError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    db.commit()
    return _result(db, p)


@router.post("/cashfree/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    gw = cashfree.client()
    raw = await request.body()
    if gw is None or not gw.verify_webhook(raw, request.headers.get("x-webhook-signature", ""), request.headers.get("x-webhook-timestamp", "")):
        raise HTTPException(status_code=401, detail="Bad signature")
    try:
        body = json.loads(raw or b"{}")
    except ValueError:
        return {"ok": True}
    data = body.get("data") or {}
    order_id = (data.get("order") or {}).get("order_id") or (data.get("refund") or {}).get("order_id")
    p = db.query(models.Payment).filter(models.Payment.order_id == order_id).first() if order_id else None
    if p is not None:
        try:
            payments.sync(db, p)        # we ask the gateway, we do not take the message's word for it
            payments.check_refunds(db, p)
        except cashfree.GatewayError:
            raise HTTPException(status_code=502, detail="Could not check with the payment service")
        db.commit()
    return {"ok": True}


@router.get("/mine", response_model=List[schemas.PaymentOut])
def my_payments(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    rows = db.query(models.Payment).filter(models.Payment.user_id == user.id, models.Payment.status == "paid").order_by(models.Payment.id.desc()).limit(100).all()
    return [_out(p) for p in rows]


# ─── the committee's view ─────────────────────────────────────────────────────

def _fest(db: Session, slug: str) -> models.Fest:
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    return fest


def _staff(db: Session, fest: models.Fest, user: models.User) -> None:
    if not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can see its payments")


@fest_router.get("/{slug}/payments", response_model=schemas.PaymentList)
def fest_payments(slug: str, status: Optional[str] = None, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    q = db.query(models.Payment).filter(models.Payment.fest_id == fest.id)
    q = q.filter(models.Payment.status == status) if status else q.filter(models.Payment.status == "paid")
    rows = q.order_by(models.Payment.id.desc()).limit(500).all()
    paid = [p for p in rows if p.status == "paid"]
    return schemas.PaymentList(collected=rupees(sum(p.amount_paise - p.refunded_paise for p in paid)), refunded=rupees(sum(p.refunded_paise for p in paid)), count=len(rows), payments=[_out(p) for p in rows])


def _fest_payment(db: Session, fest: models.Fest, payment_id: int) -> models.Payment:
    p = db.query(models.Payment).filter(models.Payment.id == payment_id, models.Payment.fest_id == fest.id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    return p


@fest_router.post("/{slug}/payments/{payment_id}/refund", response_model=schemas.PaymentOut)
def refund(slug: str, payment_id: int, data: schemas.RefundIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    p = _fest_payment(db, fest, payment_id)
    if p.status != "paid":
        raise HTTPException(status_code=400, detail="Only a payment that went through can be refunded")
    left = payments.refundable_paise(p)
    amount = to_paise(data.amount) if data.amount else left
    if left < 100:
        raise HTTPException(status_code=400, detail="Everything has already been refunded")
    if amount < 100 or amount > left:
        raise HTTPException(status_code=400, detail=f"You can refund between ₹1 and ₹{left / 100:,.2f}")
    r = payments.refund_payment(db, p, amount, data.reason, user.id)
    db.commit()
    if r.status == "failed":
        raise HTTPException(status_code=502, detail=r.note or "The payment service could not send the refund")
    db.refresh(p)
    return _out(p)


@fest_router.post("/{slug}/payments/{payment_id}/refresh", response_model=schemas.PaymentOut)
def refresh(slug: str, payment_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    p = _fest_payment(db, fest, payment_id)
    try:
        payments.sync(db, p)
        payments.check_refunds(db, p)
    except cashfree.GatewayError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    db.commit()
    return _out(p)
