"""
Handing a fest to another organiser. The fest's director offers it; nothing changes until the other person accepts.
An admin can also move a fest straight away (for example when a director has left the college).

  POST   /api/fests/{slug}/transfer                     offer the fest to another organiser (director only)
  GET    /api/fests/{slug}/transfer                     the open offer, if any (fest staff)
  DELETE /api/fests/{slug}/transfer                     withdraw the offer (director or admin)
  GET    /api/users/me/fest-transfers                   offers waiting for me
  POST   /api/fest-transfers/{id}/accept | /decline     answer an offer (the person it was made to)
  POST   /api/admin/fests/{slug}/owner                  admin: make someone the director now
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth.dependencies import get_current_user, require_admin
from app.database import get_db
from app.permissions import can_host_fests, is_fest_staff

router = APIRouter()

OWNER = models.FestMemberRoleEnum.owner


def _fest(db: Session, slug: str) -> models.Fest:
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    return fest


def _is_director(db: Session, fest: models.Fest, user: models.User) -> bool:
    return db.query(models.FestMember).filter(models.FestMember.fest_id == fest.id, models.FestMember.user_id == user.id, models.FestMember.role == OWNER).first() is not None


def _pending(db: Session, fest: models.Fest) -> Optional[models.FestTransfer]:
    return db.query(models.FestTransfer).filter(models.FestTransfer.fest_id == fest.id, models.FestTransfer.status == "pending").first()


def _check_new_director(db: Session, fest: models.Fest, user: Optional[models.User]) -> models.User:
    """Only an active organiser who is set up for the fest's college can run it."""
    if not user or user.is_active is False:
        raise HTTPException(status_code=404, detail="No HiveOut account with that email")
    if user.role != models.RoleEnum.organizer:
        raise HTTPException(status_code=400, detail="That person is not an organiser yet. An admin has to make them one first.")
    if not can_host_fests(user):
        raise HTTPException(status_code=400, detail="That organiser is not switched on for fests yet. An admin has to enable fest hosting on their account first.")
    if fest.college_id and not db.query(models.OrganizerCollege).filter(models.OrganizerCollege.user_id == user.id, models.OrganizerCollege.college_id == fest.college_id).first():
        college = fest.college.name if fest.college else "this fest's college"
        raise HTTPException(status_code=400, detail=f"That organiser is not set up for {college}. An admin has to add the college to their account first.")
    if _is_director(db, fest, user):
        raise HTTPException(status_code=400, detail="That person already runs this fest")
    return user


def _hand_over(db: Session, fest: models.Fest, new_director: models.User, keep_previous: bool) -> None:
    """Make `new_director` the fest's only director. The previous director stays as core team, or leaves the team."""
    for member in db.query(models.FestMember).filter(models.FestMember.fest_id == fest.id, models.FestMember.role == OWNER).all():
        if member.user_id == new_director.id:
            continue
        if keep_previous:
            member.role = models.FestMemberRoleEnum.core
        else:
            db.delete(member)
    membership = db.query(models.FestMember).filter(models.FestMember.fest_id == fest.id, models.FestMember.user_id == new_director.id).first()
    if membership:
        membership.role = OWNER
    else:
        db.add(models.FestMember(fest_id=fest.id, user_id=new_director.id, role=OWNER))


def _out(t: models.FestTransfer) -> schemas.TransferOut:
    return schemas.TransferOut(
        id=t.id, fest_slug=t.fest.slug, fest_name=t.fest.name,
        from_name=t.from_user.name if t.from_user else None, from_email=t.from_user.email if t.from_user else None,
        to_name=t.to_user.name if t.to_user else None, to_email=t.to_user.email if t.to_user else None,
        status=t.status, keep_previous_owner=t.keep_previous_owner, created_at=t.created_at,
    )


def _find_user(db: Session, email: str) -> Optional[models.User]:
    return db.query(models.User).filter(func.lower(models.User.email) == email.lower()).first()


@router.post("/fests/{slug}/transfer", response_model=schemas.TransferOut, status_code=201)
def offer_fest(slug: str, data: schemas.TransferCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    if not _is_director(db, fest, user):
        raise HTTPException(status_code=403, detail="Only the fest's director can hand it over")
    target = _check_new_director(db, fest, _find_user(db, data.email))
    old = _pending(db, fest)
    if old:  # a new offer replaces the old one
        old.status, old.decided_at = "cancelled", datetime.utcnow()
    transfer = models.FestTransfer(fest_id=fest.id, from_user_id=user.id, to_user_id=target.id, keep_previous_owner=data.keep_me, created_at=datetime.utcnow())
    db.add(transfer)
    db.commit()
    db.refresh(transfer)
    return _out(transfer)


@router.get("/fests/{slug}/transfer", response_model=Optional[schemas.TransferOut])
def open_offer(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    if not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=404, detail="Fest not found")
    t = _pending(db, fest)
    return _out(t) if t else None


@router.delete("/fests/{slug}/transfer", response_model=schemas.TransferOut)
def withdraw_offer(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    if not (_is_director(db, fest, user) or user.role == models.RoleEnum.admin):
        raise HTTPException(status_code=403, detail="Only the fest's director can withdraw the offer")
    t = _pending(db, fest)
    if not t:
        raise HTTPException(status_code=404, detail="There is no open offer for this fest")
    t.status, t.decided_at = "cancelled", datetime.utcnow()
    db.commit()
    return _out(t)


@router.get("/users/me/fest-transfers", response_model=List[schemas.TransferOut])
def offers_for_me(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    rows = db.query(models.FestTransfer).filter(models.FestTransfer.to_user_id == user.id, models.FestTransfer.status == "pending").order_by(models.FestTransfer.created_at).all()
    return [_out(t) for t in rows]


def _answer(transfer_id: int, accept: bool, db: Session, user: models.User) -> schemas.TransferOut:
    t = db.query(models.FestTransfer).filter(models.FestTransfer.id == transfer_id).first()
    if not t or t.to_user_id != user.id:
        raise HTTPException(status_code=404, detail="Offer not found")
    if t.status != "pending":
        raise HTTPException(status_code=400, detail="This offer has already been answered or withdrawn")
    if accept:
        # Things may have changed since the offer was made: check again
        _check_new_director(db, t.fest, user)
        if not _is_director(db, t.fest, t.from_user):
            raise HTTPException(status_code=400, detail="The person who offered this fest no longer runs it")
        _hand_over(db, t.fest, user, t.keep_previous_owner)
    t.status, t.decided_at = ("accepted" if accept else "declined"), datetime.utcnow()
    db.commit()
    db.refresh(t)
    return _out(t)


@router.post("/fest-transfers/{transfer_id}/accept", response_model=schemas.TransferOut)
def accept_offer(transfer_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return _answer(transfer_id, True, db, user)


@router.post("/fest-transfers/{transfer_id}/decline", response_model=schemas.TransferOut)
def decline_offer(transfer_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return _answer(transfer_id, False, db, user)


@router.post("/admin/fests/{slug}/owner")
def admin_set_director(slug: str, data: schemas.AdminOwnerChange, db: Session = Depends(get_db), _=Depends(require_admin)):
    """Make an organiser the fest's director straight away. Any open offer is withdrawn."""
    fest = _fest(db, slug)
    target = _check_new_director(db, fest, _find_user(db, data.email))
    t = _pending(db, fest)
    if t:
        t.status, t.decided_at = "cancelled", datetime.utcnow()
    _hand_over(db, fest, target, data.keep_previous_owner)
    db.commit()
    return {"message": f"{target.name} now runs {fest.name}"}
