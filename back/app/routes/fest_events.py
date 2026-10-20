"""
Routes for Fest Event Registration.
Mounted under /api/fest-events by main.py.

  POST   /api/fest-events/{event_id}/register   → register for a fest event
  GET    /api/fest-events/{event_id}/registrations → list registrations (privileged)
  GET    /api/fest-events/my-registrations        → current user's registrations
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models, schemas
from app.auth.dependencies import get_current_user

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


# ─── GET /fest-events/{event_id}/registrations ───────────────────────────────

@router.get("/{event_id}/registrations", response_model=List[schemas.EventRegistrationOut])
def list_event_registrations(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    List all registrations for a fest event.
    Requires: admin OR owner/core member of the fest.
    """
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.event_type != models.EventTypeEnum.fest:
        raise HTTPException(status_code=400, detail="Not a fest event")

    # Permission check
    if current_user.role != models.RoleEnum.admin:
        is_member = (
            db.query(models.FestMember)
            .filter(
                models.FestMember.fest_id == event.fest_id,
                models.FestMember.user_id == current_user.id,
                models.FestMember.role.in_([
                    models.FestMemberRoleEnum.owner,
                    models.FestMemberRoleEnum.core,
                ]),
            )
            .first()
        )
        if not is_member:
            raise HTTPException(status_code=403, detail="Forbidden")

    return (
        db.query(models.EventRegistration)
        .filter(models.EventRegistration.event_id == event_id)
        .all()
    )


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
