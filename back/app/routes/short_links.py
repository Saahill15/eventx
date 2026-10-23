"""
Custom short addresses (hiveout.in/name) for fests, built so events can hold one too later.

  GET    /api/short-links/check?name=...          is a name free? (organisers)
  GET    /api/short-links/resolve/{name}          where a short name leads (public; only for something that is live)
  GET    /api/short-links/fests/{slug}            the link a fest holds
  PUT    /api/short-links/fests/{slug}            claim a name for the fest (replaces the one it holds)
  DELETE /api/short-links/fests/{slug}            give the name up
"""

import time
from collections import defaultdict, deque
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth.dependencies import get_current_user, require_organizer
from app.database import get_db
from app.entitlements import SHORT_LINKS, has_feature, require_feature
from app.permissions import can_view_fest, is_fest_staff
from app.short_links import MESSAGES, check_name, clean

router = APIRouter()

# Checking names is cheap, but it should not be a way to list every name that exists
_checks = defaultdict(deque)
CHECKS_PER_MINUTE = 40


def _rate_limit(user_id: int) -> None:
    q = _checks[user_id]
    cutoff = time.monotonic() - 60
    while q and q[0] < cutoff:
        q.popleft()
    if len(q) >= CHECKS_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Too many checks. Wait a minute and try again.")
    q.append(time.monotonic())


def reset_rate_limit():
    _checks.clear()


def _fest(db: Session, slug: str, user: models.User) -> models.Fest:
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest or not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=404, detail="Fest not found")
    return fest


def _out(db: Session, fest: models.Fest, user: models.User) -> schemas.ShortLinkOut:
    row = db.query(models.ShortLink).filter(models.ShortLink.target_type == "fest", models.ShortLink.target_id == fest.id).first()
    return schemas.ShortLinkOut(
        name=row.name if row else None, path=f"/{row.name}" if row else None,
        target_path=f"/fests/{fest.slug}", enabled=has_feature(user, SHORT_LINKS),
    )


@router.get("/check", response_model=schemas.ShortLinkCheck)
def check(
    name: str = Query(max_length=80),
    fest: str = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_organizer),
):
    """Is this name free? Pass `fest` to treat that fest's own current name as free."""
    _rate_limit(user.id)
    name = clean(name)
    own = None
    if fest:
        f = _fest(db, fest, user)
        own = ("fest", f.id)
    reason = check_name(db, name, own)
    return schemas.ShortLinkCheck(name=name, available=reason is None, reason=reason)


@router.get("/resolve/{name}")
def resolve(name: str, db: Session = Depends(get_db)):
    """Where a short name leads. Nothing is revealed about a fest that is not public."""
    row = db.query(models.ShortLink).filter(models.ShortLink.name == clean(name)).first()
    if row and row.target_type == "fest":
        fest = db.query(models.Fest).filter(models.Fest.id == row.target_id).first()
        if fest and can_view_fest(db, fest, None):
            return {"path": f"/fests/{fest.slug}"}
    raise HTTPException(status_code=404, detail="Not found")


@router.get("/fests/{slug}", response_model=schemas.ShortLinkOut)
def get_fest_link(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return _out(db, _fest(db, slug, user), user)


@router.put("/fests/{slug}", response_model=schemas.ShortLinkOut)
def claim_fest_link(slug: str, data: schemas.ShortLinkIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug, user)
    require_feature(user, SHORT_LINKS)
    name = clean(data.name)
    reason = check_name(db, name, ("fest", fest.id))
    if reason:
        raise HTTPException(status_code=409 if reason == "taken" else 400, detail=MESSAGES[reason])
    row = db.query(models.ShortLink).filter(models.ShortLink.target_type == "fest", models.ShortLink.target_id == fest.id).first()
    try:
        if row:
            row.name = name  # renaming frees the old name
        else:
            db.add(models.ShortLink(name=name, target_type="fest", target_id=fest.id, created_by=user.id, created_at=datetime.utcnow()))
        db.commit()
    except IntegrityError:
        db.rollback()  # someone took the name between the check and now
        raise HTTPException(status_code=409, detail=MESSAGES["taken"])
    return _out(db, fest, user)


@router.delete("/fests/{slug}", response_model=schemas.ShortLinkOut)
def release_fest_link(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug, user)
    db.query(models.ShortLink).filter(models.ShortLink.target_type == "fest", models.ShortLink.target_id == fest.id).delete()
    db.commit()
    return _out(db, fest, user)
