from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app import models, schemas
from app.auth.dependencies import require_admin

router = APIRouter()

@router.get("/users", response_model=List[schemas.AdminUserOut])
def search_users(
    q: str = Query(default="", max_length=100),
    role: Optional[str] = Query(default=None, pattern="^(user|organizer|admin)$"),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """Find accounts by name or email so an admin can promote them. Shows at most 50."""
    query = db.query(models.User)
    term = q.strip().lower()
    if term:
        like = f"%{term}%"
        query = query.filter(or_(func.lower(models.User.email).like(like), func.lower(models.User.name).like(like)))
    if role:
        query = query.filter(models.User.role == role)
    return query.order_by(models.User.created_at.desc()).limit(50).all()


@router.post("/users/{user_id}/role", response_model=schemas.AdminUserOut)
def set_user_role(
    user_id: int,
    data: schemas.RoleChange,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """Make an account an organiser, or return it to a normal user. Admins are not managed here."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot change your own role")
    if user.role == models.RoleEnum.admin:
        raise HTTPException(status_code=400, detail="Admin accounts cannot be changed here")
    new_role = models.RoleEnum(data.role)
    if new_role == models.RoleEnum.user:
        owns_fest = (
            db.query(models.FestMember)
            .filter(models.FestMember.user_id == user.id, models.FestMember.role == models.FestMemberRoleEnum.owner)
            .first()
        )
        if owns_fest:
            raise HTTPException(status_code=400, detail="This person owns a fest. Transfer the fest to someone else before removing organiser access.")
    user.role = new_role
    db.commit()
    db.refresh(user)
    return user

@router.get("/events/pending")
def get_pending_events(db: Session = Depends(get_db), _=Depends(require_admin)):
    return db.query(models.Event).filter(models.Event.status == "pending").all()

@router.post("/events/{event_id}/approve")
def approve_event(event_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    event.status = models.StatusEnum.approved
    db.commit()
    return {"message": "Event approved"}

@router.post("/events/{event_id}/reject")
def reject_event(event_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    event.status = models.StatusEnum.rejected
    db.commit()
    return {"message": "Event rejected"}