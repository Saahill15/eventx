"""
Add many events to a fest at once from a spreadsheet saved as CSV.

  GET  /api/fests/{slug}/events/import-template      a CSV with the right columns and two example rows
  POST /api/fests/{slug}/events/import?dry_run=true   check the file and report problems row by row (nothing is saved)
  POST /api/fests/{slug}/events/import?dry_run=false  the same checks, then add every event, or none if any row has a problem
"""

import csv
import io
import re
from datetime import date, datetime
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.permissions import is_fest_staff

router = APIRouter()

MAX_BYTES = 512 * 1024
MAX_ROWS = 200

# (column, required, what goes in it)
COLUMNS = [
    ("title", True, "Name of the event"),
    ("description", True, "What happens at the event"),
    ("date", True, "YYYY-MM-DD or DD/MM/YYYY, within the fest's dates"),
    ("start_time", True, "24-hour HH:MM, or like 6:30 PM"),
    ("end_time", True, "Same format, after the start"),
    ("venue", True, "Where it happens"),
    ("category", False, "For example Music, Technical, Sports"),
    ("price", False, "In rupees. Empty or 0 means free"),
    ("student_price", False, "Lower price for verified students (paid events only)"),
    ("registration", False, "yes if students must register"),
    ("seat_limit", False, "Most registrations (teams, for a team event). Empty means no limit"),
    ("approval", False, "auto (confirmed at once) or manual (the committee approves)"),
    ("students_only", False, "yes if only verified students can register"),
    ("team_event", False, "yes if people register as a team"),
    ("team_min", False, "Smallest team size"),
    ("team_max", False, "Largest team size"),
]
NAMES = [c[0] for c in COLUMNS]
REQUIRED = {c[0] for c in COLUMNS if c[1]}

EXAMPLES = [
    ["Battle of Bands", "College bands compete live on the main stage.", "2026-12-05", "18:00", "21:00", "Main Stage", "Music", "0", "", "yes", "20", "manual", "no", "yes", "3", "6"],
    ["Robo Wars", "Build a bot and fight it out in the arena.", "2026-12-06", "11:00", "15:30", "Ground B", "Technical", "200", "150", "yes", "", "auto", "yes", "no", "", ""],
]


def _staff_fest(db: Session, slug: str, user: models.User) -> models.Fest:
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest or not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=404, detail="Fest not found")
    return fest


def _yes(value: str, column: str, errors: List[str]) -> bool:
    v = value.strip().lower()
    if v in ("yes", "y", "true", "1"):
        return True
    if v in ("", "no", "n", "false", "0"):
        return False
    errors.append(f"{column}: write yes or no")
    return False


def _number(value: str, column: str, errors: List[str], integer=False) -> Optional[float]:
    v = value.strip().replace(",", "").replace("₹", "")
    if not v:
        return None
    try:
        n = int(v) if integer else float(v)
    except ValueError:
        errors.append(f"{column}: must be a {'whole ' if integer else ''}number")
        return None
    if n < 0:
        errors.append(f"{column}: cannot be negative")
        return None
    return n


def _date(value: str, errors: List[str]) -> Optional[date]:
    v = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            pass
    errors.append("date: use YYYY-MM-DD or DD/MM/YYYY")
    return None


def _time(value: str, column: str, errors: List[str]) -> Optional[str]:
    v = value.strip().lower().replace(".", ":")
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", v)
    if m:
        h, mins, ampm = int(m.group(1)), int(m.group(2) or 0), m.group(3)
        if ampm:
            if not 1 <= h <= 12:
                m = None
            else:
                h = h % 12 + (12 if ampm == "pm" else 0)
        if m and h < 24 and mins < 60:
            return f"{h:02d}:{mins:02d}"
    errors.append(f"{column}: use 24-hour HH:MM, or like 6:30 PM")
    return None


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):   # Excel saves either
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise HTTPException(status_code=400, detail="Save the file as CSV (UTF-8)")


def _row_payload(cells: dict, fest: models.Fest) -> Tuple[Optional[schemas.EventCreate], List[str]]:
    errors: List[str] = []
    for col in REQUIRED:
        if not cells.get(col, "").strip():
            errors.append(f"{col}: required")
    day = _date(cells["date"], errors) if cells.get("date", "").strip() else None
    start = _time(cells["start_time"], "start_time", errors) if cells.get("start_time", "").strip() else None
    end = _time(cells["end_time"], "end_time", errors) if cells.get("end_time", "").strip() else None
    price = _number(cells.get("price", ""), "price", errors) or 0.0
    student_price = _number(cells.get("student_price", ""), "student_price", errors)
    registration = _yes(cells.get("registration", ""), "registration", errors)
    seat_limit = _number(cells.get("seat_limit", ""), "seat_limit", errors, integer=True)
    approval = (cells.get("approval", "") or "auto").strip().lower()
    if approval not in ("auto", "manual"):
        errors.append("approval: write auto or manual")
        approval = "auto"
    students_only = _yes(cells.get("students_only", ""), "students_only", errors)
    team = _yes(cells.get("team_event", ""), "team_event", errors)
    team_min = _number(cells.get("team_min", ""), "team_min", errors, integer=True)
    team_max = _number(cells.get("team_max", ""), "team_max", errors, integer=True)
    if day and fest.start_date and fest.end_date and not (fest.start_date <= day <= fest.end_date):
        errors.append(f"date: must be between {fest.start_date} and {fest.end_date}, the fest's dates")
    if errors:
        return None, errors
    paid = price > 0
    try:
        payload = schemas.EventCreate(
            event_type="fest", fest_id=fest.id, college_id=fest.college_id,
            title=cells["title"].strip(), description=cells["description"].strip(), location=cells["venue"].strip(),
            date=datetime.combine(day, datetime.min.time()), time=start, end_time=end,
            category=(cells.get("category") or "").strip()[:60] or None,
            is_free=not paid, price=price, student_price=student_price if paid else None,
            requires_registration=registration, is_paid=registration and paid,
            registration_limit=int(seat_limit) if seat_limit else None, approval_mode=approval,
            students_only=students_only, is_team_event=team, team_min=team_min, team_max=team_max,
        )
    except ValidationError as exc:
        for e in exc.errors():
            field = ".".join(str(p) for p in e.get("loc", []) if p != "__root__")
            msg = e.get("msg", "invalid").removeprefix("Value error, ")
            errors.append(f"{field}: {msg}" if field else msg)
        return None, errors
    return payload, []


@router.get("/{slug}/events/import-template")
def import_template(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    _staff_fest(db, slug, user)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(NAMES)
    for row in EXAMPLES:
        writer.writerow(row)
    return Response(content=buffer.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="hiveout-events-template.csv"'})


@router.post("/{slug}/events/import", response_model=schemas.ImportResult)
async def import_events(
    slug: str,
    file: UploadFile = File(...),
    dry_run: bool = Query(default=True),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    fest = _staff_fest(db, slug, user)
    if fest.review_status == "in_review" and user.role != models.RoleEnum.admin:
        raise HTTPException(status_code=400, detail="Your fest is waiting for review. Withdraw it first if you need to change events.")
    raw = await file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="That file is too big. The limit is 512 KB.")

    result = schemas.ImportResult(dry_run=dry_run)
    reader = csv.DictReader(io.StringIO(_decode(raw)))
    header = [h.strip().lower() for h in (reader.fieldnames or [])]
    missing = [c for c in NAMES if c in REQUIRED and c not in header]
    unknown = [h for h in header if h and h not in NAMES]
    if missing:
        result.file_errors.append("Missing columns: " + ", ".join(missing) + ". Start from the template.")
    if unknown:
        result.file_errors.append("Columns this does not know: " + ", ".join(unknown))
    if result.file_errors:
        return result

    existing = {t.lower() for (t,) in db.query(models.Event.title).filter(models.Event.fest_id == fest.id).all()}
    seen = set()
    payloads = []
    for line, row in enumerate(reader, start=2):   # line 1 is the header
        cells = {(k or "").strip().lower(): (v or "") for k, v in row.items() if k}
        if not any(v.strip() for v in cells.values()):
            continue  # blank line
        if len(result.rows) >= MAX_ROWS:
            result.file_errors.append(f"At most {MAX_ROWS} events per file. Split it into smaller files.")
            return result
        payload, errors = _row_payload(cells, fest)
        title = cells.get("title", "").strip()
        if title.lower() in seen:
            errors.append("title: appears more than once in this file")
        elif title.lower() in existing:
            errors.append("title: this fest already has an event with this name")
        seen.add(title.lower())
        result.rows.append(schemas.ImportRowOut(line=line, title=title, errors=errors))
        if not errors:
            payloads.append(payload)

    if not result.rows:
        result.file_errors.append("The file has no events in it.")
        return result
    result.valid = len(payloads)
    if dry_run or result.valid != len(result.rows):
        return result  # a preview, or something to fix first: nothing is saved

    for p in payloads:
        db.add(models.Event(**p.model_dump(), status=models.StatusEnum.approved))
    db.commit()
    result.created = len(payloads)
    return result
