"""
Contingents: the visiting colleges at a fest.

Every fest decides whether it takes visiting colleges at all, what it calls them, and the rules (size, assistants, registration
window, whether the committee approves each one). A visiting college is represented by a leader, optionally helped by
assistants, and brings a roster of delegates.

  GET    /api/fests/{slug}/contingents/info                         public: is the fest taking visiting colleges, and what does it call them
  GET    /api/fests/{slug}/contingents/settings                     the fest's terms and rules (anyone signed in who can see the fest)
  PUT    /api/fests/{slug}/contingents/settings                     change them (director or core team)
  POST   /api/fests/{slug}/contingents                              register a college; the caller becomes its leader
  GET    /api/fests/{slug}/contingents/mine                         the caller's contingent, as leader or assistant (null if none)
  GET    /api/fests/{slug}/contingents?status=                      every contingent (director or core team)
  GET    /api/fests/{slug}/contingents/{id}                         one contingent with its assistants and roster
  PATCH  /api/fests/{slug}/contingents/{id}                         change the college's name
  POST   /api/fests/{slug}/contingents/{id}/approve | /reject       the committee's decision (reject needs a reason)
  PATCH  /api/fests/{slug}/contingents/{id}/assign                  the committee sets its code and name
  POST   /api/fests/{slug}/contingents/{id}/withdraw                the leader pulls out (the committee can too); frees its code and name
  DELETE /api/fests/{slug}/contingents/{id}                         the committee deletes it
  POST   /api/fests/{slug}/contingents/{id}/assistants              add an assistant by email
  DELETE /api/fests/{slug}/contingents/{id}/assistants/{user_id}    remove one (an assistant can leave)
  POST   /api/fests/{slug}/contingents/{id}/members                 add a delegate
  PATCH  /api/fests/{slug}/contingents/{id}/members/{member_id}     change one
  DELETE /api/fests/{slug}/contingents/{id}/members/{member_id}     remove one
"""

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, notices, schemas
from app.auth.dependencies import get_current_user, get_optional_user
from app.database import get_db
from app.permissions import can_view_fest, is_fest_staff

router = APIRouter()

ACTIVE = ("pending", "approved")


# ─── helpers ──────────────────────────────────────────────────────────────────

def _fest(db: Session, slug: str) -> models.Fest:
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    return fest


def _settings(db: Session, fest: models.Fest) -> models.ContingentSettings:
    row = db.query(models.ContingentSettings).filter(models.ContingentSettings.fest_id == fest.id).first()
    if not row:
        row = models.ContingentSettings(fest_id=fest.id)
        db.add(row)
        db.flush()
        db.refresh(row)
    return row


def _registration_open(s: models.ContingentSettings) -> bool:
    today = date.today()
    return bool(s.enabled) and (s.opens_on is None or today >= s.opens_on) and (s.closes_on is None or today <= s.closes_on)


def _roster_open(s: models.ContingentSettings) -> bool:
    return not (s.lock_roster_after_close and s.closes_on and date.today() > s.closes_on)


def _settings_out(s: models.ContingentSettings) -> schemas.ContingentSettingsOut:
    return schemas.ContingentSettingsOut.model_validate(s).model_copy(update={"registration_open": _registration_open(s)})


def _contingent(db: Session, fest: models.Fest, contingent_id: int) -> models.Contingent:
    c = db.query(models.Contingent).filter(models.Contingent.id == contingent_id, models.Contingent.fest_id == fest.id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contingent not found")
    return c


def _role(c: models.Contingent, user) -> Optional[str]:
    if c.leader_user_id == user.id:
        return "leader"
    if any(a.user_id == user.id for a in c.assistants):
        return "assistant"
    return None


def _in_fest(db: Session, fest: models.Fest, user_id: int, except_id: Optional[int] = None) -> Optional[models.Contingent]:
    """The active contingent this person already leads or assists at this fest, if any."""
    q = db.query(models.Contingent).filter(models.Contingent.fest_id == fest.id, models.Contingent.status.in_(ACTIVE))
    if except_id is not None:
        q = q.filter(models.Contingent.id != except_id)
    for c in q.all():
        if c.leader_user_id == user_id or any(a.user_id == user_id for a in c.assistants):
            return c
    return None


def _college_taken(db: Session, fest: models.Fest, name: str, college_id: Optional[int], except_id: Optional[int] = None) -> bool:
    q = db.query(models.Contingent).filter(models.Contingent.fest_id == fest.id, models.Contingent.status.in_(ACTIVE))
    if except_id is not None:
        q = q.filter(models.Contingent.id != except_id)
    for c in q.all():
        if (college_id is not None and c.college_id == college_id) or " ".join(c.college_name.lower().split()) == " ".join(name.lower().split()):
            return True
    return False


def _staff_ids(db: Session, fest: models.Fest) -> List[int]:
    rows = db.query(models.FestMember).filter(
        models.FestMember.fest_id == fest.id, models.FestMember.role.in_([models.FestMemberRoleEnum.owner, models.FestMemberRoleEnum.core])
    ).all()
    return [m.user_id for m in rows]


def _require_view(db: Session, fest: models.Fest, c: models.Contingent, user) -> str:
    role = _role(c, user)
    if role:
        return role
    if is_fest_staff(db, fest.id, user):
        return "staff"
    raise HTTPException(status_code=403, detail="Only this contingent's leaders and the fest's committee can see it")


def _require_manage(db: Session, fest: models.Fest, c: models.Contingent, user, leader_only: bool = False) -> str:
    """Staff may always; the leader may; assistants may unless the action is the leader's alone."""
    role = _role(c, user)
    if role == "leader" or (role == "assistant" and not leader_only):
        return role
    if is_fest_staff(db, fest.id, user):
        return "staff"
    raise HTTPException(status_code=403, detail="Only the leader or the fest's committee can do that" if leader_only else "Only this contingent's leaders or the fest's committee can do that")


def _term(db: Session, fest: models.Fest) -> str:
    return _settings(db, fest).term.lower()


def _detail(db: Session, fest: models.Fest, c: models.Contingent, user) -> schemas.ContingentDetail:
    s = _settings(db, fest)
    role = _role(c, user) or ("staff" if is_fest_staff(db, fest.id, user) else None)
    size = len(c.members)
    ok = size >= s.min_members and (s.max_members is None or size <= s.max_members)
    base = schemas.ContingentOut.model_validate(c).model_dump()
    return schemas.ContingentDetail(
        **base, assistants=[schemas.ContingentAssistantOut.model_validate(a) for a in c.assistants],
        members=[schemas.ContingentMemberOut.model_validate(m) for m in c.members], my_role=role, roster_open=(role == "staff" or _roster_open(s)), roster_ok=ok,
    )


# ─── settings ─────────────────────────────────────────────────────────────────

@router.get("/{slug}/contingents/info", response_model=schemas.ContingentInfo)
def public_info(slug: str, db: Session = Depends(get_db), user: Optional[models.User] = Depends(get_optional_user)):
    """No sign-in needed: just enough for a live fest's page to invite visiting colleges. Draft fests do not exist to outsiders."""
    fest = _fest(db, slug)
    if not can_view_fest(db, fest, user):
        raise HTTPException(status_code=404, detail="Fest not found")
    row = db.query(models.ContingentSettings).filter(models.ContingentSettings.fest_id == fest.id).first()
    if not row:
        return schemas.ContingentInfo()
    return schemas.ContingentInfo(enabled=bool(row.enabled), registration_open=_registration_open(row), term=row.term, leader_term=row.leader_term, opens_on=row.opens_on, closes_on=row.closes_on)


@router.get("/{slug}/contingents/settings", response_model=schemas.ContingentSettingsOut)
def get_settings(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    if not can_view_fest(db, fest, user):
        raise HTTPException(status_code=404, detail="Fest not found")
    out = _settings_out(_settings(db, fest))
    db.commit()
    return out


@router.put("/{slug}/contingents/settings", response_model=schemas.ContingentSettingsOut)
def put_settings(slug: str, data: schemas.ContingentSettingsIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    if not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can change these settings")
    row = _settings(db, fest)
    for field, value in data.model_dump().items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return _settings_out(row)


# ─── registering and looking ─────────────────────────────────────────────────

@router.post("/{slug}/contingents", response_model=schemas.ContingentDetail, status_code=status.HTTP_201_CREATED)
def register(slug: str, data: schemas.ContingentCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    s = _settings(db, fest)
    if fest.status != models.FestStatusEnum.live:
        raise HTTPException(status_code=400, detail="This fest is not open yet")
    if not s.enabled:
        raise HTTPException(status_code=400, detail=f"This fest is not taking {s.term.lower()}s from other colleges")
    if not _registration_open(s):
        raise HTTPException(status_code=400, detail=f"Registration for {s.term.lower()}s is closed" if s.closes_on and date.today() > s.closes_on else f"Registration for {s.term.lower()}s has not opened yet")
    if _in_fest(db, fest, user.id):
        raise HTTPException(status_code=400, detail=f"You already lead or help a {s.term.lower()} at this fest")
    if data.college_id is not None and not db.query(models.College).filter(models.College.id == data.college_id).first():
        raise HTTPException(status_code=400, detail="College not found")
    if not s.allow_multiple_per_college and _college_taken(db, fest, data.college_name, data.college_id):
        raise HTTPException(status_code=400, detail=f"That college already has a {s.term.lower()} at this fest. Ask its {s.leader_term.lower()} to add you as an assistant.")
    c = models.Contingent(
        fest_id=fest.id, college_name=data.college_name, college_id=data.college_id, leader_user_id=user.id,
        status="pending" if s.requires_approval else "approved", decided_at=None if s.requires_approval else datetime.utcnow(),
    )
    db.add(c)
    db.flush()
    for uid in _staff_ids(db, fest):
        if uid != user.id:
            notices.notify(db, uid, "contingent", f"New {s.term.lower()}: {c.college_name}"[:120], f"{user.name} registered {c.college_name} for {fest.name}."[:500])
    db.commit()
    db.refresh(c)
    return _detail(db, fest, c, user)


@router.get("/{slug}/contingents/mine", response_model=Optional[schemas.ContingentDetail])
def my_contingent(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    rows = db.query(models.Contingent).filter(models.Contingent.fest_id == fest.id, models.Contingent.status != "withdrawn").order_by(models.Contingent.id.desc()).all()
    mine = [c for c in rows if _role(c, user)]
    if not mine:
        return None
    # An active contingent wins over an old rejected one
    mine.sort(key=lambda c: (c.status not in ACTIVE, -c.id))
    return _detail(db, fest, mine[0], user)


@router.get("/{slug}/contingents", response_model=List[schemas.ContingentOut])
def list_contingents(slug: str, status_filter: Optional[str] = Query(default=None, alias="status", pattern="^(pending|approved|rejected|withdrawn)$"), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    if not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can see every contingent")
    q = db.query(models.Contingent).filter(models.Contingent.fest_id == fest.id)
    if status_filter:
        q = q.filter(models.Contingent.status == status_filter)
    return q.order_by(func.lower(models.Contingent.college_name), models.Contingent.id).all()


@router.get("/{slug}/contingents/{contingent_id}", response_model=schemas.ContingentDetail)
def get_contingent(slug: str, contingent_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    c = _contingent(db, fest, contingent_id)
    _require_view(db, fest, c, user)
    return _detail(db, fest, c, user)


@router.patch("/{slug}/contingents/{contingent_id}", response_model=schemas.ContingentDetail)
def update_contingent(slug: str, contingent_id: int, data: schemas.ContingentUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    c = _contingent(db, fest, contingent_id)
    _require_manage(db, fest, c, user, leader_only=True)
    if c.status not in ACTIVE:
        raise HTTPException(status_code=400, detail="This contingent is no longer active")
    updates = data.model_dump(exclude_unset=True)
    s = _settings(db, fest)
    name = updates.get("college_name", c.college_name)
    college_id = updates.get("college_id", c.college_id)
    if college_id is not None and not db.query(models.College).filter(models.College.id == college_id).first():
        raise HTTPException(status_code=400, detail="College not found")
    if ("college_name" in updates or "college_id" in updates) and not s.allow_multiple_per_college and _college_taken(db, fest, name, college_id, except_id=c.id):
        raise HTTPException(status_code=400, detail=f"That college already has a {s.term.lower()} at this fest")
    if "college_name" in updates and updates["college_name"]:
        c.college_name = updates["college_name"]
    if "college_id" in updates:
        c.college_id = updates["college_id"]
    db.commit()
    db.refresh(c)
    return _detail(db, fest, c, user)


# ─── the committee decides ───────────────────────────────────────────────────

def _decide(db: Session, slug: str, contingent_id: int, user, outcome: str, note: Optional[str]) -> schemas.ContingentDetail:
    fest = _fest(db, slug)
    if not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can decide")
    c = _contingent(db, fest, contingent_id)
    if c.status == "withdrawn":
        raise HTTPException(status_code=400, detail="This contingent was withdrawn")
    if outcome == "rejected" and len(note or "") < 5:
        raise HTTPException(status_code=400, detail="Say why, so they know what to fix")
    c.status, c.note, c.decided_at = outcome, note or None, datetime.utcnow()
    if outcome == "rejected":
        c.code, c.name = None, None  # a rejected contingent holds nothing
    term = _term(db, fest)
    verdict = "approved" if outcome == "approved" else "not approved"
    body = f"Your {term} for {fest.name} was {verdict}." + (f" {note}" if note else "")
    notices.notify(db, c.leader_user_id, "contingent", f"{c.college_name}: {verdict}"[:120], body[:500])
    db.commit()
    db.refresh(c)
    return _detail(db, fest, c, user)


@router.post("/{slug}/contingents/{contingent_id}/approve", response_model=schemas.ContingentDetail)
def approve(slug: str, contingent_id: int, data: Optional[schemas.ContingentDecision] = None, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return _decide(db, slug, contingent_id, user, "approved", data.note if data else None)


@router.post("/{slug}/contingents/{contingent_id}/reject", response_model=schemas.ContingentDetail)
def reject(slug: str, contingent_id: int, data: schemas.ContingentDecision, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return _decide(db, slug, contingent_id, user, "rejected", data.note)


@router.patch("/{slug}/contingents/{contingent_id}/assign", response_model=schemas.ContingentDetail)
def assign(slug: str, contingent_id: int, data: schemas.ContingentAssign, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    if not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can set codes and names")
    c = _contingent(db, fest, contingent_id)
    if c.status not in ACTIVE:
        raise HTTPException(status_code=400, detail="Only a pending or approved contingent can hold a code or name")
    updates = data.model_dump(exclude_unset=True)
    told = []
    for field, label in (("code", "code"), ("name", "name")):
        if field not in updates:
            continue
        value = (updates[field] or "").strip() or None
        if value:
            clash = db.query(models.Contingent).filter(
                models.Contingent.fest_id == fest.id, models.Contingent.id != c.id, func.lower(getattr(models.Contingent, field)) == value.lower()
            ).first()
            if clash:
                raise HTTPException(status_code=400, detail=f"Another contingent already has that {label}")
        if value != getattr(c, field):
            setattr(c, field, value)
            if value:
                told.append(f"{label} {value}")
    if told:
        notices.notify(db, c.leader_user_id, "contingent", f"{c.college_name}: {' and '.join(told)}"[:120], f"The committee gave your {_term(db, fest)} for {fest.name}: {', '.join(told)}."[:500])
    db.commit()
    db.refresh(c)
    return _detail(db, fest, c, user)


@router.post("/{slug}/contingents/{contingent_id}/withdraw", response_model=schemas.ContingentDetail)
def withdraw(slug: str, contingent_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    c = _contingent(db, fest, contingent_id)
    role = _require_manage(db, fest, c, user, leader_only=True)
    if c.status == "withdrawn":
        raise HTTPException(status_code=400, detail="Already withdrawn")
    c.status, c.code, c.name, c.decided_at = "withdrawn", None, None, datetime.utcnow()  # the code and name go back to the pool
    if role == "leader":
        for uid in _staff_ids(db, fest):
            notices.notify(db, uid, "contingent", f"{c.college_name} withdrew"[:120], f"{user.name} withdrew {c.college_name} from {fest.name}."[:500])
    db.commit()
    db.refresh(c)
    return _detail(db, fest, c, user)


@router.delete("/{slug}/contingents/{contingent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contingent(slug: str, contingent_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    if not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can delete a contingent")
    db.delete(_contingent(db, fest, contingent_id))
    db.commit()


# ─── assistants ───────────────────────────────────────────────────────────────

@router.post("/{slug}/contingents/{contingent_id}/assistants", response_model=schemas.ContingentDetail, status_code=status.HTTP_201_CREATED)
def add_assistant(slug: str, contingent_id: int, data: schemas.ContingentAssistantIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    c = _contingent(db, fest, contingent_id)
    _require_manage(db, fest, c, user, leader_only=True)
    s = _settings(db, fest)
    if c.status not in ACTIVE:
        raise HTTPException(status_code=400, detail="This contingent is no longer active")
    if len(c.assistants) >= s.max_assistants:
        raise HTTPException(status_code=400, detail=f"A {s.term.lower()} can have at most {s.max_assistants} {s.assistant_term.lower()}s")
    person = db.query(models.User).filter(func.lower(models.User.email) == data.email.lower()).first()
    if not person:
        raise HTTPException(status_code=404, detail="No HiveOut account with that email. Ask them to sign up first, then add them.")
    if person.id == c.leader_user_id:
        raise HTTPException(status_code=400, detail=f"They are already the {s.leader_term.lower()}")
    if _in_fest(db, fest, person.id):
        raise HTTPException(status_code=400, detail=f"They already lead or help a {s.term.lower()} at this fest")
    c.assistants.append(models.ContingentAssistant(user_id=person.id))
    notices.notify(db, person.id, "contingent", f"You are {s.assistant_term.lower()} for {c.college_name}"[:120], f"{user.name} added you to help run the {c.college_name} {s.term.lower()} at {fest.name}."[:500])
    db.commit()
    db.refresh(c)
    return _detail(db, fest, c, user)


@router.delete("/{slug}/contingents/{contingent_id}/assistants/{user_id}", response_model=schemas.ContingentDetail)
def remove_assistant(slug: str, contingent_id: int, user_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    c = _contingent(db, fest, contingent_id)
    if not (user.id == user_id and _role(c, user) == "assistant"):  # an assistant may always leave
        _require_manage(db, fest, c, user, leader_only=True)
    assistant = next((a for a in c.assistants if a.user_id == user_id), None)
    if not assistant:
        raise HTTPException(status_code=404, detail="That person is not an assistant here")
    c.assistants.remove(assistant)
    db.commit()
    db.refresh(c)
    return _detail(db, fest, c, user)


# ─── the roster ───────────────────────────────────────────────────────────────

def _roster_access(db: Session, fest: models.Fest, c: models.Contingent, user) -> str:
    role = _require_manage(db, fest, c, user)
    if role != "staff":
        if c.status not in ACTIVE:
            raise HTTPException(status_code=400, detail="This contingent is no longer active")
        if not _roster_open(_settings(db, fest)):
            raise HTTPException(status_code=400, detail="The roster is locked now that registration has closed. Ask the committee to make a change.")
    return role


def _email_in_use(c: models.Contingent, email: Optional[str], except_id: Optional[int] = None) -> bool:
    return bool(email) and any(m.id != except_id and (m.email or "").lower() == email.lower() for m in c.members)


@router.post("/{slug}/contingents/{contingent_id}/members", response_model=schemas.ContingentDetail, status_code=status.HTTP_201_CREATED)
def add_member(slug: str, contingent_id: int, data: schemas.ContingentMemberIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    c = _contingent(db, fest, contingent_id)
    role = _roster_access(db, fest, c, user)
    s = _settings(db, fest)
    if role != "staff" and s.max_members is not None and len(c.members) >= s.max_members:
        raise HTTPException(status_code=400, detail=f"A {s.term.lower()} can have at most {s.max_members} people")
    if _email_in_use(c, data.email):
        raise HTTPException(status_code=400, detail="Someone with that email is already on the roster")
    c.members.append(models.ContingentMember(name=data.name, email=data.email, phone=data.phone, year=data.year, notes=data.notes or None))
    db.commit()
    db.refresh(c)
    return _detail(db, fest, c, user)


@router.patch("/{slug}/contingents/{contingent_id}/members/{member_id}", response_model=schemas.ContingentDetail)
def update_member(slug: str, contingent_id: int, member_id: int, data: schemas.ContingentMemberUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    c = _contingent(db, fest, contingent_id)
    _roster_access(db, fest, c, user)
    member = next((m for m in c.members if m.id == member_id), None)
    if not member:
        raise HTTPException(status_code=404, detail="That person is not on this roster")
    updates = data.model_dump(exclude_unset=True)
    if "name" in updates:
        if not updates["name"]:
            raise HTTPException(status_code=400, detail="A delegate needs a name")
        member.name = updates["name"]
    if "email" in updates:
        if _email_in_use(c, updates["email"], except_id=member.id):
            raise HTTPException(status_code=400, detail="Someone with that email is already on the roster")
        member.email = updates["email"] or None
    for field in ("phone", "year", "notes"):
        if field in updates:
            setattr(member, field, updates[field] or None)
    db.commit()
    db.refresh(c)
    return _detail(db, fest, c, user)


@router.delete("/{slug}/contingents/{contingent_id}/members/{member_id}", response_model=schemas.ContingentDetail)
def remove_member(slug: str, contingent_id: int, member_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    c = _contingent(db, fest, contingent_id)
    _roster_access(db, fest, c, user)
    member = next((m for m in c.members if m.id == member_id), None)
    if not member:
        raise HTTPException(status_code=404, detail="That person is not on this roster")
    c.members.remove(member)
    db.commit()
    db.refresh(c)
    return _detail(db, fest, c, user)
