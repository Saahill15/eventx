"""
Finance: the fest's budget, spending with approvals, and money coming in.

Anyone on the committee can ask to spend money; the director and core team decide, and mark it paid. The budget, income and
the summary are for the director and core team. Every fest names its own categories and sets its own rules for what needs
approval and what needs a receipt.

  GET|PUT   /api/fests/{slug}/finance/settings                  the fest's rules for money
  GET|POST  /api/fests/{slug}/finance/categories                the fest's own categories (POST .../categories/usual for a usual set)
  PATCH|DELETE .../finance/categories/{id}
  GET       /api/fests/{slug}/finance/options                   what a member needs to file a request (categories and budget lines)
  GET|POST  /api/fests/{slug}/finance/budget                    the budget lines; PATCH|DELETE .../budget/{id}
  GET|POST  /api/fests/{slug}/finance/expenses                  spend requests (members see their own; the committee sees all)
  PATCH     .../finance/expenses/{id}                           change one (the requester while it waits; the committee until it is paid)
  POST      .../finance/expenses/{id}/approve | reject | pay | cancel;  DELETE .../expenses/{id}
  POST      /api/fests/{slug}/finance/receipts                  upload a receipt (photo or PDF)
  GET|POST  /api/fests/{slug}/finance/income                    money expected (sponsors, grants...); PATCH|DELETE .../income/{id}
  POST      .../finance/income/{id}/payments                    record money received; DELETE .../income/payments/{id}
  GET       /api/fests/{slug}/finance/summary | /export         the position, and everything as a spreadsheet
"""

import csv
import io
import secrets
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import contingent_money, finance as fin, models, notices, schemas
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.money import rupees, to_paise
from app.permissions import is_fest_member, is_fest_staff

router = APIRouter()
MAX_CATEGORIES, MAX_LINES, MAX_RECEIPT_BYTES, MAX_RECEIPTS_PER_DAY = 60, 300, 3 * 1024 * 1024, 30


# ─── helpers ──────────────────────────────────────────────────────────────────

def _fest(db: Session, slug: str) -> models.Fest:
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    return fest


def _staff(db: Session, fest: models.Fest, user) -> None:
    if not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can do that")


def _member(db: Session, fest: models.Fest, user) -> None:
    if not is_fest_member(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's committee can do that")


def _my_member(db: Session, fest: models.Fest, user) -> Optional[models.FestMember]:
    return db.query(models.FestMember).filter(models.FestMember.fest_id == fest.id, models.FestMember.user_id == user.id).first()


def _category(db: Session, fest: models.Fest, category_id: int, kind: Optional[str] = None) -> models.FinanceCategory:
    c = db.query(models.FinanceCategory).filter(models.FinanceCategory.id == category_id, models.FinanceCategory.fest_id == fest.id).first()
    if not c:
        raise HTTPException(status_code=400, detail="That category is not part of this fest")
    if kind and c.kind != kind:
        raise HTTPException(status_code=400, detail=f"“{c.name}” is an {c.kind} category. Choose an {kind} one.")
    return c


def _line(db: Session, fest: models.Fest, line_id: int) -> models.BudgetLine:
    l = db.query(models.BudgetLine).filter(models.BudgetLine.id == line_id, models.BudgetLine.fest_id == fest.id).first()
    if not l:
        raise HTTPException(status_code=404, detail="Budget line not found")
    return l


def _expense(db: Session, fest: models.Fest, expense_id: int) -> models.Expense:
    e = db.query(models.Expense).filter(models.Expense.id == expense_id, models.Expense.fest_id == fest.id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Request not found")
    return e


def _income(db: Session, fest: models.Fest, income_id: int) -> models.IncomeItem:
    i = db.query(models.IncomeItem).filter(models.IncomeItem.id == income_id, models.IncomeItem.fest_id == fest.id).first()
    if not i:
        raise HTTPException(status_code=404, detail="Income not found")
    return i


def _team_check(db: Session, fest: models.Fest, team_id: Optional[int]) -> None:
    if team_id is not None and not db.query(models.CommitteeTeam).filter(models.CommitteeTeam.id == team_id, models.CommitteeTeam.fest_id == fest.id).first():
        raise HTTPException(status_code=400, detail="That team is not part of this fest")


def _staff_ids(db: Session, fest: models.Fest) -> List[int]:
    return [m.user_id for m in db.query(models.FestMember).filter(models.FestMember.fest_id == fest.id, models.FestMember.role.in_([models.FestMemberRoleEnum.owner, models.FestMemberRoleEnum.core])).all()]


def _inr(paise: int) -> str:
    return f"₹{rupees(paise):,.2f}".replace(".00", "")


# ─── settings ─────────────────────────────────────────────────────────────────

@router.get("/{slug}/finance/settings", response_model=schemas.FinanceSettingsOut)
def get_settings(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _member(db, fest, user)
    out = fin.settings_out(fin.get_settings(db, fest))
    db.commit()
    return out


@router.put("/{slug}/finance/settings", response_model=schemas.FinanceSettingsOut)
def put_settings(slug: str, data: schemas.FinanceSettingsIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    s = fin.get_settings(db, fest)
    u = data.model_dump(exclude_unset=True)
    if u.get("auto_approve_below") is not None:
        s.auto_approve_below_paise = to_paise(u["auto_approve_below"])
    if u.get("receipts_never_needed"):
        s.receipt_required_above_paise = None
    elif u.get("receipt_required_above") is not None:
        s.receipt_required_above_paise = to_paise(u["receipt_required_above"])
    if u.get("refund_on_cancel") is not None:
        s.refund_on_cancel = u["refund_on_cancel"]
    if u.get("refund_cutoff_days") is not None:
        s.refund_cutoff_days = u["refund_cutoff_days"]
    db.commit()
    return fin.settings_out(s)


# ─── categories ───────────────────────────────────────────────────────────────

@router.get("/{slug}/finance/categories", response_model=List[schemas.CategoryOut])
def list_categories(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _member(db, fest, user)
    return [fin.category_out(db, c) for c in db.query(models.FinanceCategory).filter(models.FinanceCategory.fest_id == fest.id).order_by(models.FinanceCategory.kind.desc(), models.FinanceCategory.position, models.FinanceCategory.id).all()]


def _name_taken(db: Session, fest: models.Fest, name: str, except_id: Optional[int] = None) -> bool:
    q = db.query(models.FinanceCategory).filter(models.FinanceCategory.fest_id == fest.id, func.lower(models.FinanceCategory.name) == name.lower())
    if except_id is not None:
        q = q.filter(models.FinanceCategory.id != except_id)
    return q.first() is not None


@router.post("/{slug}/finance/categories", response_model=schemas.CategoryOut, status_code=status.HTTP_201_CREATED)
def add_category(slug: str, data: schemas.CategoryIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    n = db.query(models.FinanceCategory).filter(models.FinanceCategory.fest_id == fest.id).count()
    if n >= MAX_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"A fest can have at most {MAX_CATEGORIES} categories")
    if _name_taken(db, fest, data.name):
        raise HTTPException(status_code=400, detail="This fest already has a category with that name")
    c = models.FinanceCategory(fest_id=fest.id, name=data.name, kind=data.kind, position=n)
    db.add(c)
    db.commit()
    db.refresh(c)
    return fin.category_out(db, c)


@router.post("/{slug}/finance/categories/usual", response_model=List[schemas.CategoryOut], status_code=status.HTTP_201_CREATED)
def add_usual_categories(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """A usual set of income and expense categories to start from. Names the fest already has are skipped. All of it can be changed."""
    fest = _fest(db, slug)
    _staff(db, fest, user)
    n = db.query(models.FinanceCategory).filter(models.FinanceCategory.fest_id == fest.id).count()
    for name, kind in fin.USUAL_CATEGORIES:
        if n >= MAX_CATEGORIES:
            break
        if not _name_taken(db, fest, name):
            db.add(models.FinanceCategory(fest_id=fest.id, name=name, kind=kind, position=n))
            n += 1
    db.commit()
    return list_categories(slug, db, user)


@router.patch("/{slug}/finance/categories/{category_id}", response_model=schemas.CategoryOut)
def rename_category(slug: str, category_id: int, data: schemas.CategoryUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    c = _category(db, fest, category_id)
    if _name_taken(db, fest, data.name, except_id=c.id):
        raise HTTPException(status_code=400, detail="This fest already has a category with that name")
    c.name = data.name
    db.commit()
    return fin.category_out(db, c)


@router.delete("/{slug}/finance/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(slug: str, category_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    c = _category(db, fest, category_id)
    if fin.category_out(db, c).used:
        raise HTTPException(status_code=400, detail="Budget lines, spending or income are filed under this category. Move them first, or just rename it.")
    db.delete(c)
    db.commit()


@router.get("/{slug}/finance/options", response_model=schemas.SpendOptions)
def spend_options(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _member(db, fest, user)
    cats = [fin.category_out(db, c) for c in db.query(models.FinanceCategory).filter(models.FinanceCategory.fest_id == fest.id, models.FinanceCategory.kind == "expense").order_by(models.FinanceCategory.position, models.FinanceCategory.id).all()]
    lines = [{"id": l.id, "title": l.title, "category_id": l.category_id, "category_name": l.category.name, "team_name": l.team.name if l.team else None}
             for l in db.query(models.BudgetLine).filter(models.BudgetLine.fest_id == fest.id).order_by(models.BudgetLine.id).all()]
    return schemas.SpendOptions(categories=cats, lines=lines)


# ─── budget ───────────────────────────────────────────────────────────────────

@router.get("/{slug}/finance/budget", response_model=List[schemas.BudgetLineOut])
def list_budget(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    totals = fin.spent_by_line(db, fest.id)
    return [fin.line_out(l, totals) for l in db.query(models.BudgetLine).filter(models.BudgetLine.fest_id == fest.id).order_by(models.BudgetLine.category_id, models.BudgetLine.id).all()]


@router.post("/{slug}/finance/budget", response_model=schemas.BudgetLineOut, status_code=status.HTTP_201_CREATED)
def add_line(slug: str, data: schemas.BudgetLineIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    if db.query(models.BudgetLine).filter(models.BudgetLine.fest_id == fest.id).count() >= MAX_LINES:
        raise HTTPException(status_code=400, detail=f"A fest can have at most {MAX_LINES} budget lines")
    _category(db, fest, data.category_id, "expense")
    _team_check(db, fest, data.committee_team_id)
    l = models.BudgetLine(fest_id=fest.id, category_id=data.category_id, title=data.title, planned_paise=to_paise(data.planned), committee_team_id=data.committee_team_id, notes=data.notes or None)
    db.add(l)
    db.commit()
    db.refresh(l)
    return fin.line_out(l, fin.spent_by_line(db, fest.id))


@router.patch("/{slug}/finance/budget/{line_id}", response_model=schemas.BudgetLineOut)
def update_line(slug: str, line_id: int, data: schemas.BudgetLineUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    l = _line(db, fest, line_id)
    u = data.model_dump(exclude_unset=True)
    if u.get("category_id") is not None and u["category_id"] != l.category_id:
        _category(db, fest, u["category_id"], "expense")
        l.category_id = u["category_id"]
        # Spending filed under the line follows it into its new category
        db.query(models.Expense).filter(models.Expense.budget_line_id == l.id).update({"category_id": l.category_id}, synchronize_session=False)
    if u.get("title") is not None:
        l.title = u["title"]
    if u.get("planned") is not None:
        l.planned_paise = to_paise(u["planned"])
    if "committee_team_id" in u:
        _team_check(db, fest, u["committee_team_id"])
        l.committee_team_id = u["committee_team_id"]
    if "notes" in u:
        l.notes = u["notes"] or None
    db.commit()
    db.refresh(l)
    return fin.line_out(l, fin.spent_by_line(db, fest.id))


@router.delete("/{slug}/finance/budget/{line_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_line(slug: str, line_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    l = _line(db, fest, line_id)
    if db.query(models.Expense.id).filter(models.Expense.budget_line_id == l.id).first():
        raise HTTPException(status_code=400, detail="There is spending under this line. Move or delete it first.")
    db.delete(l)
    db.commit()


# ─── receipts ─────────────────────────────────────────────────────────────────

def _sniff(data: bytes) -> Optional[str]:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    return None


@router.post("/{slug}/finance/receipts", response_model=schemas.MediaOut, status_code=status.HTTP_201_CREATED)
async def upload_receipt(slug: str, file: UploadFile = File(...), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """A photo (JPEG, PNG, WebP) or a PDF of a bill, up to 3 MB. Anyone on the committee can attach one to a request."""
    fest = _fest(db, slug)
    _member(db, fest, user)
    today = db.query(models.Media).filter(models.Media.owner_id == user.id, models.Media.created_at > datetime.utcnow() - timedelta(days=1)).count()
    if today >= MAX_RECEIPTS_PER_DAY:
        raise HTTPException(status_code=429, detail="Upload limit reached for today. Try again tomorrow.")
    content = await file.read(MAX_RECEIPT_BYTES + 1)
    if len(content) > MAX_RECEIPT_BYTES:
        raise HTTPException(status_code=400, detail="That file is too large. The limit is 3 MB.")
    mime = _sniff(content)
    if mime is None:
        raise HTTPException(status_code=400, detail="Upload a JPEG, PNG, WebP or PDF.")
    media = models.Media(id=secrets.token_hex(16), owner_id=user.id, mime=mime, size=len(content), data=content, created_at=datetime.utcnow())
    db.add(media)
    db.commit()
    return schemas.MediaOut(id=media.id, url=f"/api/media/{media.id}")


# ─── spending ─────────────────────────────────────────────────────────────────

def _check_receipt(settings: models.FinanceSettings, amount_paise: int, receipts: List[str]) -> None:
    limit = settings.receipt_required_above_paise
    if limit is not None and amount_paise > limit and not receipts:
        raise HTTPException(status_code=400, detail=f"Attach a receipt for anything over {_inr(limit)}")


def _where(db: Session, fest: models.Fest, line_id: Optional[int], category_id: Optional[int]):
    """The budget line and category a request belongs to. A line brings its own category."""
    if line_id is not None:
        line = _line(db, fest, line_id)
        return line, line.category
    return None, _category(db, fest, category_id, "expense")


@router.get("/{slug}/finance/expenses", response_model=List[schemas.ExpenseOut])
def list_expenses(slug: str, status_filter: Optional[str] = Query(default=None, alias="status", pattern="^(pending|approved|rejected|paid|cancelled)$"), line_id: Optional[int] = None,
                  db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _member(db, fest, user)
    q = db.query(models.Expense).filter(models.Expense.fest_id == fest.id)
    if not is_fest_staff(db, fest.id, user):
        mine = _my_member(db, fest, user)
        q = q.filter((models.Expense.requested_by_id == user.id) | (models.Expense.paid_by_member_id == (mine.id if mine else -1)))
    if status_filter:
        q = q.filter(models.Expense.status == status_filter)
    if line_id is not None:
        q = q.filter(models.Expense.budget_line_id == line_id)
    return [fin.expense_out(e) for e in q.order_by(models.Expense.created_at.desc(), models.Expense.id.desc()).limit(500).all()]


@router.post("/{slug}/finance/expenses", response_model=schemas.ExpenseOut, status_code=status.HTTP_201_CREATED)
def request_spend(slug: str, data: schemas.ExpenseIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _member(db, fest, user)
    settings = fin.get_settings(db, fest)
    line, category = _where(db, fest, data.budget_line_id, data.category_id)
    amount = to_paise(data.amount)
    _check_receipt(settings, amount, data.receipts or [])
    me = _my_member(db, fest, user)
    if data.paid_by_me and me is None:
        raise HTTPException(status_code=400, detail="Only a committee member can say they paid out of their own pocket")
    e = models.Expense(
        fest_id=fest.id, budget_line_id=line.id if line else None, category_id=category.id, title=data.title, amount_paise=amount, spent_on=data.spent_on or date.today(),
        vendor=data.vendor or None, notes=data.notes or None, receipts=data.receipts or [], status="pending", requested_by_id=user.id, paid_by_member_id=me.id if (data.paid_by_me and me) else None,
    )
    if settings.auto_approve_below_paise and amount < settings.auto_approve_below_paise:
        e.status, e.decided_at, e.decision_note = "approved", datetime.utcnow(), "Approved automatically: under the limit"
    db.add(e)
    db.flush()
    if e.status == "pending":
        for uid in _staff_ids(db, fest):
            if uid != user.id:
                notices.notify(db, uid, "finance", f"Spend request: {data.title}", f"{user.name} asked to spend {_inr(amount)} on {data.title} ({fest.name}). Decide it under Finance.")
    db.commit()
    db.refresh(e)
    return fin.expense_out(e)


def _can_edit(db: Session, fest: models.Fest, e: models.Expense, user) -> None:
    staff = is_fest_staff(db, fest.id, user)
    if e.status == "paid":
        raise HTTPException(status_code=400, detail="This has been paid, so it can no longer be changed")
    if e.status in ("rejected", "cancelled"):
        raise HTTPException(status_code=400, detail="This request is closed. Make a new one.")
    if not staff and not (e.requested_by_id == user.id and e.status == "pending"):
        raise HTTPException(status_code=403, detail="You can change your own request while it is waiting for a decision")


@router.patch("/{slug}/finance/expenses/{expense_id}", response_model=schemas.ExpenseOut)
def change_expense(slug: str, expense_id: int, data: schemas.ExpenseUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _member(db, fest, user)
    e = _expense(db, fest, expense_id)
    _can_edit(db, fest, e, user)
    u = data.model_dump(exclude_unset=True)
    if "budget_line_id" in u or "category_id" in u:
        # Choosing a line brings its category. Choosing only a category takes the request off any line
        line_id = u.get("budget_line_id")
        line, category = _where(db, fest, line_id, u.get("category_id", e.category_id))
        e.budget_line_id, e.category_id = (line.id if line else None), category.id
    if u.get("title") is not None:
        e.title = u["title"]
    if u.get("amount") is not None:
        e.amount_paise = to_paise(u["amount"])
    if u.get("spent_on") is not None:
        e.spent_on = u["spent_on"]
    for field in ("vendor", "notes"):
        if field in u:
            setattr(e, field, u[field] or None)
    if "receipts" in u:
        e.receipts = u["receipts"] or []
    if "paid_by_me" in u:
        me = _my_member(db, fest, user)
        if u["paid_by_me"] and me is None:
            raise HTTPException(status_code=400, detail="Only a committee member can say they paid out of their own pocket")
        e.paid_by_member_id = me.id if (u["paid_by_me"] and me) else None
    _check_receipt(fin.get_settings(db, fest), e.amount_paise, list(e.receipts or []))
    db.commit()
    db.refresh(e)
    return fin.expense_out(e)


def _decide(db: Session, fest: models.Fest, e: models.Expense, user, new_status: str, note: Optional[str]) -> None:
    e.status, e.decided_by_id, e.decided_at, e.decision_note = new_status, user.id, datetime.utcnow(), note or None
    verb = "approved" if new_status == "approved" else "not approved"
    notices.notify(db, e.requested_by_id, "finance", f"Your spend request was {verb}", f"“{e.title}” ({_inr(e.amount_paise)}) was {verb}." + (f" Note: {note}" if note else ""))


@router.post("/{slug}/finance/expenses/{expense_id}/approve", response_model=schemas.ExpenseOut)
def approve(slug: str, expense_id: int, data: schemas.ExpenseDecision = schemas.ExpenseDecision(), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    e = _expense(db, fest, expense_id)
    if e.status != "pending":
        raise HTTPException(status_code=400, detail="Only a request that is waiting can be approved")
    _decide(db, fest, e, user, "approved", data.note)
    db.commit()
    db.refresh(e)
    return fin.expense_out(e)


@router.post("/{slug}/finance/expenses/{expense_id}/reject", response_model=schemas.ExpenseOut)
def reject(slug: str, expense_id: int, data: schemas.ExpenseReject, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    e = _expense(db, fest, expense_id)
    if e.status != "pending":
        raise HTTPException(status_code=400, detail="Only a request that is waiting can be turned down")
    _decide(db, fest, e, user, "rejected", data.note)
    db.commit()
    db.refresh(e)
    return fin.expense_out(e)


@router.post("/{slug}/finance/expenses/{expense_id}/pay", response_model=schemas.ExpenseOut)
def pay(slug: str, expense_id: int, data: schemas.ExpensePay = schemas.ExpensePay(), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Mark an approved request as paid. For one a member paid out of pocket, this means they have been paid back."""
    fest = _fest(db, slug)
    _staff(db, fest, user)
    e = _expense(db, fest, expense_id)
    if e.status != "approved":
        raise HTTPException(status_code=400, detail="Only an approved request can be marked paid")
    e.status, e.paid_on, e.paid_note = "paid", data.paid_on or date.today(), data.note or None
    if e.paid_by_member_id:
        notices.notify(db, e.requested_by_id, "finance", "You have been paid back", f"“{e.title}” ({_inr(e.amount_paise)}) was marked as reimbursed.")
    db.commit()
    db.refresh(e)
    return fin.expense_out(e)


@router.post("/{slug}/finance/expenses/{expense_id}/cancel", response_model=schemas.ExpenseOut)
def cancel(slug: str, expense_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _member(db, fest, user)
    e = _expense(db, fest, expense_id)
    if e.status != "pending":
        raise HTTPException(status_code=400, detail="Only a request that is still waiting can be withdrawn")
    if e.requested_by_id != user.id and not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the person who asked can withdraw a request")
    e.status = "cancelled"
    db.commit()
    db.refresh(e)
    return fin.expense_out(e)


@router.delete("/{slug}/finance/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(slug: str, expense_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    e = _expense(db, fest, expense_id)
    if e.status == "paid":
        raise HTTPException(status_code=400, detail="A paid expense is part of the record and cannot be deleted")
    db.delete(e)
    db.commit()


# ─── income ───────────────────────────────────────────────────────────────────

@router.get("/{slug}/finance/income", response_model=List[schemas.IncomeOut])
def list_income(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    return [fin.income_out(i, date.today()) for i in db.query(models.IncomeItem).filter(models.IncomeItem.fest_id == fest.id).order_by(models.IncomeItem.id).all()]


def _sponsor_check(db: Session, fest: models.Fest, sponsor_id: Optional[int]) -> None:
    if sponsor_id is not None and not db.query(models.FestSponsor).filter(models.FestSponsor.id == sponsor_id, models.FestSponsor.fest_id == fest.id).first():
        raise HTTPException(status_code=400, detail="That sponsor is not listed for this fest")


@router.post("/{slug}/finance/income", response_model=schemas.IncomeOut, status_code=status.HTTP_201_CREATED)
def add_income(slug: str, data: schemas.IncomeIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    _category(db, fest, data.category_id, "income")
    _sponsor_check(db, fest, data.sponsor_id)
    i = models.IncomeItem(fest_id=fest.id, category_id=data.category_id, title=data.title, source=data.source or None, sponsor_id=data.sponsor_id, expected_paise=to_paise(data.expected), due_on=data.due_on, notes=data.notes or None)
    db.add(i)
    db.commit()
    db.refresh(i)
    return fin.income_out(i, date.today())


@router.patch("/{slug}/finance/income/{income_id}", response_model=schemas.IncomeOut)
def update_income(slug: str, income_id: int, data: schemas.IncomeUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    i = _income(db, fest, income_id)
    u = data.model_dump(exclude_unset=True)
    if u.get("category_id") is not None:
        _category(db, fest, u["category_id"], "income")
        i.category_id = u["category_id"]
    if "sponsor_id" in u:
        _sponsor_check(db, fest, u["sponsor_id"])
        i.sponsor_id = u["sponsor_id"]
    if u.get("title") is not None:
        i.title = u["title"]
    if u.get("expected") is not None:
        i.expected_paise = to_paise(u["expected"])
    for field in ("source", "notes"):
        if field in u:
            setattr(i, field, u[field] or None)
    if "due_on" in u:
        i.due_on = u["due_on"]
    db.commit()
    db.refresh(i)
    return fin.income_out(i, date.today())


@router.delete("/{slug}/finance/income/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_income(slug: str, income_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    i = _income(db, fest, income_id)
    if i.payments:
        raise HTTPException(status_code=400, detail="Payments are recorded against this. Delete them first.")
    db.delete(i)
    db.commit()


@router.post("/{slug}/finance/income/{income_id}/payments", response_model=schemas.IncomeOut, status_code=status.HTTP_201_CREATED)
def receive(slug: str, income_id: int, data: schemas.IncomePaymentIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    i = _income(db, fest, income_id)
    db.add(models.IncomePayment(income_id=i.id, amount_paise=to_paise(data.amount), received_on=data.received_on or date.today(), method=data.method or None, note=data.note or None, recorded_by_id=user.id))
    db.commit()
    db.refresh(i)
    return fin.income_out(i, date.today())


@router.delete("/{slug}/finance/income/payments/{payment_id}", response_model=schemas.IncomeOut)
def delete_receipt(slug: str, payment_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    p = db.query(models.IncomePayment).join(models.IncomeItem, models.IncomeItem.id == models.IncomePayment.income_id).filter(models.IncomePayment.id == payment_id, models.IncomeItem.fest_id == fest.id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    i = p.income_id
    db.delete(p)
    db.commit()
    return fin.income_out(_income(db, fest, i), date.today())


# ─── summary and export ───────────────────────────────────────────────────────

@router.get("/{slug}/finance/summary", response_model=schemas.FinanceSummary)
def get_summary(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    out = fin.summary(db, fest, date.today())
    db.commit()
    return out


def _cell(v) -> str:
    """Neutralise spreadsheet formulas in text people typed."""
    text = "" if v is None else str(v)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@router.get("/{slug}/finance/export")
def export(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Every rupee in and out as one spreadsheet, for the fest's accounts."""
    fest = _fest(db, slug)
    _staff(db, fest, user)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Date", "Type", "Description", "Category", "Budget line / source", "Amount (INR)", "Status", "Person", "Note"])
    for e in db.query(models.Expense).filter(models.Expense.fest_id == fest.id, models.Expense.status != "cancelled").order_by(models.Expense.spent_on, models.Expense.id).all():
        w.writerow([e.spent_on.isoformat(), "Expense", _cell(e.title), _cell(e.category.name), _cell(e.budget_line.title if e.budget_line else ""), f"{rupees(e.amount_paise):.2f}", e.status,
                    _cell(e.requested_by.name if e.requested_by else ""), _cell(e.paid_note or e.decision_note or "")])
    for i in db.query(models.IncomeItem).filter(models.IncomeItem.fest_id == fest.id).order_by(models.IncomeItem.id).all():
        for p in i.payments:
            w.writerow([p.received_on.isoformat(), "Income received", _cell(i.title), _cell(i.category.name), _cell(i.source or ""), f"{rupees(p.amount_paise):.2f}", "received", "", _cell(p.method or p.note or "")])
    for p in db.query(models.FeePayment).filter(models.FeePayment.fest_id == fest.id).order_by(models.FeePayment.received_on, models.FeePayment.id).all():
        w.writerow([p.received_on.isoformat(), "Income received", "Visiting college fees", "Visiting colleges", _cell(contingent_money.label(p.contingent) if hasattr(p, "contingent") and p.contingent else ""), f"{rupees(p.amount_paise):.2f}", "received", "", _cell(p.method or p.reference or "")])
    db.commit()
    return Response(content=buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{fest.slug}-finance.csv"'})
