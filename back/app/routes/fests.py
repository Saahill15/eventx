from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List, Union
from app.database import get_db
from app import models, schemas
from app.auth.dependencies import get_current_user, get_optional_user
from app.permissions import can_host_fests, can_view_fest, fest_hosting_switched_off
from app.fest_review import fest_missing
from app import notices

router = APIRouter()


# ─── Permission helpers ───────────────────────────────────────────────────────

def _is_fest_privileged(fest: models.Fest, user: models.User, db: Session) -> bool:
    """Return True if user is admin OR a FestMember with role owner/core, and still allowed to host fests."""
    if user.role == models.RoleEnum.admin:
        return True
    if fest_hosting_switched_off(user):
        return False
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


# ─── GET /fests/mine ─────────────────────────────────────────────────────────
@router.get("/mine", response_model=List[schemas.FestMineOut])
def list_my_fests(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Fests the current user belongs to (all fests for admins), with their role in each."""
    if current_user.role == models.RoleEnum.admin:
        rows = [(f, "admin") for f in db.query(models.Fest).order_by(models.Fest.created_at.desc()).all()]
    else:
        rows = [
            (m.fest, m.role.value)
            for m in db.query(models.FestMember)
            .filter(models.FestMember.user_id == current_user.id)
            .order_by(models.FestMember.created_at.desc())
            .all()
        ]
    return [
        {**schemas.FestOut.model_validate(fest).model_dump(), "my_role": role, "review_status": fest.review_status, "review_note": fest.review_note}
        for fest, role in rows
    ]


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


# ─── GET /fests/:slug/manage/events ──────────────────────────────────────────
@router.get("/{slug}/manage/events", response_model=List[schemas.FestEventManageOut])
def manage_fest_events(
    slug: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Every event of the fest, whatever its status, with registration counts (owner / core / admin)."""
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    _require_fest_privileged(fest, current_user, db)

    events = db.query(models.Event).filter(models.Event.fest_id == fest.id).order_by(models.Event.date).all()
    counts = {}
    for event_id, approval in (
        db.query(models.EventRegistration.event_id, models.EventRegistration.approval_status)
        .filter(models.EventRegistration.event_id.in_([e.id for e in events] or [0]))
        .all()
    ):
        total, pending = counts.get(event_id, (0, 0))
        if approval == models.RegApprovalStatusEnum.pending:
            counts[event_id] = (total + 1, pending + 1)
        elif approval == models.RegApprovalStatusEnum.approved:
            counts[event_id] = (total + 1, pending)
    out = []
    for e in events:
        total, pending = counts.get(e.id, (0, 0))
        out.append({**schemas.EventOut.model_validate(e).model_dump(), "registration_count": total, "pending_count": pending})
    return out


# ─── GET /fests/:slug/manage/stats ───────────────────────────────────────────
@router.get("/{slug}/manage/stats", response_model=schemas.FestStats)
def fest_stats(
    slug: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Numbers for the committee: passes issued and used, and per-event registrations and attendance."""
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    _require_fest_privileged(fest, current_user, db)

    passes = db.query(models.FestPass).filter(models.FestPass.fest_id == fest.id).all()
    events = db.query(models.Event).filter(models.Event.fest_id == fest.id).order_by(models.Event.date).all()
    rows = (
        db.query(models.EventRegistration.event_id, models.EventRegistration.approval_status, models.EventRegistration.attended)
        .filter(models.EventRegistration.event_id.in_([e.id for e in events] or [0]))
        .all()
    )
    out = []
    for e in events:
        mine = [r for r in rows if r[0] == e.id]
        out.append(schemas.EventStat(
            id=e.id, title=e.title, date=e.date, cancelled=e.cancelled,
            requires_registration=bool(e.requires_registration), registration_limit=e.registration_limit,
            registered=sum(1 for r in mine if r[1] == models.RegApprovalStatusEnum.approved),
            pending=sum(1 for r in mine if r[1] == models.RegApprovalStatusEnum.pending),
            attended=sum(1 for r in mine if r[2]),
        ))
    return schemas.FestStats(
        passes_issued=len(passes),
        passes_checked_in=sum(1 for p in passes if p.checked_in),
        events=out,
    )


# ─── GET /fests/:slug/manage ─────────────────────────────────────────────────
@router.get("/{slug}/manage", response_model=schemas.FestManageOut)
def manage_fest(
    slug: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """The fest with its private contact details and review state (owner / core / admin)."""
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    _require_fest_privileged(fest, current_user, db)
    return fest


# ─── GET /fests/:slug/manage/checklist ───────────────────────────────────────
@router.get("/{slug}/manage/checklist", response_model=schemas.ChecklistOut)
def fest_checklist(
    slug: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """What is still missing before the fest can be sent for review (empty = ready)."""
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    _require_fest_privileged(fest, current_user, db)
    events = db.query(models.Event).filter(models.Event.fest_id == fest.id).all()
    return schemas.ChecklistOut(missing=fest_missing(fest, events))


# ─── PATCH /fests/:slug ──────────────────────────────────────────────────────
@router.patch("/{slug}", response_model=schemas.FestManageOut)
def update_fest(
    slug: str,
    payload: schemas.FestUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Fill in or change a fest's details (owner / core / admin).

    While the fest waits for review it cannot be edited (withdraw it first). Once approved, dates and descriptions
    change freely, but changing the name or college sends the fest back to review and takes it offline.
    """
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    _require_fest_privileged(fest, current_user, db)

    if fest.review_status == "in_review" and current_user.role != models.RoleEnum.admin:
        raise HTTPException(status_code=400, detail="Your fest is waiting for review. Withdraw it first if you need to make changes.")

    updates = payload.model_dump(exclude_unset=True)
    if updates.get("name") is None:
        updates.pop("name", None)

    if "college_id" in updates:
        new_college_id = updates["college_id"]
        if new_college_id is None:
            updates.pop("college_id")
        elif new_college_id != fest.college_id:
            college = db.query(models.College).filter(models.College.id == new_college_id).first()
            if not college:
                raise HTTPException(status_code=400, detail="College not found")
            if current_user.role != models.RoleEnum.admin:
                if not db.query(models.OrganizerCollege).filter(models.OrganizerCollege.user_id == current_user.id, models.OrganizerCollege.college_id == college.id).first():
                    raise HTTPException(status_code=403, detail="You can only list fests for your own college.")
                if college.partner_status != "partner":
                    raise HTTPException(status_code=400, detail="HiveOut has not partnered with this college yet.")

    new_start = updates.get("start_date", fest.start_date)
    new_end = updates.get("end_date", fest.end_date)
    if new_start and new_end and new_end < new_start:
        raise HTTPException(status_code=400, detail="The fest cannot end before it starts")

    sensitive_changed = [
        f for f in ("name", "college_id") if f in updates and updates[f] != getattr(fest, f)
    ]
    for field, value in updates.items():
        if field == "extra_sections" and value is not None:
            value = [section if isinstance(section, dict) else section.model_dump() for section in value]
        setattr(fest, field, value)

    if sensitive_changed and fest.review_status == "approved" and current_user.role != models.RoleEnum.admin:
        fest.review_status = "in_review"
        fest.review_note = "Sent back to review because the fest's " + " and ".join(l.replace("_id", "") for l in sensitive_changed) + " changed."
        fest.submitted_at = datetime.utcnow()
        fest.status = models.FestStatusEnum.draft

    db.commit()
    db.refresh(fest)
    return fest


# ─── POST /fests/:slug/submit ────────────────────────────────────────────────
@router.post("/{slug}/submit", response_model=schemas.SubmitOut)
def submit_fest(
    slug: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Send the fest, with its events, to HiveOut for review. Everything required must be filled in first."""
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    _require_fest_privileged(fest, current_user, db)
    if fest.review_status == "in_review":
        raise HTTPException(status_code=400, detail="This fest is already waiting for review.")
    if fest.review_status == "approved":
        raise HTTPException(status_code=400, detail="This fest is already approved.")

    events = db.query(models.Event).filter(models.Event.fest_id == fest.id).all()
    missing = fest_missing(fest, events)
    if missing:
        raise HTTPException(status_code=400, detail={"message": "Finish these before submitting", "missing": missing})

    fest.review_status = "in_review"
    fest.review_note = None
    fest.submitted_at = datetime.utcnow()
    db.commit()
    db.refresh(fest)
    return schemas.SubmitOut(fest=fest, missing=[])


# ─── POST /fests/:slug/withdraw ──────────────────────────────────────────────
@router.post("/{slug}/withdraw", response_model=schemas.FestManageOut)
def withdraw_fest(
    slug: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Take a fest back from review so it can be edited."""
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    _require_fest_privileged(fest, current_user, db)
    if fest.review_status != "in_review":
        raise HTTPException(status_code=400, detail="This fest is not waiting for review.")
    fest.review_status = "draft"
    db.commit()
    db.refresh(fest)
    return fest


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
@router.post("/", response_model=schemas.FestManageOut, status_code=status.HTTP_201_CREATED)
def create_fest(
    payload: schemas.FestCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Start a fest as a draft. Organisers can only start fests for the colleges an admin assigned to them."""
    if current_user.role not in (models.RoleEnum.admin, models.RoleEnum.organizer) or not can_host_fests(current_user):
        raise HTTPException(status_code=403, detail="Committee tools are switched on by the HiveOut team. Get in touch to have your account set up.")

    college = db.query(models.College).filter(models.College.id == payload.college_id).first()
    if not college:
        raise HTTPException(status_code=400, detail="College not found")
    if current_user.role == models.RoleEnum.organizer:
        assigned = db.query(models.OrganizerCollege).filter(
            models.OrganizerCollege.user_id == current_user.id, models.OrganizerCollege.college_id == college.id
        ).first()
        if not assigned:
            raise HTTPException(status_code=403, detail="You can only list fests for your own college. Ask HiveOut to add this college to your account.")
    if college.partner_status != "partner" and current_user.role != models.RoleEnum.admin:
        raise HTTPException(status_code=400, detail="HiveOut has not partnered with this college yet.")

    if db.query(models.Fest).filter(models.Fest.slug == payload.slug).first():
        raise HTTPException(status_code=400, detail="Slug already in use")

    fest = models.Fest(
        slug=payload.slug, name=payload.name, tagline=payload.tagline, college_id=college.id,
        status=models.FestStatusEnum.draft, review_status="draft",
    )
    db.add(fest)
    db.flush()  # populate fest.id before creating the membership row

    # The creator is automatically the owner
    db.add(models.FestMember(fest_id=fest.id, user_id=current_user.id, role=models.FestMemberRoleEnum.owner))
    db.commit()
    db.refresh(fest)
    return fest


# ─── POST /fests/:slug/members ───────────────────────────────────────────────
@router.post("/{slug}/members", response_model=Union[schemas.FestMemberOut, schemas.FestInviteOut], status_code=status.HTTP_201_CREATED)
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

    if payload.user_id is not None:
        target = db.query(models.User).filter(models.User.id == payload.user_id).first()
    else:
        target = db.query(models.User).filter(func.lower(models.User.email) == payload.email.lower()).first()
    if not target:
        raise HTTPException(
            status_code=404,
            detail="No EventX account with that email. Ask them to sign up first, then add them.",
        )
    if target.role == models.RoleEnum.admin:
        raise HTTPException(status_code=400, detail="You can't add this user to a fest team.")
    target_id = target.id

    # Upsert: if already a member, update their role
    existing = (
        db.query(models.FestMember)
        .filter(models.FestMember.fest_id == fest.id, models.FestMember.user_id == target_id)
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

    # Nobody joins a committee straight away: they get an invitation and join once they accept it.
    # Verification is checked when they accept, so they can be invited first and verify afterwards.
    pending = (
        db.query(models.FestInvite)
        .filter(models.FestInvite.fest_id == fest.id, models.FestInvite.user_id == target_id, models.FestInvite.status == "pending")
        .first()
    )
    if pending:
        pending.role = role.value
        pending.invited_by_id = current_user.id
        db.commit()
        db.refresh(pending)
        return notices.invite_out(pending)

    invite = models.FestInvite(fest_id=fest.id, user_id=target_id, invited_by_id=current_user.id, role=role.value, status="pending", created_at=datetime.utcnow())
    db.add(invite)
    db.flush()
    notices.notify(
        db, target_id, "fest_invite",
        title=f"Invitation to join {fest.name}",
        body=f"{current_user.name} has invited you to join the team as {notices.ROLE_NAMES.get(role.value, role.value)}. Accept or decline below. Joining needs a verified student status.",
        invite_id=invite.id,
    )
    db.commit()
    db.refresh(invite)
    if target.email:
        notices.send_invite_email(target.email, target.name, fest.name, role.value, current_user.name)
    return notices.invite_out(invite)


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

    if new_status == "live" and fest.review_status != "approved":
        raise HTTPException(status_code=400, detail="An admin must approve your fest before it can go live.")

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
