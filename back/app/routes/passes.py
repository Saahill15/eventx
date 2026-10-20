from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.auth.dependencies import get_current_user
import uuid

router = APIRouter()

@router.post("/{event_id}/register", response_model=schemas.PassOut)
def register_pass(event_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Register for a standalone city event. Fest events use the entry-pass + /fest-events flow instead."""
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event or event.status != models.StatusEnum.approved:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.event_type != models.EventTypeEnum.city:
        raise HTTPException(
            status_code=400,
            detail="This is a fest event: get the fest entry pass, then register for the event from the fest page",
        )
    existing = db.query(models.Pass).filter(
        models.Pass.user_id == current_user.id,
        models.Pass.event_id == event_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already registered")
    new_pass = models.Pass(
        user_id=current_user.id,
        event_id=event_id,
        pass_code=uuid.uuid4().hex.upper()[:12],
        payment_status="free" if event.is_free else "pending",
    )
    db.add(new_pass)
    db.commit()
    db.refresh(new_pass)
    return new_pass

@router.get("/my", response_model=list[schemas.PassOut])
def my_passes(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return db.query(models.Pass).filter(models.Pass.user_id == current_user.id).order_by(models.Pass.created_at.desc()).all()
