"""
What visiting colleges pay.

The committee decides the fest's charges (a registration fee, a fee for each person, a fee on each event entry, a price per night
for accommodation) or charges nothing. A contingent's statement is worked out from what it has done, plus lines added by hand,
less the payments the committee has recorded. Online payment is not part of this yet: colleges pay as the fest's instructions say.

  GET|PUT  /api/fests/{slug}/fees/settings                  the fest's charges and how to pay (committee)
  GET      /api/fests/{slug}/fees/mine                      a leader's own statement
  GET      /api/fests/{slug}/fees                           every contingent's totals (committee)
  GET      /api/fests/{slug}/fees/export                    the same as a spreadsheet (CSV)
  GET      /api/fests/{slug}/fees/{contingent_id}           one statement (the committee, or that contingent's leaders)
  POST     /api/fests/{slug}/fees/{contingent_id}/payments  record money received; DELETE .../fees/payments/{id}
  POST     /api/fests/{slug}/fees/{contingent_id}/adjustments  add a line (late fee, waiver); DELETE .../fees/adjustments/{id}
"""

import csv
import io
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app import contingent_money as money
from app import models, notices, schemas
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.money import rupees, to_paise
from app.permissions import is_fest_staff
from app.routes.contingents import _fest, _role

router = APIRouter()


def _staff(db: Session, fest: models.Fest, user) -> None:
    if not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can do that")


def _settings_out(s: models.ContingentSettings) -> schemas.FeeSettingsOut:
    return schemas.FeeSettingsOut(registration_fee=rupees(s.registration_fee_paise), fee_per_member=rupees(s.fee_per_member_paise), fee_instructions=s.fee_instructions, fees_due_on=s.fees_due_on)


def _contingent(db: Session, fest: models.Fest, contingent_id: int) -> models.Contingent:
    c = db.query(models.Contingent).filter(models.Contingent.id == contingent_id, models.Contingent.fest_id == fest.id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contingent not found")
    return c


@router.get("/{slug}/fees/settings", response_model=schemas.FeeSettingsOut)
def get_settings(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    out = _settings_out(money.settings_row(db, fest))
    db.commit()
    return out


@router.put("/{slug}/fees/settings", response_model=schemas.FeeSettingsOut)
def put_settings(slug: str, data: schemas.FeeSettingsIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    s = money.settings_row(db, fest)
    u = data.model_dump(exclude_unset=True)
    if u.get("registration_fee") is not None:
        s.registration_fee_paise = to_paise(u["registration_fee"])
    if u.get("fee_per_member") is not None:
        s.fee_per_member_paise = to_paise(u["fee_per_member"])
    if "fee_instructions" in u:
        s.fee_instructions = u["fee_instructions"] or None
    if "fees_due_on" in u:
        s.fees_due_on = u["fees_due_on"]
    db.commit()
    return _settings_out(s)


@router.get("/{slug}/fees/mine", response_model=Optional[schemas.FeeStatement])
def my_statement(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    rows = db.query(models.Contingent).filter(models.Contingent.fest_id == fest.id, models.Contingent.status.in_(["pending", "approved"])).order_by(models.Contingent.id).all()
    mine = next((c for c in rows if _role(c, user)), None)
    if not mine:
        return None
    out = money.statement(db, fest, mine)
    db.commit()
    return out


def _summary(db: Session, fest: models.Fest) -> schemas.FeeSummary:
    rows = []
    for c in db.query(models.Contingent).filter(models.Contingent.fest_id == fest.id, models.Contingent.status == "approved").order_by(models.Contingent.id).all():
        st = money.statement(db, fest, c)
        rows.append(schemas.FeeSummaryRow(contingent_id=c.id, contingent_label=st.contingent_label, college_name=c.college_name, total=st.total, paid=st.paid, balance=st.balance, status=st.status))
    return schemas.FeeSummary(total=round(sum(r.total for r in rows), 2), paid=round(sum(r.paid for r in rows), 2), balance=round(sum(r.balance for r in rows), 2), rows=rows)


@router.get("/{slug}/fees", response_model=schemas.FeeSummary)
def summary(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    out = _summary(db, fest)
    db.commit()
    return out


def _cell(v) -> str:
    """Neutralise spreadsheet formulas in text a college typed."""
    text = "" if v is None else str(v)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@router.get("/{slug}/fees/export")
def export(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Contingent", "College", "Total due (INR)", "Paid (INR)", "Balance (INR)", "Status"])
    for r in _summary(db, fest).rows:
        w.writerow([_cell(r.contingent_label), _cell(r.college_name), f"{r.total:.2f}", f"{r.paid:.2f}", f"{r.balance:.2f}", r.status])
    db.commit()
    return Response(content=buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{fest.slug}-fees.csv"'})


@router.get("/{slug}/fees/{contingent_id}", response_model=schemas.FeeStatement)
def statement(slug: str, contingent_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    c = _contingent(db, fest, contingent_id)
    if not _role(c, user) and not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only this contingent's leaders and the committee can see its fees")
    out = money.statement(db, fest, c)
    db.commit()
    return out


@router.post("/{slug}/fees/{contingent_id}/payments", response_model=schemas.FeeStatement, status_code=status.HTTP_201_CREATED)
def record_payment(slug: str, contingent_id: int, data: schemas.FeePaymentIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    c = _contingent(db, fest, contingent_id)
    db.add(models.FeePayment(fest_id=fest.id, contingent_id=c.id, amount_paise=to_paise(data.amount), received_on=data.received_on or date.today(), method=data.method or None,
                             reference=data.reference or None, note=data.note or None, recorded_by_id=user.id))
    notices.notify(db, c.leader_user_id, "contingent", "We received your payment", f"The committee recorded a payment of ₹{data.amount:,.2f} from {money.label(c)}.")
    db.commit()
    return money.statement(db, fest, c)


@router.delete("/{slug}/fees/payments/{payment_id}", response_model=schemas.FeeStatement)
def delete_payment(slug: str, payment_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    p = db.query(models.FeePayment).filter(models.FeePayment.id == payment_id, models.FeePayment.fest_id == fest.id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    c = _contingent(db, fest, p.contingent_id)
    db.delete(p)
    db.commit()
    return money.statement(db, fest, c)


@router.post("/{slug}/fees/{contingent_id}/adjustments", response_model=schemas.FeeStatement, status_code=status.HTTP_201_CREATED)
def add_adjustment(slug: str, contingent_id: int, data: schemas.FeeAdjustmentIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    c = _contingent(db, fest, contingent_id)
    db.add(models.FeeAdjustment(fest_id=fest.id, contingent_id=c.id, label=data.label, amount_paise=to_paise(data.amount), created_by_id=user.id))
    db.commit()
    return money.statement(db, fest, c)


@router.delete("/{slug}/fees/adjustments/{adjustment_id}", response_model=schemas.FeeStatement)
def delete_adjustment(slug: str, adjustment_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    a = db.query(models.FeeAdjustment).filter(models.FeeAdjustment.id == adjustment_id, models.FeeAdjustment.fest_id == fest.id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Line not found")
    c = _contingent(db, fest, a.contingent_id)
    db.delete(a)
    db.commit()
    return money.statement(db, fest, c)
