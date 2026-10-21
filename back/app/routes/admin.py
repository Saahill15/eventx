from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app import models, schemas
from app.auth.dependencies import require_admin
from app.routes.student import verify_user
from app.fest_review import fest_missing

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


def _valid_partner_colleges(db: Session, ids: List[int]) -> List[models.College]:
    colleges = db.query(models.College).filter(models.College.id.in_(ids)).all() if ids else []
    if not ids or len(colleges) != len(set(ids)):
        raise HTTPException(status_code=400, detail="Pick at least one existing college")
    not_partner = [c.name for c in colleges if c.partner_status != "partner"]
    if not_partner:
        raise HTTPException(status_code=400, detail="Not a partner college yet: " + ", ".join(not_partner))
    return colleges


@router.post("/users/{user_id}/role", response_model=schemas.AdminUserOut)
def set_user_role(
    user_id: int,
    data: schemas.RoleChange,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """
    Make an account an organiser for one or more partner colleges, or return it to a normal member.
    Admins are not managed here.
    """
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
        user.organizer_colleges.clear()
    else:
        colleges = _valid_partner_colleges(db, data.college_ids)
        user.organizer_colleges.clear()
        db.flush()
        for c in colleges:
            user.organizer_colleges.append(models.OrganizerCollege(college_id=c.id))
    user.role = new_role
    db.commit()
    db.refresh(user)
    return user


@router.put("/users/{user_id}/colleges", response_model=schemas.AdminUserOut)
def set_organizer_colleges(user_id: int, data: schemas.CollegeAssignment, db: Session = Depends(get_db), _=Depends(require_admin)):
    """Change which colleges an existing organiser may list fests for."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or user.role != models.RoleEnum.organizer:
        raise HTTPException(status_code=404, detail="Organiser not found")
    colleges = _valid_partner_colleges(db, data.college_ids)
    user.organizer_colleges.clear()
    db.flush()
    for c in colleges:
        user.organizer_colleges.append(models.OrganizerCollege(college_id=c.id))
    db.commit()
    db.refresh(user)
    return user


# ─── Colleges (partnership details) ──────────────────────────────────────────

@router.get("/colleges", response_model=List[schemas.CollegeAdminOut])
def list_colleges_admin(db: Session = Depends(get_db), _=Depends(require_admin)):
    """Every college with its private partnership details."""
    return db.query(models.College).order_by(models.College.name).all()


# ─── Fest review ─────────────────────────────────────────────────────────────

def _review_view(db: Session, fest: models.Fest) -> schemas.FestReviewOut:
    events = db.query(models.Event).filter(models.Event.fest_id == fest.id).order_by(models.Event.date).all()
    owners = (
        db.query(models.FestMember)
        .filter(models.FestMember.fest_id == fest.id, models.FestMember.role == models.FestMemberRoleEnum.owner)
        .all()
    )
    return schemas.FestReviewOut(
        fest=schemas.FestManageOut.model_validate(fest),
        college=schemas.ReviewCollege.model_validate(fest.college, from_attributes=True) if fest.college else None,
        events=[schemas.ReviewEvent.model_validate(e, from_attributes=True) for e in events],
        missing=fest_missing(fest, events),
        owners=[f"{m.user_name} <{m.user_email}>" for m in owners],
    )


@router.get("/fests", response_model=List[schemas.FestReviewOut])
def list_fests_for_review(
    review_status: str = Query(default="in_review", pattern="^(draft|in_review|changes_requested|approved|rejected)$"),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    fests = db.query(models.Fest).filter(models.Fest.review_status == review_status).order_by(models.Fest.submitted_at).limit(100).all()
    return [_review_view(db, f) for f in fests]


@router.get("/fests/{slug}", response_model=schemas.FestReviewOut)
def get_fest_for_review(slug: str, db: Session = Depends(get_db), _=Depends(require_admin)):
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    return _review_view(db, fest)


def _decide_fest(db: Session, slug: str, admin: models.User, outcome: str, note: Optional[str]) -> models.Fest:
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    if fest.review_status != "in_review":
        raise HTTPException(status_code=400, detail="This fest is not waiting for review")
    fest.review_status = outcome
    fest.review_note = note
    fest.reviewed_by = admin.id
    fest.reviewed_at = datetime.utcnow()
    return fest


@router.post("/fests/{slug}/approve", response_model=schemas.FestReviewOut)
def approve_fest(slug: str, data: Optional[schemas.ReviewNote] = None, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    """Approve the fest. The organiser can now make it live. A note is optional."""
    fest = _decide_fest(db, slug, admin, "approved", data.note if data else None)
    events = db.query(models.Event).filter(models.Event.fest_id == fest.id).all()
    missing = fest_missing(fest, events)
    if missing:
        raise HTTPException(status_code=400, detail={"message": "The fest is incomplete", "missing": missing})
    db.commit()
    db.refresh(fest)
    return _review_view(db, fest)


@router.post("/fests/{slug}/request-changes", response_model=schemas.FestReviewOut)
def request_fest_changes(slug: str, data: schemas.ReviewNote, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    """Send it back to the organiser with a note saying what to fix."""
    fest = _decide_fest(db, slug, admin, "changes_requested", data.note)
    db.commit()
    db.refresh(fest)
    return _review_view(db, fest)


@router.post("/fests/{slug}/reject", response_model=schemas.FestReviewOut)
def reject_fest(slug: str, data: schemas.ReviewNote, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    """Decline the fest. The organiser sees the reason and may fix things and submit again."""
    fest = _decide_fest(db, slug, admin, "rejected", data.note)
    db.commit()
    db.refresh(fest)
    return _review_view(db, fest)


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
