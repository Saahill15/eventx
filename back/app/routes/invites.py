"""
Team invitations and the account notices behind the bell icon.

  GET    /api/fests/{slug}/invites                          pending invitations for the fest (fest staff)
  DELETE /api/fests/{slug}/invites/{id}                     withdraw an invitation (fest staff)
  POST   /api/fest-invites/{id}/accept | /decline           answer an invitation (the person it was sent to)
  GET    /api/users/me/account-notices                      newest first
  GET    /api/users/me/account-notices/unread-count
  POST   /api/users/me/account-notices/read-all
  POST   /api/users/me/account-notices/{id}/read
"""

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, notices, schemas
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.permissions import is_fest_staff

router = APIRouter()
notices_router = APIRouter()


def _open_invite(db: Session, invite_id: int, user: models.User) -> models.FestInvite:
    invite = db.query(models.FestInvite).filter(models.FestInvite.id == invite_id, models.FestInvite.user_id == user.id).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if invite.status != "pending":
        raise HTTPException(status_code=400, detail="This invitation is no longer open")
    return invite


def _answer(db: Session, invite: models.FestInvite, user: models.User, accept: bool) -> models.FestInvite:
    now = datetime.utcnow()
    if accept:
        # Checked again: the verification may have run out since the invitation was sent
        # 403 tells the app to send the person to verify their student status. The invitation stays open meanwhile
        if not user.is_student_verified:
            raise HTTPException(status_code=403, detail="Only verified students can join a fest team. Verify your student status, then accept again. Your invitation stays open.")
        already = db.query(models.FestMember).filter(models.FestMember.fest_id == invite.fest_id, models.FestMember.user_id == user.id).first()
        if not already:
            db.add(models.FestMember(fest_id=invite.fest_id, user_id=user.id, role=models.FestMemberRoleEnum(invite.role)))
    invite.status = "accepted" if accept else "declined"
    invite.decided_at = now
    for n in db.query(models.AccountNotice).filter(models.AccountNotice.invite_id == invite.id, models.AccountNotice.user_id == user.id, models.AccountNotice.read_at.is_(None)).all():
        n.read_at = now
    verb = "joined" if accept else "declined"
    notices.notify(
        db, invite.invited_by_id, "fest_invite_answer",
        title=f"{user.name} {verb} the team",
        body=f"{user.name} {verb} your invitation to {invite.fest.name}.",
        invite_id=invite.id,
    )
    db.commit()
    db.refresh(invite)
    return invite


# ─── Fest staff: see and withdraw invitations ────────────────────────────────

@router.get("/fests/{slug}/invites", response_model=List[schemas.FestInviteOut])
def list_invites(slug: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    if not is_fest_staff(db, fest.id, current_user):
        raise HTTPException(status_code=403, detail="Must be a fest owner or core member to see invitations")
    rows = (
        db.query(models.FestInvite)
        .filter(models.FestInvite.fest_id == fest.id, models.FestInvite.status == "pending")
        .order_by(models.FestInvite.created_at.desc())
        .all()
    )
    return [notices.invite_out(r) for r in rows]


@router.delete("/fests/{slug}/invites/{invite_id}", response_model=schemas.FestInviteOut)
def withdraw_invite(slug: str, invite_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    if not is_fest_staff(db, fest.id, current_user):
        raise HTTPException(status_code=403, detail="Must be a fest owner or core member to withdraw invitations")
    invite = db.query(models.FestInvite).filter(models.FestInvite.id == invite_id, models.FestInvite.fest_id == fest.id).first()
    if not invite or invite.status != "pending":
        raise HTTPException(status_code=404, detail="Invitation not found")
    if invite.role in ("owner", "core") and current_user.role != models.RoleEnum.admin:
        member = db.query(models.FestMember).filter(models.FestMember.fest_id == fest.id, models.FestMember.user_id == current_user.id).first()
        if not member or member.role != models.FestMemberRoleEnum.owner:
            raise HTTPException(status_code=403, detail="Only the fest owner can withdraw a core invitation")
    invite.status = "cancelled"
    invite.decided_at = datetime.utcnow()
    db.commit()
    db.refresh(invite)
    return notices.invite_out(invite)


# ─── The invited person: accept or decline ───────────────────────────────────

@router.post("/fest-invites/{invite_id}/accept", response_model=schemas.FestInviteOut)
def accept_invite(invite_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    invite = _open_invite(db, invite_id, current_user)
    return notices.invite_out(_answer(db, invite, current_user, accept=True))


@router.post("/fest-invites/{invite_id}/decline", response_model=schemas.FestInviteOut)
def decline_invite(invite_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    invite = _open_invite(db, invite_id, current_user)
    return notices.invite_out(_answer(db, invite, current_user, accept=False))


# ─── Account notices (bell icon) ─────────────────────────────────────────────

def _notice_out(n: models.AccountNotice) -> schemas.AccountNoticeOut:
    inv = n.invite
    return schemas.AccountNoticeOut(
        id=n.id, kind=n.kind, title=n.title, body=n.body, created_at=n.created_at, read_at=n.read_at,
        invite_id=n.invite_id, invite_status=inv.status if inv else None,
        fest_slug=inv.fest.slug if inv and inv.fest else None, fest_name=inv.fest.name if inv and inv.fest else None,
        role=inv.role if inv else None,
    )


@notices_router.get("/account-notices", response_model=List[schemas.AccountNoticeOut])
def list_notices(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    rows = (
        db.query(models.AccountNotice)
        .filter(models.AccountNotice.user_id == current_user.id)
        .order_by(models.AccountNotice.created_at.desc(), models.AccountNotice.id.desc())
        .limit(50)
        .all()
    )
    return [_notice_out(n) for n in rows]


@notices_router.get("/account-notices/unread-count", response_model=schemas.NoticeCount)
def unread_count(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    count = (
        db.query(models.AccountNotice)
        .filter(models.AccountNotice.user_id == current_user.id, models.AccountNotice.read_at.is_(None))
        .count()
    )
    return schemas.NoticeCount(count=count)


@notices_router.post("/account-notices/read-all", response_model=schemas.NoticeCount)
def read_all(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    now = datetime.utcnow()
    db.query(models.AccountNotice).filter(models.AccountNotice.user_id == current_user.id, models.AccountNotice.read_at.is_(None)).update({"read_at": now}, synchronize_session=False)
    db.commit()
    return schemas.NoticeCount(count=0)


@notices_router.post("/account-notices/{notice_id}/read", response_model=schemas.AccountNoticeOut)
def read_one(notice_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    n = db.query(models.AccountNotice).filter(models.AccountNotice.id == notice_id, models.AccountNotice.user_id == current_user.id).first()
    if not n:
        raise HTTPException(status_code=404, detail="Notice not found")
    if n.read_at is None:
        n.read_at = datetime.utcnow()
        db.commit()
        db.refresh(n)
    return _notice_out(n)
