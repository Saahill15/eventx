"""
Gate work on the day of the fest, by scanning a pass QR code.

  GET  /api/fests/{slug}/gate/lookup?code=...   show who a pass belongs to (any committee member)
  POST /api/fests/{slug}/gate/check-in          let someone in (any committee member, volunteers included)
  POST /api/fests/{slug}/gate/undo              reverse a wrong scan (owner / core / admin)
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app import models, schemas
from app.permissions import is_fest_member, is_fest_staff

router = APIRouter()


def _fest_for_gate(db: Session, slug: str, user: models.User, staff_only: bool = False) -> models.Fest:
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    allowed = is_fest_staff(db, fest.id, user) if staff_only else is_fest_member(db, fest.id, user)
    if not allowed:
        raise HTTPException(status_code=403, detail="Only this fest's committee can do gate work")
    return fest


def _pass_by_code(db: Session, fest: models.Fest, code: str) -> models.FestPass:
    fp = db.query(models.FestPass).filter(models.FestPass.qr_code == code, models.FestPass.fest_id == fest.id).first()
    if not fp:
        raise HTTPException(status_code=404, detail="No pass with that code for this fest")
    return fp


def _summary(fp: models.FestPass) -> schemas.GatePassOut:
    return schemas.GatePassOut(
        pass_id=fp.id,
        user_name=fp.user.name if fp.user else None,
        user_email=fp.user.email if fp.user else None,
        status=fp.status.value,
        checked_in=bool(fp.checked_in),
        checked_in_at=fp.checked_in_at,
        registrations=[
            schemas.GateRegistration(event_id=r.event_id, title=r.event.title, approval_status=r.approval_status.value, attended=bool(r.attended))
            for r in fp.registrations
        ],
    )


@router.get("/{slug}/gate/lookup", response_model=schemas.GatePassOut)
def lookup(slug: str, code: str = Query(min_length=8, max_length=100), db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    fest = _fest_for_gate(db, slug, current_user)
    return _summary(_pass_by_code(db, fest, code))


@router.post("/{slug}/gate/check-in", response_model=schemas.GatePassOut)
def check_in(slug: str, data: schemas.QrCodeIn, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    fest = _fest_for_gate(db, slug, current_user)
    fp = _pass_by_code(db, fest, data.qr_code)
    if fp.status != models.FestPassStatusEnum.approved:
        raise HTTPException(status_code=400, detail="Pass is blocked: entry denied")
    if fp.checked_in:
        when = fp.checked_in_at.strftime("%H:%M") if fp.checked_in_at else "earlier"
        raise HTTPException(status_code=400, detail=f"Pass already used at {when}: entry denied")
    fp.checked_in = True
    fp.checked_in_at = datetime.utcnow()
    fp.checked_in_by = current_user.id
    db.commit()
    db.refresh(fp)
    return _summary(fp)


@router.post("/{slug}/gate/undo", response_model=schemas.GatePassOut)
def undo_check_in(slug: str, data: schemas.QrCodeIn, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    fest = _fest_for_gate(db, slug, current_user, staff_only=True)
    fp = _pass_by_code(db, fest, data.qr_code)
    if not fp.checked_in:
        raise HTTPException(status_code=400, detail="This pass has not been checked in")
    fp.checked_in = False
    fp.checked_in_at = None
    fp.checked_in_by = None
    db.commit()
    db.refresh(fp)
    return _summary(fp)
