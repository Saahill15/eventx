"""
A fest's money: what it plans to spend, what it has been asked to spend, and what is coming in.

Amounts are whole paise in the database and rupees in the API. Nothing here is a stored total: budget lines, income and the
summary are all worked out from the expenses and payments themselves, so they always agree with them.

An expense moves pending -> approved -> paid, or pending -> rejected. A request from a member who paid out of their own pocket
is owed back to them until the committee marks it paid (which then means "reimbursed").
"""

from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app import contingent_money, models, schemas
from app.money import rupees

# The usual categories. Only a starting point: a fest can rename, delete or add its own.
USUAL_CATEGORIES = [
    ("Sponsorship", "income"), ("Ticket and registration income", "income"), ("College grant", "income"), ("Stalls and merchandise", "income"), ("Other income", "income"),
    ("Venue and infrastructure", "expense"), ("Logistics", "expense"), ("Marketing and design", "expense"), ("Prizes and awards", "expense"), ("Food and hospitality", "expense"),
    ("Sound, lights and tech", "expense"), ("Security and medical", "expense"), ("Printing and stationery", "expense"), ("Travel", "expense"), ("Contingency", "expense"),
]
COMMITTED = ("approved", "paid")


def get_settings(db: Session, fest: models.Fest) -> models.FinanceSettings:
    row = db.query(models.FinanceSettings).filter(models.FinanceSettings.fest_id == fest.id).first()
    if not row:
        row = models.FinanceSettings(fest_id=fest.id, auto_approve_below_paise=0, receipt_required_above_paise=100000)
        db.add(row)
        db.flush()
    return row


def settings_out(s: models.FinanceSettings) -> schemas.FinanceSettingsOut:
    return schemas.FinanceSettingsOut(auto_approve_below=rupees(s.auto_approve_below_paise), receipt_required_above=None if s.receipt_required_above_paise is None else rupees(s.receipt_required_above_paise))


def category_out(db: Session, c: models.FinanceCategory) -> schemas.CategoryOut:
    used = bool(
        db.query(models.BudgetLine.id).filter(models.BudgetLine.category_id == c.id).first()
        or db.query(models.Expense.id).filter(models.Expense.category_id == c.id).first()
        or db.query(models.IncomeItem.id).filter(models.IncomeItem.category_id == c.id).first()
    )
    return schemas.CategoryOut(id=c.id, name=c.name, kind=c.kind, position=c.position, used=used)


def spent_by_line(db: Session, fest_id: int) -> Dict[int, Dict[str, int]]:
    out: Dict[int, Dict[str, int]] = {}
    for line_id, status, amount in db.query(models.Expense.budget_line_id, models.Expense.status, models.Expense.amount_paise).filter(models.Expense.fest_id == fest_id, models.Expense.budget_line_id.isnot(None)).all():
        t = out.setdefault(line_id, {"pending": 0, "committed": 0, "paid": 0})
        if status == "pending":
            t["pending"] += amount
        elif status in COMMITTED:
            t["committed"] += amount
            if status == "paid":
                t["paid"] += amount
    return out


def line_out(line: models.BudgetLine, totals: Dict[int, Dict[str, int]]) -> schemas.BudgetLineOut:
    t = totals.get(line.id, {"pending": 0, "committed": 0, "paid": 0})
    return schemas.BudgetLineOut(
        id=line.id, category_id=line.category_id, category_name=line.category.name, title=line.title, planned=rupees(line.planned_paise), committee_team_id=line.committee_team_id,
        team_name=line.team.name if line.team else None, notes=line.notes, pending=rupees(t["pending"]), committed=rupees(t["committed"]), paid=rupees(t["paid"]),
        remaining=rupees(line.planned_paise - t["committed"]), over_budget=t["committed"] > line.planned_paise,
    )


def expense_out(e: models.Expense) -> schemas.ExpenseOut:
    return schemas.ExpenseOut(
        id=e.id, title=e.title, amount=rupees(e.amount_paise), spent_on=e.spent_on, status=e.status, budget_line_id=e.budget_line_id, line_title=e.budget_line.title if e.budget_line else None,
        category_id=e.category_id, category_name=e.category.name, vendor=e.vendor, notes=e.notes, receipts=list(e.receipts or []), requested_by_id=e.requested_by_id,
        requested_by_name=e.requested_by.name if e.requested_by else None, out_of_pocket_by=e.paid_by.user_name if e.paid_by else None,
        decided_by_name=e.decided_by.name if e.decided_by else None, decided_at=e.decided_at, decision_note=e.decision_note, paid_on=e.paid_on, paid_note=e.paid_note,
        created_at=e.created_at, auto_approved=e.status in COMMITTED and e.decided_by_id is None and e.decided_at is not None,
    )


def income_out(i: models.IncomeItem, today) -> schemas.IncomeOut:
    received = sum(p.amount_paise for p in i.payments)
    outstanding = i.expected_paise - received
    status = "received" if received >= i.expected_paise and i.expected_paise > 0 or (i.expected_paise == 0 and received > 0) else "partial" if received else "pledged"
    if status != "received" and i.due_on and today > i.due_on:
        status = "overdue"
    return schemas.IncomeOut(
        id=i.id, category_id=i.category_id, category_name=i.category.name, title=i.title, source=i.source, sponsor_id=i.sponsor_id, sponsor_name=i.sponsor.name if i.sponsor else None,
        expected=rupees(i.expected_paise), received=rupees(received), outstanding=rupees(max(outstanding, 0)), status=status, due_on=i.due_on, notes=i.notes,
        payments=[schemas.IncomePaymentOut(id=p.id, amount=rupees(p.amount_paise), received_on=p.received_on, method=p.method, note=p.note) for p in i.payments],
    )


def registration_income_paise(db: Session, fest_id: int) -> int:
    """What students paid through HiveOut for paid events (approved registrations only)."""
    rows = (
        db.query(models.EventRegistration.amount_due)
        .join(models.Event, models.Event.id == models.EventRegistration.event_id)
        .filter(models.Event.fest_id == fest_id, models.EventRegistration.payment_status == models.RegPaymentStatusEnum.paid, models.EventRegistration.approval_status == models.RegApprovalStatusEnum.approved)
        .all()
    )
    return int(round(sum((a or 0.0) for (a,) in rows) * 100))


def summary(db: Session, fest: models.Fest, today) -> schemas.FinanceSummary:
    cats = {c.id: c for c in db.query(models.FinanceCategory).filter(models.FinanceCategory.fest_id == fest.id).all()}
    lines = db.query(models.BudgetLine).filter(models.BudgetLine.fest_id == fest.id).all()
    expenses = db.query(models.Expense).filter(models.Expense.fest_id == fest.id).all()
    incomes = db.query(models.IncomeItem).filter(models.IncomeItem.fest_id == fest.id).all()
    totals = spent_by_line(db, fest.id)

    pending = sum(e.amount_paise for e in expenses if e.status == "pending")
    approved = sum(e.amount_paise for e in expenses if e.status == "approved")
    paid = sum(e.amount_paise for e in expenses if e.status == "paid")
    planned = sum(l.planned_paise for l in lines)
    income_expected = sum(i.expected_paise for i in incomes)
    income_received = sum(sum(p.amount_paise for p in i.payments) for i in incomes)
    registration = registration_income_paise(db, fest.id)
    fees_received = fees_due = 0
    for c in db.query(models.Contingent).filter(models.Contingent.fest_id == fest.id, models.Contingent.status == "approved").all():
        st = contingent_money.statement(db, fest, c)
        fees_received += int(round(st.paid * 100))
        fees_due += int(round(st.total * 100))

    by_cat: Dict[int, schemas.CategoryTotal] = {}
    for c in cats.values():
        by_cat[c.id] = schemas.CategoryTotal(category_id=c.id, name=c.name, kind=c.kind)
    for l in lines:
        t = totals.get(l.id, {"committed": 0, "paid": 0})
        row = by_cat[l.category_id]
        row.planned += rupees(l.planned_paise)
    for e in expenses:
        if e.status in COMMITTED:
            row = by_cat[e.category_id]
            row.committed = round(row.committed + rupees(e.amount_paise), 2)
            if e.status == "paid":
                row.paid = round(row.paid + rupees(e.amount_paise), 2)
    for i in incomes:
        row = by_cat[i.category_id]
        row.planned = round(row.planned + rupees(i.expected_paise), 2)
        row.committed = round(row.committed + rupees(sum(p.amount_paise for p in i.payments)), 2)
    for row in by_cat.values():
        row.planned = round(row.planned, 2)

    teams: Dict[Optional[int], schemas.TeamTotal] = {}
    for l in lines:
        key = l.committee_team_id
        row = teams.setdefault(key, schemas.TeamTotal(team_id=key, name=l.team.name if l.team else "No team"))
        row.planned = round(row.planned + rupees(l.planned_paise), 2)
        t = totals.get(l.id, {"committed": 0, "paid": 0})
        row.committed = round(row.committed + rupees(t["committed"]), 2)
        row.paid = round(row.paid + rupees(t["paid"]), 2)

    owed: Dict[int, schemas.OwedToMember] = {}
    for e in expenses:
        if e.status == "approved" and e.paid_by_member_id and e.paid_by:
            o = owed.setdefault(e.paid_by_member_id, schemas.OwedToMember(member_id=e.paid_by_member_id, name=e.paid_by.user_name or "A member", amount=0, expenses=0))
            o.amount = round(o.amount + rupees(e.amount_paise), 2)
            o.expenses += 1

    committed = approved + paid
    cash_in = income_received + registration + fees_received
    expected_income = income_expected + registration + fees_due
    unbudgeted = sum(e.amount_paise for e in expenses if e.status in COMMITTED and e.budget_line_id is None)
    return schemas.FinanceSummary(
        income_expected=rupees(income_expected), income_received=rupees(income_received), registration_income=rupees(registration), college_fees_due=rupees(fees_due), college_fees_received=rupees(fees_received),
        budget_planned=rupees(planned), pending=rupees(pending), approved=rupees(approved), paid=rupees(paid), committed=rupees(committed),
        cash_in=rupees(cash_in), cash_out=rupees(paid), cash_position=rupees(cash_in - paid), expected_income=rupees(expected_income), projected_net=rupees(expected_income - max(planned, committed)),
        pending_requests=sum(1 for e in expenses if e.status == "pending"), over_budget_lines=sum(1 for l in lines if totals.get(l.id, {}).get("committed", 0) > l.planned_paise), unbudgeted=rupees(unbudgeted),
        by_category=sorted(by_cat.values(), key=lambda r: (r.kind != "income", r.name.lower())), by_team=sorted(teams.values(), key=lambda r: r.name.lower()), owed_to_members=sorted(owed.values(), key=lambda r: -r.amount),
    )
