from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app import models, schemas
from app.auth.dependencies import require_admin
from app.routes.student import verify_user

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

# ─── Student verification review ─────────────────────────────────────────────

def _review_row(v: models.StudentVerification) -> schemas.VerificationReview:
    return schemas.VerificationReview(
        id=v.id, user_id=v.user_id, user_name=v.user.name if v.user else None, user_email=v.user.email if v.user else None,
        method=v.method.value, status=v.status.value, college_id=v.college_id, college_name=v.college.name if v.college else None,
        document_type=v.document_type, document_name=v.document_name, has_file=v.document_data is not None, created_at=v.created_at,
    )


@router.get("/student-verifications", response_model=List[schemas.VerificationReview])
def list_verifications(
    status: str = Query(default="pending", pattern="^(pending|approved|rejected)$"),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    rows = (
        db.query(models.StudentVerification)
        .filter(models.StudentVerification.method == models.VerificationMethodEnum.proof, models.StudentVerification.status == status)
        .order_by(models.StudentVerification.created_at)
        .limit(100)
        .all()
    )
    return [_review_row(v) for v in rows]


@router.get("/student-verifications/{verification_id}/file")
def verification_file(verification_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    v = db.query(models.StudentVerification).filter(models.StudentVerification.id == verification_id).first()
    if not v or v.document_data is None:
        raise HTTPException(status_code=404, detail="No document on file")
    return Response(
        content=v.document_data,
        media_type=v.document_mime or "application/octet-stream",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox"},
    )


def _decide(db: Session, verification_id: int, admin: models.User) -> models.StudentVerification:
    v = db.query(models.StudentVerification).filter(models.StudentVerification.id == verification_id).first()
    if not v or v.method != models.VerificationMethodEnum.proof:
        raise HTTPException(status_code=404, detail="Verification not found")
    if v.status != models.VerificationStatusEnum.pending:
        raise HTTPException(status_code=400, detail="This one was already reviewed")
    v.reviewed_by = admin.id
    v.reviewed_at = datetime.utcnow()
    v.document_data = None  # the photo is deleted as soon as a decision is made
    return v


@router.post("/student-verifications/{verification_id}/approve", response_model=schemas.VerificationReview)
def approve_verification(verification_id: int, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    v = _decide(db, verification_id, admin)
    v.status = models.VerificationStatusEnum.approved
    verify_user(db, v.user, v.college_id)
    db.commit()
    db.refresh(v)
    return _review_row(v)


@router.post("/student-verifications/{verification_id}/reject", response_model=schemas.VerificationReview)
def reject_verification(verification_id: int, data: schemas.RejectVerification, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    v = _decide(db, verification_id, admin)
    v.status = models.VerificationStatusEnum.rejected
    v.reject_reason = data.reason
    db.commit()
    db.refresh(v)
    return _review_row(v)
