"""
Routes for Fest Event Registration.
Mounted under /api/fest-events by main.py.

  POST   /api/fest-events/{event_id}/register   → register for a fest event
  GET    /api/fest-events/{event_id}/registrations → list registrations (privileged)
  GET    /api/fest-events/my-registrations        → current user's registrations
"""

import csv
import io
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models, schemas
from app.auth.dependencies import get_current_user
from app.permissions import is_fest_staff

router = APIRouter()


# ─── POST /fest-events/{event_id}/register ───────────────────────────────────

@router.post("/{event_id}/register", response_model=schemas.EventRegistrationOut, status_code=status.HTTP_201_CREATED)
def register_for_event(
    event_id: int,
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

    registration = models.EventRegistration(
        fest_pass_id    = fest_pass.id,
        event_id        = event_id,
        approval_status = approval_status,
        payment_status  = payment_status,
    )
    db.add(registration)
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
    writer.writerow(["Name", "Email", "Approval", "Payment", "Checked in at fest", "Registered at"])
    for r in _registrations_for(db, event_id):
        writer.writerow([
            _csv_cell(r.user_name), _csv_cell(r.user_email),
            r.approval_status.value, r.payment_status.value,
            "yes" if r.checked_in else "no",
            r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
        ])
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
