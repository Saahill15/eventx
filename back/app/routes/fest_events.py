"""
Routes for Fest Event Registration.
Mounted under /api/fest-events by main.py.

  POST   /api/fest-events/{event_id}/register   → register for a fest event
  GET    /api/fest-events/{event_id}/registrations → list registrations (privileged)
  GET    /api/fest-events/my-registrations        → current user's registrations
"""

import csv
import io
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models, schemas
from app.auth.dependencies import get_current_user
from app.permissions import is_fest_member, is_fest_staff
from app.routes.event_questions import validate_answers

router = APIRouter()


# ─── POST /fest-events/{event_id}/register ───────────────────────────────────

@router.post("/{event_id}/register", response_model=schemas.EventRegistrationOut, status_code=status.HTTP_201_CREATED)
def register_for_event(
    event_id: int,
    data: Optional[schemas.RegisterIn] = Body(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Register the current user for a fest event.

    Flow:
      1. Validate event_type='fest'
      2. Validate requires_registration=True
      3. Validate user has an approved FestPass for this event's fest
      4. Check capacity (approved + pending < limit)
      5. If is_paid → simulate payment → payment_status='paid', approval_status='approved'
         If is_paid=False + approval_mode='auto' → approval_status='approved'
         If is_paid=False + approval_mode='manual' → approval_status='pending'
    """
    # ── 1. Fetch and validate event ──────────────────────────────────────────
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.event_type != models.EventTypeEnum.fest:
        raise HTTPException(
            status_code=400,
            detail="Registration is only available for fest events",
        )
    if event.status != models.StatusEnum.approved:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.cancelled:
        raise HTTPException(status_code=400, detail="This event has been cancelled")
    if event.students_only and not current_user.is_student_verified:
        raise HTTPException(status_code=403, detail="This event is for verified students. Verify your student status in your profile first.")

    # ── 2. Registration must be enabled ──────────────────────────────────────
    if not event.requires_registration:
        raise HTTPException(
            status_code=400,
            detail="This event does not require registration",
        )

    # ── 3. User must have an approved FestPass ────────────────────────────────
    fest_pass = (
        db.query(models.FestPass)
        .filter(
            models.FestPass.user_id == current_user.id,
            models.FestPass.fest_id == event.fest_id,
            models.FestPass.status == models.FestPassStatusEnum.approved,
        )
        .first()
    )
    if not fest_pass:
        raise HTTPException(
            status_code=400,
            detail="You must hold an approved entry pass for this fest before registering for events",
        )

    # Idempotent — return existing registration if already registered
    existing = (
        db.query(models.EventRegistration)
        .filter(
            models.EventRegistration.fest_pass_id == fest_pass.id,
            models.EventRegistration.event_id == event_id,
        )
        .first()
    )
    if existing:
        return existing

    # Custom questions the committee added (a body is only needed when the event asks something)
    answers = validate_answers(event, data.answers if data else [])

    # ── 4. Capacity check ────────────────────────────────────────────────────
    if event.registration_limit is not None:
        active_count = (
            db.query(models.EventRegistration)
            .filter(
                models.EventRegistration.event_id == event_id,
                models.EventRegistration.approval_status.in_([
                    models.RegApprovalStatusEnum.approved,
                    models.RegApprovalStatusEnum.pending,
                ]),
            )
            .count()
        )
        if active_count >= event.registration_limit:
            raise HTTPException(status_code=400, detail="Registration full")

    # ── 5. Determine statuses ─────────────────────────────────────────────────
    if event.is_paid:
        # Simulate payment success — always succeeds in this implementation
        approval_status = models.RegApprovalStatusEnum.approved
        payment_status  = models.RegPaymentStatusEnum.paid
    else:
        payment_status = models.RegPaymentStatusEnum.unpaid
        if event.approval_mode == models.ApprovalModeEnum.auto:
            approval_status = models.RegApprovalStatusEnum.approved
        else:
            approval_status = models.RegApprovalStatusEnum.pending

    # What this person owes: students who are verified get the student price when the event has one
    if event.is_paid:
        amount_due = event.student_price if (current_user.is_student_verified and event.student_price is not None) else event.price
    else:
        amount_due = 0.0

    registration = models.EventRegistration(
        fest_pass_id    = fest_pass.id,
        event_id        = event_id,
        approval_status = approval_status,
        payment_status  = payment_status,
        amount_due      = amount_due,
    )
    db.add(registration)
    db.flush()
    for question, value in answers:
        db.add(models.RegistrationAnswer(registration_id=registration.id, question_id=question.id, answer=value))
    db.commit()
    db.refresh(registration)
    return registration


# ─── helpers ─────────────────────────────────────────────────────────────────

def _require_event_staff(db: Session, event: models.Event, user: models.User):
    if event.event_type != models.EventTypeEnum.fest:
        raise HTTPException(status_code=400, detail="Not a fest event")
    if not is_fest_staff(db, event.fest_id, user):
        raise HTTPException(status_code=403, detail="Forbidden")


def _registrations_for(db: Session, event_id: int):
    return (
        db.query(models.EventRegistration)
        .filter(models.EventRegistration.event_id == event_id)
        .order_by(models.EventRegistration.created_at)
        .all()
    )


def _csv_cell(value) -> str:
    """Neutralise spreadsheet formulas in user-supplied text (CSV injection)."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


# ─── DELETE /fest-events/{event_id}/register ─────────────────────────────────

@router.delete("/{event_id}/register", status_code=status.HTTP_204_NO_CONTENT)
def cancel_my_registration(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Cancel the current user's registration. Frees the seat. Not possible once they have been checked in."""
    registration = (
        db.query(models.EventRegistration)
        .join(models.FestPass, models.EventRegistration.fest_pass_id == models.FestPass.id)
        .filter(models.EventRegistration.event_id == event_id, models.FestPass.user_id == current_user.id)
        .first()
    )
    if not registration:
        raise HTTPException(status_code=404, detail="You are not registered for this event")
    if registration.attended:
        raise HTTPException(status_code=400, detail="You have already attended this event")
    db.delete(registration)
    db.commit()


# ─── POST /fest-events/{event_id}/check-in ───────────────────────────────────

@router.post("/{event_id}/check-in", response_model=schemas.EventCheckInOut)
def check_in_to_event(
    event_id: int,
    data: schemas.QrCodeIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Mark a student as present at one event, by their fest pass QR code (any committee member)."""
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event or event.event_type != models.EventTypeEnum.fest:
        raise HTTPException(status_code=404, detail="Event not found")
    if not is_fest_member(db, event.fest_id, current_user):
        raise HTTPException(status_code=403, detail="Only this fest's committee can check people in")

    fest_pass = (
        db.query(models.FestPass)
        .filter(models.FestPass.qr_code == data.qr_code, models.FestPass.fest_id == event.fest_id)
        .first()
    )
    if not fest_pass:
        raise HTTPException(status_code=404, detail="No pass with that code for this fest")
    if fest_pass.status != models.FestPassStatusEnum.approved:
        raise HTTPException(status_code=400, detail="Pass is blocked: entry denied")

    if event.requires_registration:
        registration = (
            db.query(models.EventRegistration)
            .filter(models.EventRegistration.fest_pass_id == fest_pass.id, models.EventRegistration.event_id == event_id)
            .first()
        )
        if not registration:
            raise HTTPException(status_code=400, detail="This student is not registered for the event")
        if registration.approval_status != models.RegApprovalStatusEnum.approved:
            raise HTTPException(status_code=400, detail="Registration is not approved yet")
    else:
        # Open events have no registration: record attendance on demand
        registration = (
            db.query(models.EventRegistration)
            .filter(models.EventRegistration.fest_pass_id == fest_pass.id, models.EventRegistration.event_id == event_id)
            .first()
        )
        if not registration:
            registration = models.EventRegistration(
                fest_pass_id=fest_pass.id, event_id=event_id,
                approval_status=models.RegApprovalStatusEnum.approved, payment_status=models.RegPaymentStatusEnum.unpaid,
            )
            db.add(registration)
            db.flush()

    if registration.attended:
        raise HTTPException(status_code=400, detail="Already checked in to this event")
    registration.attended = True
    registration.attended_at = datetime.utcnow()
    registration.attended_by = current_user.id
    db.commit()
    db.refresh(registration)
    return schemas.EventCheckInOut(
        registration_id=registration.id, user_name=registration.user_name,
        attended=True, attended_at=registration.attended_at,
    )


# ─── GET /fest-events/{event_id}/registrations ───────────────────────────────

@router.get("/{event_id}/registrations", response_model=List[schemas.EventRegistrationDetailOut])
def list_event_registrations(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    List all registrations for a fest event, with who registered.
    Requires: admin OR owner/core member of the fest.
    """
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_staff(db, event, current_user)
    return _registrations_for(db, event_id)


# ─── GET /fest-events/{event_id}/registrations.csv ───────────────────────────

@router.get("/{event_id}/registrations.csv")
def export_event_registrations(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Download the registrations as a CSV file (same permission as the list)."""
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_staff(db, event, current_user)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    questions = list(event.questions)
    writer.writerow(["Name", "Email", "Approval", "Payment", "Amount due (INR)", "Checked in at fest", "Attended this event", "Registered at"] + [_csv_cell(q.label) for q in questions])
    for r in _registrations_for(db, event_id):
        by_question = {a.question_id: a.answer for a in r.answers}
        writer.writerow([
            _csv_cell(r.user_name), _csv_cell(r.user_email),
            r.approval_status.value, r.payment_status.value,
            "" if r.amount_due is None else f"{r.amount_due:g}",
            "yes" if r.checked_in else "no",
            "yes" if r.attended else "no",
            r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
        ] + [_csv_cell(by_question.get(q.id, "")) for q in questions])
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="registrations-event-{event_id}.csv"'},
    )


# ─── POST /fest-events/registrations/{registration_id}/approve | reject ──────

def _decide(registration_id: int, approve: bool, db: Session, user: models.User):
    registration = db.query(models.EventRegistration).filter(models.EventRegistration.id == registration_id).first()
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")
    _require_event_staff(db, registration.event, user)
    if registration.approval_status != models.RegApprovalStatusEnum.pending:
        raise HTTPException(status_code=400, detail="Only pending registrations can be decided")
    registration.approval_status = (
        models.RegApprovalStatusEnum.approved if approve else models.RegApprovalStatusEnum.rejected
    )
    db.commit()
    db.refresh(registration)
    return registration


@router.post("/registrations/{registration_id}/approve", response_model=schemas.EventRegistrationDetailOut)
def approve_registration(registration_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return _decide(registration_id, True, db, current_user)


@router.post("/registrations/{registration_id}/reject", response_model=schemas.EventRegistrationDetailOut)
def reject_registration(registration_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return _decide(registration_id, False, db, current_user)


# ─── GET /fest-events/my-registrations ───────────────────────────────────────

@router.get("/my-registrations", response_model=List[schemas.EventRegistrationOut])
def my_registrations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return all event registrations belonging to the current user (via their FestPasses)."""
    pass_ids = [fp.id for fp in db.query(models.FestPass).filter(
        models.FestPass.user_id == current_user.id
    ).all()]

    if not pass_ids:
        return []

    return (
        db.query(models.EventRegistration)
        .filter(models.EventRegistration.fest_pass_id.in_(pass_ids))
        .order_by(models.EventRegistration.created_at.desc())
        .all()
    )
