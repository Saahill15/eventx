"""
Announcements from a fest committee.

  POST   /api/fests/{slug}/announcements        post one (owner / core / admin), optionally emailed
  GET    /api/fests/{slug}/announcements        read them (public for live fests)
  DELETE /api/fests/{slug}/announcements/{id}   remove one
  GET    /api/users/me/notifications            announcements from fests the user holds a pass for
"""

import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth.dependencies import get_current_user, get_optional_user
from app.database import SessionLocal, get_db
from app.mailer import MailFailed, MailNotConfigured, send_email
from app.permissions import can_view_fest, is_fest_staff

log = logging.getLogger("hiveout.announcements")
router = APIRouter()
notifications_router = APIRouter()

MAX_PER_DAY = 10


def _site_url() -> str:
    return os.getenv("SITE_URL", "http://localhost:3000").rstrip("/")


def _out(a: models.Announcement) -> schemas.AnnouncementOut:
    return schemas.AnnouncementOut(
        id=a.id, fest_id=a.fest_id, fest_slug=a.fest.slug if a.fest else None, fest_name=a.fest.name if a.fest else None,
        event_id=a.event_id, event_title=a.event.title if a.event else None, title=a.title, body=a.body,
        email_requested=a.email_requested, emails_sent=a.emails_sent, emails_failed=a.emails_failed, created_at=a.created_at,
    )


def recipients(db: Session, fest: models.Fest, event: Optional[models.Event]) -> List[models.User]:
    """People with registrations for the event, or everyone holding an approved pass for the fest."""
    if event is not None:
        users = (
            db.query(models.User)
            .join(models.FestPass, models.FestPass.user_id == models.User.id)
            .join(models.EventRegistration, models.EventRegistration.fest_pass_id == models.FestPass.id)
            .filter(
                models.EventRegistration.event_id == event.id,
                models.EventRegistration.approval_status.in_([models.RegApprovalStatusEnum.approved, models.RegApprovalStatusEnum.pending]),
            )
            .all()
        )
    else:
        users = (
            db.query(models.User)
            .join(models.FestPass, models.FestPass.user_id == models.User.id)
            .filter(models.FestPass.fest_id == fest.id, models.FestPass.status == models.FestPassStatusEnum.approved)
            .all()
        )
    seen, out = set(), []
    for u in users:
        if u.id not in seen and u.email and u.is_active is not False:
            seen.add(u.id)
            out.append(u)
    return out


def _send_all(announcement_id: int, subject: str, text: str, addresses: List[str]) -> None:
    """Runs after the response: email everyone, then record how many went out."""
    sent = failed = 0
    for address in addresses:
        try:
            send_email(address, subject, text)
            sent += 1
        except (MailFailed, MailNotConfigured) as exc:
            failed += 1
            log.warning("Could not email an announcement recipient: %s", exc.__class__.__name__)
    db = SessionLocal()
    try:
        row = db.query(models.Announcement).filter(models.Announcement.id == announcement_id).first()
        if row:
            row.emails_sent, row.emails_failed = sent, failed
            db.commit()
    finally:
        db.close()


def _email_text(fest: models.Fest, title: str, body: str) -> str:
    return f"{title}\n\n{body}\n\nFrom {fest.name} on HiveOut: {_site_url()}/fests/{fest.slug}"


def _create(db: Session, fest: models.Fest, event: Optional[models.Event], author: models.User, title: str, body: str, email: bool, background: BackgroundTasks) -> models.Announcement:
    row = models.Announcement(fest_id=fest.id, event_id=event.id if event else None, author_id=author.id, title=title, body=body, email_requested=email, created_at=datetime.utcnow())
    db.add(row)
    db.commit()
    db.refresh(row)
    if email:
        addresses = [u.email for u in recipients(db, fest, event)]
        if addresses:
            background.add_task(_send_all, row.id, f"[{fest.name}] {title}", _email_text(fest, title, body), addresses)
    return row


def announce_cancellation(db: Session, event: models.Event, author: models.User, background: BackgroundTasks) -> None:
    fest = db.query(models.Fest).filter(models.Fest.id == event.fest_id).first()
    if fest:
        _create(db, fest, event, author, f"Cancelled: {event.title}", event.cancel_reason or "This event has been cancelled.", True, background)


@router.post("/{slug}/announcements", response_model=schemas.AnnouncementOut, status_code=201)
def post_announcement(slug: str, data: schemas.AnnouncementIn, background: BackgroundTasks, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    if not is_fest_staff(db, fest.id, current_user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can post announcements")
    if fest.status != models.FestStatusEnum.live:
        raise HTTPException(status_code=400, detail="Make the fest live before posting announcements")
    event = None
    if data.event_id is not None:
        event = db.query(models.Event).filter(models.Event.id == data.event_id, models.Event.fest_id == fest.id).first()
        if not event:
            raise HTTPException(status_code=400, detail="That event is not part of this fest")
    today = db.query(models.Announcement).filter(models.Announcement.fest_id == fest.id, models.Announcement.author_id != 0, models.Announcement.created_at > datetime.utcnow() - timedelta(days=1)).count()
    if today >= MAX_PER_DAY:
        raise HTTPException(status_code=429, detail="Daily announcement limit reached. Try again tomorrow.")
    return _out(_create(db, fest, event, current_user, data.title, data.body, data.send_email, background))


@router.get("/{slug}/announcements", response_model=List[schemas.AnnouncementOut])
def list_announcements(slug: str, event_id: Optional[int] = Query(default=None), db: Session = Depends(get_db), current_user=Depends(get_optional_user)):
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest or not can_view_fest(db, fest, current_user):
        raise HTTPException(status_code=404, detail="Fest not found")
    q = db.query(models.Announcement).filter(models.Announcement.fest_id == fest.id)
    if event_id is not None:
        q = q.filter((models.Announcement.event_id == event_id) | (models.Announcement.event_id.is_(None)))
    return [_out(a) for a in q.order_by(models.Announcement.created_at.desc()).limit(100).all()]


@router.delete("/{slug}/announcements/{announcement_id}", status_code=204)
def delete_announcement(slug: str, announcement_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest or not is_fest_staff(db, fest.id, current_user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can remove announcements")
    row = db.query(models.Announcement).filter(models.Announcement.id == announcement_id, models.Announcement.fest_id == fest.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Announcement not found")
    db.delete(row)
    db.commit()


@notifications_router.get("/notifications", response_model=List[schemas.AnnouncementOut])
def my_notifications(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Announcements from every fest the user has a pass for, newest first. Event announcements only for events they registered for."""
    fest_ids = [fp.fest_id for fp in db.query(models.FestPass).filter(models.FestPass.user_id == current_user.id).all()]
    if not fest_ids:
        return []
    my_events = {
        r.event_id for r in db.query(models.EventRegistration)
        .join(models.FestPass, models.EventRegistration.fest_pass_id == models.FestPass.id)
        .filter(models.FestPass.user_id == current_user.id).all()
    }
    rows = db.query(models.Announcement).filter(models.Announcement.fest_id.in_(fest_ids)).order_by(models.Announcement.created_at.desc()).limit(100).all()
    return [_out(a) for a in rows if a.event_id is None or a.event_id in my_events][:50]
