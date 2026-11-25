"""
What a visiting college owes, worked out from what it has actually done: its registration, its people, the events it entered
and the place it was given to stay, plus any lines the committee added by hand. Nothing is stored as a total, so the statement
always matches the facts, and changing an entry or an allocation changes the bill.
"""

from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session

from app import models, schemas
from app.money import rupees


def settings_row(db: Session, fest: models.Fest) -> models.ContingentSettings:
    row = db.query(models.ContingentSettings).filter(models.ContingentSettings.fest_id == fest.id).first()
    if not row:
        row = models.ContingentSettings(fest_id=fest.id)
        db.add(row)
        db.flush()
    return row


def label(c: models.Contingent) -> str:
    return c.name or c.college_name


def stay_fee_paise(request: models.AccommodationRequest) -> int:
    """People x nights x each place's price per person per night, only for the people actually placed."""
    return sum(a.people * request.nights * (a.option.fee_per_night_paise or 0) for a in request.allocations if a.option)


def entry_fee_paise(entry: models.ContingentEntry) -> int:
    fee = entry.event.entry_fee_paise or 0
    return fee * (len(entry.members) if entry.event.entry_fee_per == "participant" else 1)


def statement(db: Session, fest: models.Fest, c: models.Contingent) -> schemas.FeeStatement:
    s = settings_row(db, fest)
    lines: List[schemas.FeeLine] = []
    if s.registration_fee_paise:
        lines.append(schemas.FeeLine(kind="registration", label="Registration", quantity=1, unit=rupees(s.registration_fee_paise), amount=rupees(s.registration_fee_paise)))
    people = len(c.members)
    if s.fee_per_member_paise and people:
        lines.append(schemas.FeeLine(kind="members", label="Fee for each person on your list", quantity=people, unit=rupees(s.fee_per_member_paise), amount=rupees(s.fee_per_member_paise * people)))
    entries = db.query(models.ContingentEntry).filter(models.ContingentEntry.contingent_id == c.id, models.ContingentEntry.status == "confirmed").order_by(models.ContingentEntry.id).all()
    for e in entries:
        fee = e.event.entry_fee_paise or 0
        if fee:
            qty = len(e.members) if e.event.entry_fee_per == "participant" else 1
            who = f"{qty} participant{'s' if qty != 1 else ''}" if e.event.entry_fee_per == "participant" else "entry"
            lines.append(schemas.FeeLine(kind="entry", label=f"{e.event.title} ({who})", quantity=qty, unit=rupees(fee), amount=rupees(fee * qty)))
    request = db.query(models.AccommodationRequest).filter(models.AccommodationRequest.contingent_id == c.id, models.AccommodationRequest.status == "allocated").first()
    if request:
        for a in sorted(request.allocations, key=lambda x: x.id):
            fee = a.option.fee_per_night_paise if a.option else 0
            if fee and request.nights:
                lines.append(schemas.FeeLine(kind="stay", label=f"{a.option.name}: {a.people} {a.grp} for {request.nights} night{'s' if request.nights != 1 else ''}", quantity=a.people * request.nights, unit=rupees(fee), amount=rupees(fee * a.people * request.nights)))
    for adj in db.query(models.FeeAdjustment).filter(models.FeeAdjustment.contingent_id == c.id).order_by(models.FeeAdjustment.id).all():
        lines.append(schemas.FeeLine(kind="adjustment", label=adj.label, quantity=1, unit=rupees(adj.amount_paise), amount=rupees(adj.amount_paise), adjustment_id=adj.id))

    total = round(sum(l.amount for l in lines), 2)
    pays = db.query(models.FeePayment).filter(models.FeePayment.contingent_id == c.id).order_by(models.FeePayment.received_on, models.FeePayment.id).all()
    paid = round(sum(rupees(p.amount_paise) for p in pays), 2)
    balance = round(total - paid, 2)
    status = "no_fees" if total == 0 and paid == 0 else "paid" if balance == 0 else "overpaid" if balance < 0 else "unpaid" if paid == 0 else "part"
    return schemas.FeeStatement(
        contingent_id=c.id, contingent_label=label(c), college_name=c.college_name, lines=lines, total=total, paid=paid, balance=balance, status=status,
        payments=[schemas.FeePaymentOut(id=p.id, amount=rupees(p.amount_paise), received_on=p.received_on, method=p.method, reference=p.reference, note=p.note) for p in pays],
        due_on=s.fees_due_on, instructions=s.fee_instructions,
    )
