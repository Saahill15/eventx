from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app import models, schemas
from app.auth.dependencies import get_current_user, get_optional_user
from app.permissions import can_view_fest

router = APIRouter()


# ─── Permission helpers ───────────────────────────────────────────────────────

def _is_fest_privileged(fest: models.Fest, user: models.User, db: Session) -> bool:
    """Return True if user is admin OR a FestMember with role owner/core."""
    if user.role == models.RoleEnum.admin:
        return True
    return (
        db.query(models.FestMember)
        .filter(
            models.FestMember.fest_id == fest.id,
            models.FestMember.user_id == user.id,
            models.FestMember.role.in_([
                models.FestMemberRoleEnum.owner,
                models.FestMemberRoleEnum.core,
            ]),
        )
        .first()
    ) is not None


def _actor_fest_role(fest: models.Fest, user: models.User, db: Session) -> str:
    """'admin', 'owner' or 'core' (callers have already passed the privilege check)."""
    if user.role == models.RoleEnum.admin:
        return "admin"
    member = (
        db.query(models.FestMember)
        .filter(models.FestMember.fest_id == fest.id, models.FestMember.user_id == user.id)
        .first()
    )
    return member.role.value if member else "none"


def _require_fest_privileged(fest: models.Fest, user: models.User, db: Session):
    if not _is_fest_privileged(fest, user, db):
        raise HTTPException(
            status_code=403,
            detail="Must be a fest owner or core member to perform this action",
        )


# ─── GET /fests/ ─────────────────────────────────────────────────────────────
@router.get("/", response_model=List[schemas.FestOut])
def list_fests(db: Session = Depends(get_db)):
    """Return all live fests (public)."""
    return (
        db.query(models.Fest)
        .filter(models.Fest.status == models.FestStatusEnum.live)
        .order_by(models.Fest.created_at.desc())
        .all()
    )


# ─── GET /fests/all ──────────────────────────────────────────────────────────
@router.get("/all", response_model=List[schemas.FestOut])
def list_all_fests(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return all fests regardless of status (admin / organizer only)."""
    if current_user.role not in (models.RoleEnum.admin, models.RoleEnum.organizer):
        raise HTTPException(status_code=403, detail="Forbidden")
    return db.query(models.Fest).order_by(models.Fest.created_at.desc()).all()


# ─── GET /fests/:slug ────────────────────────────────────────────────────────
@router.get("/{slug}", response_model=schemas.FestOut)
def get_fest(slug: str, db: Session = Depends(get_db), current_user=Depends(get_optional_user)):
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest or not can_view_fest(db, fest, current_user):
        raise HTTPException(status_code=404, detail="Fest not found")
    return fest


# ─── GET /fests/:slug/events ─────────────────────────────────────────────────
@router.get("/{slug}/events", response_model=List[schemas.EventOut])
def get_fest_events(slug: str, db: Session = Depends(get_db), current_user=Depends(get_optional_user)):
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest or not can_view_fest(db, fest, current_user):
        raise HTTPException(status_code=404, detail="Fest not found")
    return (
        db.query(models.Event)
        .filter(
            models.Event.fest_id == fest.id,
            models.Event.status == models.StatusEnum.approved,
        )
        .order_by(models.Event.date)
        .all()
    )


# ─── GET /fests/:slug/members ────────────────────────────────────────────────
@router.get("/{slug}/members", response_model=List[schemas.FestMemberOut])
def get_fest_members(
    slug: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List all committee members for a fest (any logged-in user)."""
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    return db.query(models.FestMember).filter(models.FestMember.fest_id == fest.id).all()


# ─── POST /fests/ ────────────────────────────────────────────────────────────
@router.post("/", response_model=schemas.FestOut, status_code=status.HTTP_201_CREATED)
def create_fest(
    payload: schemas.FestCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role not in (models.RoleEnum.admin, models.RoleEnum.organizer):
        raise HTTPException(status_code=403, detail="Forbidden")

    if db.query(models.Fest).filter(models.Fest.slug == payload.slug).first():
        raise HTTPException(status_code=400, detail="Slug already in use")

    fest = models.Fest(
        slug=payload.slug,
        name=payload.name,
        tagline=payload.tagline,
        banner_url=payload.banner_url,
        logo_url=payload.logo_url,
        college_id=payload.college_id,
        status=models.FestStatusEnum.live if payload.status == "live" else models.FestStatusEnum.draft,
    )
    db.add(fest)
    db.flush()  # populate fest.id before creating the membership row

    # The creator is automatically the owner
    db.add(models.FestMember(
        fest_id=fest.id,
        user_id=current_user.id,
        role=models.FestMemberRoleEnum.owner,
    ))
    db.commit()
    db.refresh(fest)
    return fest


# ─── POST /fests/:slug/members ───────────────────────────────────────────────
@router.post("/{slug}/members", response_model=schemas.FestMemberOut, status_code=status.HTTP_201_CREATED)
def add_fest_member(
    slug: str,
    payload: schemas.AddFestMember,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Add or update a committee member. Requires owner / core / admin."""
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")

    _require_fest_privileged(fest, current_user, db)

    try:
        role = models.FestMemberRoleEnum(payload.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role '{payload.role}'. Use: owner, core, volunteer")

    # Only admins may grant the owner role
    if role == models.FestMemberRoleEnum.owner and current_user.role != models.RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Only admins can grant the owner role")

    actor_role = _actor_fest_role(fest, current_user, db)

    target = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Upsert: if already a member, update their role
    existing = (
        db.query(models.FestMember)
        .filter(models.FestMember.fest_id == fest.id, models.FestMember.user_id == payload.user_id)
        .first()
    )
    # Owners can only be changed by admins; core members may only manage volunteers
    if existing and existing.role == models.FestMemberRoleEnum.owner and actor_role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can change an owner's role")
    if actor_role == "core":
        touches_staff = role == models.FestMemberRoleEnum.core or (
            existing and existing.role == models.FestMemberRoleEnum.core
        )
        if touches_staff:
            raise HTTPException(status_code=403, detail="Only the fest owner can add or change core members")
    if existing:
        existing.role = role
        db.commit()
        db.refresh(existing)
        return existing

    member = models.FestMember(fest_id=fest.id, user_id=payload.user_id, role=role)
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


# ─── DELETE /fests/:slug/members/:user_id ────────────────────────────────────
@router.delete("/{slug}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_fest_member(
    slug: str,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Remove a committee member. Owners can only be removed by admin."""
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")

    _require_fest_privileged(fest, current_user, db)

    member = (
        db.query(models.FestMember)
        .filter(models.FestMember.fest_id == fest.id, models.FestMember.user_id == user_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Member not found in this fest")

    if member.role == models.FestMemberRoleEnum.owner and current_user.role != models.RoleEnum.admin:
        raise HTTPException(
            status_code=403,
            detail="Cannot remove an owner. Transfer ownership first or ask an admin.",
        )
    if member.role == models.FestMemberRoleEnum.core and _actor_fest_role(fest, current_user, db) == "core":
        raise HTTPException(status_code=403, detail="Only the fest owner can remove core members")

    db.delete(member)
    db.commit()


# ─── PATCH /fests/:slug/status ───────────────────────────────────────────────
@router.patch("/{slug}/status", response_model=schemas.FestOut)
def set_fest_status(
    slug: str,
    status_update: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Promote/demote a fest between draft and live (owner / core / admin only)."""
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")

    _require_fest_privileged(fest, current_user, db)

    new_status = status_update.get("status")
    if new_status not in ("draft", "live"):
        raise HTTPException(status_code=400, detail="status must be 'draft' or 'live'")

    # Guard: a fest cannot go live without at least one owner in its committee.
    # This prevents orphaned fests that no organizer can manage after launch.
    if new_status == "live":
        owner_exists = (
            db.query(models.FestMember)
            .filter(
                models.FestMember.fest_id == fest.id,
                models.FestMember.role == models.FestMemberRoleEnum.owner,
            )
            .first()
        ) is not None
        if not owner_exists:
            raise HTTPException(
                status_code=400,
                detail="Cannot set fest to live: no owner exists. "
                       "Add at least one member with role='owner' first.",
            )

    fest.status = models.FestStatusEnum.live if new_status == "live" else models.FestStatusEnum.draft
    db.commit()
    db.refresh(fest)
    return fest
