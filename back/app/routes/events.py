from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app import models, schemas
from app.auth.dependencies import get_current_user, get_optional_user, require_organizer
from app.permissions import can_view_event, is_fest_staff

router = APIRouter()

@router.get("/", response_model=List[schemas.EventOut])
def get_events(db: Session = Depends(get_db)):
    """Return all approved events across both branches (used by homepage feed)."""
    return (
        db.query(models.Event)
        .filter(models.Event.status == models.StatusEnum.approved)
        .order_by(models.Event.date.desc())
        .all()
    )

@router.get("/city", response_model=List[schemas.EventOut])
def get_city_events(db: Session = Depends(get_db)):
    """Return only standalone City Events (event_type='city', approved)."""
    return (
        db.query(models.Event)
        .filter(
            models.Event.event_type == models.EventTypeEnum.city,
            models.Event.status == models.StatusEnum.approved,
        )
        .order_by(models.Event.date.desc())
        .all()
    )

@router.get("/mine", response_model=List[schemas.EventOut])
def get_my_events(db: Session = Depends(get_db), current_user=Depends(require_organizer)):
    """Return city events owned by the current organizer.
    Fest events are managed via /fests/:slug, not here.
    """
    return (
        db.query(models.Event)
        .filter(
            models.Event.event_type == models.EventTypeEnum.city,
            models.Event.organizer_id == current_user.id,
        )
        .order_by(models.Event.date.desc())
        .all()
    )

@router.get("/feed", response_model=List[schemas.EventOut])
def get_feed(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    interest_names = {
        name for (name,) in (
            db.query(models.Interest.name)
            .join(models.UserInterest, models.UserInterest.interest_id == models.Interest.id)
            .filter(models.UserInterest.user_id == current_user.id)
            .all()
        )
    }
    all_events = (
        db.query(models.Event)
        .filter(models.Event.status == models.StatusEnum.approved)
        .order_by(models.Event.date.desc())
        .all()
    )
    priority = [e for e in all_events if e.category in interest_names]
    others   = [e for e in all_events if e.category not in interest_names]
    return priority + others

@router.get("/{event_id}", response_model=schemas.EventOut)
def get_event(event_id: int, db: Session = Depends(get_db), current_user=Depends(get_optional_user)):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    # Pending/rejected events look like they do not exist to anyone who may not see them
    if not event or not can_view_event(db, event, current_user):
        raise HTTPException(status_code=404, detail="Event not found")
    return event

@router.post("/", response_model=schemas.EventOut)
def create_event(data: schemas.EventCreate, db: Session = Depends(get_db), current_user=Depends(require_organizer)):
    """Create an event.
    - event_type="city":  organizer_id is set to current_user; fest_id must be null (enforced by schema).
    - event_type="fest":  fest_id required (enforced by schema); organizer_id stays NULL.
    """
    event_data = data.model_dump()

    if data.college_id is not None and not db.query(models.College).filter(models.College.id == data.college_id).first():
        raise HTTPException(status_code=400, detail="College not found")

    if data.event_type == "fest":
        fest = db.query(models.Fest).filter(models.Fest.id == data.fest_id).first()
        if not fest:
            raise HTTPException(status_code=400, detail="Fest not found")
        if not is_fest_staff(db, fest.id, current_user):
            raise HTTPException(status_code=403, detail="Only the fest's owner or core team can add events to it")

    if data.event_type == "city":
        event_data["organizer_id"] = current_user.id
    # fest events: organizer_id intentionally NULL; committee managed via FestMember

    # Fest staff publish their own fest's events directly; city events wait for an admin
    initial_status = models.StatusEnum.approved if data.event_type == "fest" else models.StatusEnum.pending
    event = models.Event(**event_data, status=initial_status)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.patch("/{event_id}", response_model=schemas.EventOut)
def update_event(
    event_id: int,
    data: schemas.EventUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_organizer),
):
    """
    Partial update of an event.

    Protected fields (rejected if any EventRegistrations exist):
      - requires_registration
      - is_paid
      - price (decrease only — increasing or keeping same is fine)
      - registration_limit (cannot decrease below current active registration count)

    Always allowed:
      - title, description, location, date, time, image_url, category
      - increasing registration_limit
      - approval_mode
    """
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Ownership check: city event organizer or fest owner/core or admin
    if current_user.role != models.RoleEnum.admin:
        if event.event_type == models.EventTypeEnum.city:
            if event.organizer_id != current_user.id:
                raise HTTPException(status_code=403, detail="Not your event")
        else:
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

    # Count active registrations for this event
    active_reg_count = (
        db.query(models.EventRegistration)
        .filter(
            models.EventRegistration.event_id == event_id,
            models.EventRegistration.approval_status.in_([
                models.RegApprovalStatusEnum.approved,
                models.RegApprovalStatusEnum.pending,
            ]),
        )
        .count()
    ) if event.event_type == models.EventTypeEnum.fest else 0

    has_registrations = active_reg_count > 0

    updates = data.model_dump(exclude_unset=True)
    for non_nullable in ("title", "date", "price", "requires_registration", "is_paid", "approval_mode", "students_only"):
        if updates.get(non_nullable) is None:
            updates.pop(non_nullable, None)

    # Student price must stay below the normal price
    new_price = updates.get("price", event.price)
    if updates.get("student_price") is not None and updates["student_price"] >= (new_price or 0):
        raise HTTPException(status_code=400, detail="The student price must be lower than the normal price")

    # Guard locked fields if registrations exist
    if has_registrations:
        locked = []
        if updates.get("students_only") is True and not event.students_only:
            locked.append("students_only (cannot be turned on)")
        if "student_price" in updates:
            locked.append("student_price")
        if "requires_registration" in updates:
            locked.append("requires_registration")
        if "is_paid" in updates:
            locked.append("is_paid")
        if "price" in updates and updates["price"] < (event.price or 0):
            locked.append("price (cannot decrease)")
        if "registration_limit" in updates:
            new_limit = updates["registration_limit"]
            if new_limit is not None and new_limit < active_reg_count:
                locked.append(
                    f"registration_limit (cannot set below current count of {active_reg_count})"
                )
        if locked:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot change locked fields while registrations exist: {', '.join(locked)}",
            )

    for field, value in updates.items():
        setattr(event, field, value)

    db.commit()
    db.refresh(event)
    return event


def _require_event_manager(db: Session, event: models.Event, user):
    if user.role == models.RoleEnum.admin:
        return
    if event.event_type == models.EventTypeEnum.city:
        allowed = event.organizer_id == user.id
    else:
        allowed = is_fest_staff(db, event.fest_id, user)
    if not allowed:
        raise HTTPException(status_code=403, detail="Not allowed to manage this event")


@router.post("/{event_id}/cancel", response_model=schemas.EventOut)
def cancel_event(event_id: int, data: schemas.CancelEvent, db: Session = Depends(get_db), current_user=Depends(require_organizer)):
    """Cancel an event. It stays listed, marked as cancelled, and nobody can register for it any more."""
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_manager(db, event, current_user)
    if event.cancelled:
        raise HTTPException(status_code=400, detail="Event is already cancelled")
    event.cancelled_at = datetime.utcnow()
    event.cancel_reason = data.reason
    db.commit()
    db.refresh(event)
    return event


@router.post("/{event_id}/restore", response_model=schemas.EventOut)
def restore_event(event_id: int, db: Session = Depends(get_db), current_user=Depends(require_organizer)):
    """Undo a cancellation."""
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_manager(db, event, current_user)
    if not event.cancelled:
        raise HTTPException(status_code=400, detail="Event is not cancelled")
    event.cancelled_at = None
    event.cancel_reason = None
    db.commit()
    db.refresh(event)
    return event
