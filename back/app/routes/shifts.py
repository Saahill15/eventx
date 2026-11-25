"""
The duty roster: who is on the gate, the registration desk or the stage, and when.

  GET    /api/fests/{slug}/shifts?when=upcoming|past|all&mine=true   the duties (any committee member), soonest first
  GET    /api/fests/{slug}/shifts/coverage                           what is still unfilled, and who has no duty (director or core)
  POST   /api/fests/{slug}/shifts                                    add a duty, optionally on several days and with people on it (director or core)
  PATCH  /api/fests/{slug}/shifts/{id}                               change it; the people on it are told if the time or place moved
  DELETE /api/fests/{slug}/shifts/{id}                               cancel it; the people on it are told
  POST   /api/fests/{slug}/shifts/{id}/assign                        put a member on it (director or core)
  DELETE /api/fests/{slug}/shifts/{id}/people/{member_id}            take a member off it (director or core)
  POST   /api/fests/{slug}/shifts/{id}/claim                         put yourself down, when the duty is open for sign-up
  DELETE /api/fests/{slug}/shifts/{id}/claim                         take yourself off, until it starts
  POST   /api/fests/{slug}/shifts/{id}/arrive                        say "I am here" (from 30 minutes before it starts)
  PUT    /api/fests/{slug}/shifts/{id}/attendance                    mark who arrived or did not come (director or core)
"""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import models, notices, schemas, shifts as roster
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.permissions import is_fest_member, is_fest_staff

router = APIRouter()

MAX_SHIFTS = 1000
SOON_DAYS = 3


def _fest(db: Session, slug: str) -> models.Fest:
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    return fest


def _need_member(db: Session, fest: models.Fest, user: models.User) -> None:
    if not is_fest_member(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's committee can see the duty roster")


def _need_staff(db: Session, fest: models.Fest, user: models.User) -> None:
    if not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can change the duty roster")


def _me(db: Session, fest: models.Fest, user: models.User) -> Optional[models.FestMember]:
    return db.query(models.FestMember).filter(models.FestMember.fest_id == fest.id, models.FestMember.user_id == user.id).first()


def _shift(db: Session, fest: models.Fest, shift_id: int) -> models.Shift:
    s = db.query(models.Shift).filter(models.Shift.id == shift_id, models.Shift.fest_id == fest.id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Duty not found")
    return s


def _member(db: Session, fest: models.Fest, member_id: int) -> models.FestMember:
    m = db.query(models.FestMember).filter(models.FestMember.id == member_id, models.FestMember.fest_id == fest.id).first()
    if not m:
        raise HTTPException(status_code=400, detail="That person is not on this fest's committee")
    return m


def _check_links(db: Session, fest: models.Fest, event_id: Optional[int], team_id: Optional[int]) -> None:
    if event_id is not None and not db.query(models.Event).filter(models.Event.id == event_id, models.Event.fest_id == fest.id).first():
        raise HTTPException(status_code=400, detail="That event is not part of this fest")
    if team_id is not None and not db.query(models.CommitteeTeam).filter(models.CommitteeTeam.id == team_id, models.CommitteeTeam.fest_id == fest.id).first():
        raise HTTPException(status_code=400, detail="That team is not part of this fest")


def _out(s: models.Shift, me: Optional[models.FestMember], now: datetime) -> schemas.ShiftOut:
    state = roster.state_of(s, now)
    mine = me is not None and any(a.member_id == me.id for a in s.assignments)
    people = sorted(s.assignments, key=lambda a: (a.user_name or "").lower())
    return schemas.ShiftOut(
        id=s.id, title=s.title, event_id=s.event_id, event_title=s.event_title, committee_team_id=s.committee_team_id, team_name=s.team_name,
        location=s.location, starts_at=s.starts_at, ends_at=s.ends_at, needed=s.needed, filled=s.filled, open_spots=max(s.needed - s.filled, 0),
        open_signup=s.open_signup, notes=s.notes, state=state,
        people=[schemas.ShiftPerson(member_id=a.member_id, user_id=a.user_id, user_name=a.user_name, title=a.title, arrived_at=a.arrived_at, no_show=a.no_show) for a in people],
        mine=mine,
        can_claim=bool(me) and not mine and s.open_signup and state != "over" and s.filled < s.needed,
        can_leave=mine and state == "upcoming",
        can_arrive=mine and state != "over" and now >= s.starts_at - roster.ARRIVE_EARLY and not any(a.member_id == me.id and a.arrived_at for a in s.assignments),
    )


def _tell(db: Session, fest: models.Fest, s: models.Shift, user_ids: List[int], headline: str, skip: Optional[int] = None) -> None:
    where = f" at {s.location}" if s.location else ""
    for uid in dict.fromkeys(user_ids):
        if uid != skip:
            notices.notify(db, uid, "shift", f"{headline}: {s.title}"[:120], f"{fest.name}: {roster.when_text(s)}{where}."[:500])


def _put_on(db: Session, s: models.Shift, member: models.FestMember) -> None:
    """Add a person to a duty, refusing a double booking. Does not commit."""
    if any(a.member_id == member.id for a in s.assignments):
        raise HTTPException(status_code=400, detail=f"{member.user_name} is already on this duty")
    other = roster.clash(db, member.id, s.starts_at, s.ends_at, ignore_shift_id=s.id)
    if other:
        raise HTTPException(status_code=400, detail=f"{member.user_name} is already on \"{other.title}\" at that time ({roster.when_text(other)})")
    s.assignments.append(models.ShiftAssignment(member_id=member.id))


@router.get("/{slug}/shifts", response_model=List[schemas.ShiftOut])
def list_shifts(slug: str, when: str = Query(default="upcoming", pattern="^(upcoming|past|all)$"), mine: bool = False, event_id: Optional[int] = None,
                db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _need_member(db, fest, user)
    now = datetime.now()
    me = _me(db, fest, user)
    q = db.query(models.Shift).filter(models.Shift.fest_id == fest.id)
    if when == "upcoming":
        q = q.filter(models.Shift.ends_at > now).order_by(models.Shift.starts_at, models.Shift.id)
    elif when == "past":
        q = q.filter(models.Shift.ends_at <= now).order_by(models.Shift.starts_at.desc(), models.Shift.id)
    else:
        q = q.order_by(models.Shift.starts_at, models.Shift.id)
    if event_id is not None:
        q = q.filter(models.Shift.event_id == event_id)
    rows = [_out(s, me, now) for s in q.all()]
    return [r for r in rows if r.mine] if mine else rows


@router.get("/{slug}/shifts/coverage", response_model=schemas.ShiftCoverage)
def coverage(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _need_staff(db, fest, user)
    now = datetime.now()
    upcoming = roster.upcoming_shifts(db, fest.id, now)
    short = [s for s in upcoming if s.filled < s.needed]
    busy = {a.member_id for s in upcoming for a in s.assignments}
    idle = [m.user_name for m in db.query(models.FestMember).filter(models.FestMember.fest_id == fest.id).all() if m.id not in busy and m.user_name]
    soon = [s for s in short if s.starts_at <= now + timedelta(days=SOON_DAYS)]
    return schemas.ShiftCoverage(
        upcoming=len(upcoming), understaffed=len(short), open_spots=sum(s.needed - s.filled for s in short),
        soon=[schemas.ShiftGap(shift_id=s.id, title=s.title, starts_at=s.starts_at, needed=s.needed, filled=s.filled) for s in soon[:10]],
        unassigned_people=sorted(idle, key=str.lower),
    )


@router.post("/{slug}/shifts", response_model=List[schemas.ShiftOut], status_code=status.HTTP_201_CREATED)
def add_shift(slug: str, data: schemas.ShiftIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _need_staff(db, fest, user)
    _check_links(db, fest, data.event_id, data.committee_team_id)
    members = [_member(db, fest, i) for i in dict.fromkeys(data.member_ids)]
    if len(members) > data.needed:
        raise HTTPException(status_code=400, detail=f"{len(members)} people were chosen but only {data.needed} are needed. Raise the number needed")
    length = data.ends_at - data.starts_at
    starts = [data.starts_at.replace(tzinfo=None)]
    for d in dict.fromkeys(data.repeat_on):
        when = datetime.combine(d, data.starts_at.time())
        if when not in starts:
            starts.append(when)
    if db.query(models.Shift).filter(models.Shift.fest_id == fest.id).count() + len(starts) > MAX_SHIFTS:
        raise HTTPException(status_code=400, detail=f"A fest can have at most {MAX_SHIFTS} duties")
    made: List[models.Shift] = []
    for start in starts:
        s = models.Shift(fest_id=fest.id, title=data.title, event_id=data.event_id, committee_team_id=data.committee_team_id, location=data.location or None,
                         starts_at=start, ends_at=start + length, needed=data.needed, open_signup=data.open_signup, notes=data.notes or None, created_by_id=user.id)
        db.add(s)
        db.flush()
        for m in members:
            _put_on(db, s, m)
        made.append(s)
    for s in made:
        _tell(db, fest, s, [m.user_id for m in members], "You are on duty", skip=user.id)
    db.commit()
    now = datetime.now()
    me = _me(db, fest, user)
    return [_out(s, me, now) for s in made]


@router.patch("/{slug}/shifts/{shift_id}", response_model=schemas.ShiftOut)
def update_shift(slug: str, shift_id: int, data: schemas.ShiftUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _need_staff(db, fest, user)
    s = _shift(db, fest, shift_id)
    u = data.model_dump(exclude_unset=True)
    if "event_id" in u or "committee_team_id" in u:
        _check_links(db, fest, u.get("event_id"), u.get("committee_team_id"))
    for key in ("title", "needed", "open_signup"):
        if key in u and u[key] is None:
            raise HTTPException(status_code=400, detail=f"{key.replace('_', ' ').capitalize()} cannot be empty")
    starts, ends = u.get("starts_at") or s.starts_at, u.get("ends_at") or s.ends_at
    starts, ends = starts.replace(tzinfo=None), ends.replace(tzinfo=None)
    if ends <= starts or ends - starts > timedelta(hours=18):
        raise HTTPException(status_code=400, detail="A duty must end after it starts, and last at most 18 hours")
    if "needed" in u and u["needed"] < s.filled:
        raise HTTPException(status_code=400, detail=f"{s.filled} people are on this duty. Take some off before lowering the number needed")
    moved = (starts, ends, u.get("location", s.location) or None) != (s.starts_at, s.ends_at, s.location)
    if (starts, ends) != (s.starts_at, s.ends_at):
        for a in s.assignments:
            other = roster.clash(db, a.member_id, starts, ends, ignore_shift_id=s.id)
            if other:
                raise HTTPException(status_code=400, detail=f"{a.user_name} would clash with \"{other.title}\" ({roster.when_text(other)}). Take them off first")
    for key in ("title", "event_id", "committee_team_id", "needed", "open_signup"):
        if key in u:
            setattr(s, key, u[key])
    for key in ("location", "notes"):
        if key in u:
            setattr(s, key, u[key] or None)
    s.starts_at, s.ends_at = starts, ends
    if moved:
        _tell(db, fest, s, [a.user_id for a in s.assignments], "Your duty changed", skip=user.id)
    db.commit()
    db.refresh(s)
    return _out(s, _me(db, fest, user), datetime.now())


@router.delete("/{slug}/shifts/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shift(slug: str, shift_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _need_staff(db, fest, user)
    s = _shift(db, fest, shift_id)
    _tell(db, fest, s, [a.user_id for a in s.assignments], "Duty cancelled", skip=user.id)
    db.delete(s)
    db.commit()


@router.post("/{slug}/shifts/{shift_id}/assign", response_model=schemas.ShiftOut)
def assign(slug: str, shift_id: int, data: schemas.ShiftAssignIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _need_staff(db, fest, user)
    s = _shift(db, fest, shift_id)
    if s.ends_at <= datetime.now():
        raise HTTPException(status_code=400, detail="That duty is already over")
    member = _member(db, fest, data.member_id)
    if s.filled >= s.needed:
        raise HTTPException(status_code=400, detail="This duty is full. Raise the number needed first")
    _put_on(db, s, member)
    _tell(db, fest, s, [member.user_id], "You are on duty", skip=user.id)
    db.commit()
    db.refresh(s)
    return _out(s, _me(db, fest, user), datetime.now())


@router.delete("/{slug}/shifts/{shift_id}/people/{member_id}", response_model=schemas.ShiftOut)
def take_off(slug: str, shift_id: int, member_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _need_staff(db, fest, user)
    s = _shift(db, fest, shift_id)
    a = next((x for x in s.assignments if x.member_id == member_id), None)
    if not a:
        raise HTTPException(status_code=404, detail="That person is not on this duty")
    _tell(db, fest, s, [a.user_id], "Taken off a duty", skip=user.id)
    s.assignments.remove(a)
    db.commit()
    db.refresh(s)
    return _out(s, _me(db, fest, user), datetime.now())


@router.post("/{slug}/shifts/{shift_id}/claim", response_model=schemas.ShiftOut)
def claim(slug: str, shift_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    s = _shift(db, fest, shift_id)
    me = _me(db, fest, user)
    if not me:
        raise HTTPException(status_code=403, detail="Only the fest's committee can take duties")
    if not s.open_signup:
        raise HTTPException(status_code=400, detail="This duty is not open for sign-up. Ask the core team")
    if s.ends_at <= datetime.now():
        raise HTTPException(status_code=400, detail="That duty is already over")
    if s.filled >= s.needed:
        raise HTTPException(status_code=400, detail="This duty is already full")
    _put_on(db, s, me)
    db.commit()
    db.refresh(s)
    return _out(s, me, datetime.now())


@router.delete("/{slug}/shifts/{shift_id}/claim", response_model=schemas.ShiftOut)
def leave(slug: str, shift_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    s = _shift(db, fest, shift_id)
    me = _me(db, fest, user)
    a = next((x for x in s.assignments if me and x.member_id == me.id), None)
    if not a:
        raise HTTPException(status_code=404, detail="You are not on this duty")
    if s.starts_at <= datetime.now():
        raise HTTPException(status_code=400, detail="This duty has started. Ask the core team to change it")
    s.assignments.remove(a)
    for staff in db.query(models.FestMember).filter(models.FestMember.fest_id == fest.id, models.FestMember.role == models.FestMemberRoleEnum.owner).all():
        if staff.user_id != user.id:
            notices.notify(db, staff.user_id, "shift", f"{user.name} left a duty: {s.title}"[:120], f"{fest.name}: {roster.when_text(s)} now needs {s.needed - s.filled} more."[:500])
    db.commit()
    db.refresh(s)
    return _out(s, me, datetime.now())


@router.post("/{slug}/shifts/{shift_id}/arrive", response_model=schemas.ShiftOut)
def arrive(slug: str, shift_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    s = _shift(db, fest, shift_id)
    me = _me(db, fest, user)
    a = next((x for x in s.assignments if me and x.member_id == me.id), None)
    if not a:
        raise HTTPException(status_code=404, detail="You are not on this duty")
    now = datetime.now()
    if now < s.starts_at - roster.ARRIVE_EARLY:
        raise HTTPException(status_code=400, detail="It is too early to say you are here. You can do it from 30 minutes before the duty starts")
    if now >= s.ends_at:
        raise HTTPException(status_code=400, detail="This duty is over")
    a.arrived_at, a.no_show = now, False
    db.commit()
    db.refresh(s)
    return _out(s, me, now)


@router.put("/{slug}/shifts/{shift_id}/attendance", response_model=schemas.ShiftOut)
def attendance(slug: str, shift_id: int, data: schemas.ShiftAttendanceIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _need_staff(db, fest, user)
    s = _shift(db, fest, shift_id)
    by_member = {a.member_id: a for a in s.assignments}
    for mark in data.marks:
        a = by_member.get(mark.member_id)
        if not a:
            raise HTTPException(status_code=400, detail="Some of those people are not on this duty")
        if mark.status == "arrived":
            a.arrived_at, a.no_show = a.arrived_at or datetime.now(), False
        elif mark.status == "no_show":
            a.arrived_at, a.no_show = None, True
        else:
            a.arrived_at, a.no_show = None, False
    db.commit()
    db.refresh(s)
    return _out(s, _me(db, fest, user), datetime.now())
