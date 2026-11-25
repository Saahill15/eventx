"""
Sponsors and partners of a fest, shown with their logos on the fest's public page.

  GET    /api/fests/{slug}/sponsors              the list, biggest tier first (public once the fest is live)
  POST   /api/fests/{slug}/sponsors              add one (director or core team)
  PATCH  /api/fests/{slug}/sponsors/{id}         change one
  POST   /api/fests/{slug}/sponsors/{id}/move    move one up or down inside its tier
  DELETE /api/fests/{slug}/sponsors/{id}         remove one
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth.dependencies import get_current_user, get_optional_user
from app.database import get_db
from app.permissions import can_view_fest, is_fest_staff

router = APIRouter()


def _fest(db: Session, slug: str) -> models.Fest:
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    return fest


def _require_staff(db: Session, fest: models.Fest, user) -> None:
    if not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can change its sponsors")


def _sponsor(db: Session, fest: models.Fest, sponsor_id: int) -> models.FestSponsor:
    row = db.query(models.FestSponsor).filter(models.FestSponsor.id == sponsor_id, models.FestSponsor.fest_id == fest.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Sponsor not found")
    return row


def _ordered(db: Session, fest_id: int) -> List[models.FestSponsor]:
    return db.query(models.FestSponsor).filter(models.FestSponsor.fest_id == fest_id).order_by(models.FestSponsor.level, models.FestSponsor.position, models.FestSponsor.id).all()


def _name_taken(db: Session, fest: models.Fest, name: str, except_id=None) -> bool:
    q = db.query(models.FestSponsor).filter(models.FestSponsor.fest_id == fest.id, func.lower(models.FestSponsor.name) == name.lower())
    if except_id is not None:
        q = q.filter(models.FestSponsor.id != except_id)
    return q.first() is not None


@router.get("/{slug}/sponsors", response_model=List[schemas.SponsorOut])
def list_sponsors(slug: str, db: Session = Depends(get_db), user=Depends(get_optional_user)):
    fest = _fest(db, slug)
    if not can_view_fest(db, fest, user):
        raise HTTPException(status_code=404, detail="Fest not found")
    return _ordered(db, fest.id)


@router.post("/{slug}/sponsors", response_model=schemas.SponsorOut, status_code=status.HTTP_201_CREATED)
def add_sponsor(slug: str, data: schemas.SponsorIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _require_staff(db, fest, user)
    if db.query(models.FestSponsor).filter(models.FestSponsor.fest_id == fest.id).count() >= schemas.MAX_SPONSORS:
        raise HTTPException(status_code=400, detail=f"A fest can list at most {schemas.MAX_SPONSORS} sponsors")
    if _name_taken(db, fest, data.name):
        raise HTTPException(status_code=400, detail="That sponsor is already listed")
    last = db.query(func.max(models.FestSponsor.position)).filter(models.FestSponsor.fest_id == fest.id, models.FestSponsor.level == data.level).scalar()
    row = models.FestSponsor(
        fest_id=fest.id, name=data.name, level=data.level, tier_label=data.tier_label or schemas.SPONSOR_LEVELS[data.level],
        logo_url=data.logo_url, website_url=data.website_url, blurb=data.blurb or None, position=(last + 1) if last is not None else 0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{slug}/sponsors/{sponsor_id}", response_model=schemas.SponsorOut)
def update_sponsor(slug: str, sponsor_id: int, data: schemas.SponsorUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _require_staff(db, fest, user)
    row = _sponsor(db, fest, sponsor_id)
    updates = data.model_dump(exclude_unset=True)
    if "name" in updates:
        if not updates["name"]:
            raise HTTPException(status_code=400, detail="A sponsor needs a name")
        if _name_taken(db, fest, updates["name"], except_id=row.id):
            raise HTTPException(status_code=400, detail="That sponsor is already listed")
        row.name = updates["name"]
    if updates.get("level") is not None and updates["level"] != row.level:
        # Moving to another tier puts it last there, and it takes that tier's usual label unless a label was given
        last = db.query(func.max(models.FestSponsor.position)).filter(models.FestSponsor.fest_id == fest.id, models.FestSponsor.level == updates["level"]).scalar()
        row.level, row.position = updates["level"], (last + 1) if last is not None else 0
        if "tier_label" not in updates:
            row.tier_label = schemas.SPONSOR_LEVELS[row.level]
    if "tier_label" in updates:
        row.tier_label = updates["tier_label"] or schemas.SPONSOR_LEVELS[row.level]
    for field in ("logo_url", "website_url"):
        if field in updates:
            setattr(row, field, updates[field])
    if "blurb" in updates:
        row.blurb = updates["blurb"] or None
    db.commit()
    db.refresh(row)
    return row


@router.post("/{slug}/sponsors/{sponsor_id}/move", response_model=List[schemas.SponsorOut])
def move_sponsor(slug: str, sponsor_id: int, data: schemas.SponsorMove, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _require_staff(db, fest, user)
    row = _sponsor(db, fest, sponsor_id)
    tier = [s for s in _ordered(db, fest.id) if s.level == row.level]
    for i, s in enumerate(tier):  # settle ties first so a swap always changes the order
        s.position = i
    i = tier.index(row)
    j = i - 1 if data.direction == "up" else i + 1
    if 0 <= j < len(tier):
        tier[i].position, tier[j].position = tier[j].position, tier[i].position
    db.commit()
    return _ordered(db, fest.id)


@router.delete("/{slug}/sponsors/{sponsor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sponsor(slug: str, sponsor_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _require_staff(db, fest, user)
    db.delete(_sponsor(db, fest, sponsor_id))
    db.commit()
