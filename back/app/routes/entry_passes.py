"""
Routes for Fest Entry Passes (FestPass).
Mounted under /api/fests by main.py — so paths here are relative.

  POST   /api/fests/{slug}/entry-pass       → claim / get existing pass
  GET    /api/fests/{slug}/my-pass          → fetch current user's pass
  POST   /api/fests/{slug}/gate-scan/{pass_id} → QR gate check-in (privileged)
"""

import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.auth.dependencies import get_current_user
from app.permissions import is_fest_member

router = APIRouter()


# ─── POST /fests/{slug}/entry-pass ───────────────────────────────────────────

@router.post("/{slug}/entry-pass", response_model=schemas.FestPassOut, status_code=status.HTTP_201_CREATED)
def claim_entry_pass(
    slug: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Issue a FestPass to the current user for the given fest.
    Entry is always free.
    If the user already has a pass, return it (idempotent).
    """
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    if fest.status != models.FestStatusEnum.live:
        raise HTTPException(status_code=400, detail="Fest is not live yet")

    # Idempotent — return existing pass if already issued
    existing = (
        db.query(models.FestPass)
        .filter(
            models.FestPass.user_id == current_user.id,
            models.FestPass.fest_id == fest.id,
        )
        .first()
    )
    if existing:
        return existing

    fest_pass = models.FestPass(
        user_id    = current_user.id,
        fest_id    = fest.id,
        status     = models.FestPassStatusEnum.approved,
        qr_code    = str(uuid.uuid4()),
        checked_in = False,
    )
    db.add(fest_pass)
    db.commit()
    db.refresh(fest_pass)
    return fest_pass


# ─── GET /fests/{slug}/my-pass ───────────────────────────────────────────────

@router.get("/{slug}/my-pass", response_model=schemas.FestPassOut)
def get_my_pass(
    slug: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return the current user's FestPass for the given fest, or 404 if none."""
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")

    fest_pass = (
        db.query(models.FestPass)
        .filter(
            models.FestPass.user_id == current_user.id,
            models.FestPass.fest_id == fest.id,
        )
        .first()
    )
    if not fest_pass:
        raise HTTPException(status_code=404, detail="No entry pass found for this fest")
    return fest_pass


# ─── POST /fests/{slug}/gate-scan/{pass_id} ──────────────────────────────────

@router.post("/{slug}/gate-scan/{pass_id}", response_model=schemas.FestPassOut)
def gate_scan(
    slug: str,
    pass_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    QR gate verification endpoint.
    Marks a FestPass as checked_in=True.

    Rules:
      - status must be "approved"
      - checked_in must be False
      - Does NOT check event registrations

    Requires: any fest committee member (volunteers included), or admin.
    """
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")

    # Permission: any member of the fest's committee (volunteers work the gate), or an admin
    if not is_fest_member(db, fest.id, current_user):
        raise HTTPException(status_code=403, detail="Gate access requires being on this fest's committee")

    fest_pass = (
        db.query(models.FestPass)
        .filter(
            models.FestPass.id == pass_id,
            models.FestPass.fest_id == fest.id,
        )
        .first()
    )
    if not fest_pass:
        raise HTTPException(status_code=404, detail="Pass not found")

    if fest_pass.status != models.FestPassStatusEnum.approved:
        raise HTTPException(status_code=400, detail="Pass is blocked — entry denied")

    if fest_pass.checked_in:
        raise HTTPException(status_code=400, detail="Pass already used — entry denied")

    fest_pass.checked_in = True
    fest_pass.checked_in_at = datetime.utcnow()
    fest_pass.checked_in_by = current_user.id
    db.commit()
    db.refresh(fest_pass)
    return fest_pass
