"""
Contingents entering events.

An event can be opened to visiting colleges. A contingent's leader then enters it, choosing which people from the contingent's
list take part: one person for a solo event, a team within the event's size for a team event. Each event sets how many entries a
college may send, what an entry costs and until when it can be entered; the committee can enter or remove on a college's behalf.

  GET    /api/fests/{slug}/entries/mine            the events a leader can enter, and their contingent's entries
  GET    /api/fests/{slug}/entries                 every entry (committee), optionally for one event
  POST   /api/fests/{slug}/entries                 enter an event (a leader for their own contingent, the committee for anyone)
  PUT    /api/fests/{slug}/entries/{id}            change who takes part
  DELETE /api/fests/{slug}/entries/{id}            withdraw it (the committee's removal can carry a reason)
"""

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import competition as comp
from app import contingent_money as money
from app import models, notices, schedule, schemas
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.money import rupees
from app.permissions import is_fest_staff
from app.routes.contingents import _fest, _role

router = APIRouter()
MAX_TEAM = 100


# ─── helpers ──────────────────────────────────────────────────────────────────

def _my_contingent(db: Session, fest: models.Fest, user) -> Optional[models.Contingent]:
    for c in db.query(models.Contingent).filter(models.Contingent.fest_id == fest.id, models.Contingent.status == "approved").order_by(models.Contingent.id).all():
        if _role(c, user):
            return c
    return None


def _staff(db: Session, fest: models.Fest, user) -> bool:
    return is_fest_staff(db, fest.id, user)


def _closed_reason(event: models.Event, staff: bool) -> Optional[str]:
    """Why a contingent cannot enter this event right now, or None. The committee may enter after the deadline."""
    if not event.contingent_entries:
        return "This event is not open to visiting colleges"
    if event.cancelled:
        return "This event has been cancelled"
    if event.status != models.StatusEnum.approved:
        return "This event is not published yet"
    if not staff and event.entry_deadline and date.today() > event.entry_deadline:
        return f"Entries closed on {event.entry_deadline.strftime('%d %b %Y').lstrip('0')}"
    return None


def _entry_out(db: Session, e: models.ContingentEntry, show_phone: bool, warnings: Optional[List[str]] = None) -> schemas.EntryOut:
    return schemas.EntryOut(
        id=e.id, contingent_id=e.contingent_id, contingent_label=money.label(e.contingent), college_name=e.contingent.college_name,
        event_id=e.event_id, event_title=e.event.title, event_date=e.event.date, event_time=e.event.time, location=e.event.location, status=e.status, note=e.note,
        members=[schemas.EntryMemberOut(member_id=m.member_id, name=m.member.name, year=m.member.year, phone=m.member.phone if show_phone else None) for m in sorted(e.members, key=lambda x: x.member_id) if m.member],
        fee=rupees(money.entry_fee_paise(e)) if e.status == "confirmed" else 0, warnings=warnings or [],
    )


def _clash_warnings(db: Session, c: models.Contingent, event: models.Event, member_ids: List[int], skip_entry_id: Optional[int]) -> List[str]:
    """A person entered in two events that overlap in time. It is a warning, not a block: the committee may know better."""
    mine = schedule.span(event.time, event.end_time)
    if mine is None:
        return []
    my_days = {d for d, _ in schedule.days_of(event)}
    out = []
    others = db.query(models.ContingentEntry).filter(models.ContingentEntry.contingent_id == c.id, models.ContingentEntry.status == "confirmed", models.ContingentEntry.event_id != event.id).all()
    for other in others:
        if other.id == skip_entry_id or other.event.cancelled:
            continue
        theirs = schedule.span(other.event.time, other.event.end_time)
        if theirs is None or not (my_days & {d for d, _ in schedule.days_of(other.event)}) or not schedule.overlaps(mine, theirs):
            continue
        for m in other.members:
            if m.member_id in member_ids and m.member:
                out.append(f"{m.member.name} is also entered in {other.event.title}, which is at the same time")
    return out


def _check(db: Session, fest: models.Fest, c: models.Contingent, event: models.Event, member_ids: List[int], staff: bool, entry: Optional[models.ContingentEntry]) -> None:
    reason = _closed_reason(event, staff)
    if reason:
        raise HTTPException(status_code=400, detail=reason)
    if c.status != "approved":
        raise HTTPException(status_code=400, detail="Only an approved contingent can enter events")
    if c.id in comp.disqualified_everywhere(comp.active_penalties(db, fest.id)):
        raise HTTPException(status_code=400, detail="This contingent has been disqualified and cannot enter events")
    ids = list(member_ids)
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=400, detail="The same person is listed twice")
    roster = {m.id for m in c.members}
    if any(i not in roster for i in ids):
        raise HTTPException(status_code=400, detail="Everyone taking part must be on the contingent's list of people")
    if event.is_team_event:
        low, high = event.team_min or 1, event.team_max or MAX_TEAM
        if not low <= len(ids) <= high:
            raise HTTPException(status_code=400, detail=f"A team for this event has {low}{'' if low == high else f' to {high}'} people")
    elif len(ids) != 1:
        raise HTTPException(status_code=400, detail="This is a solo event: choose one person for each entry")
    others = db.query(models.ContingentEntry).filter(models.ContingentEntry.contingent_id == c.id, models.ContingentEntry.event_id == event.id, models.ContingentEntry.status == "confirmed").all()
    others = [o for o in others if not entry or o.id != entry.id]
    if entry is None and len(others) >= event.entries_per_contingent:
        raise HTTPException(status_code=400, detail=f"A college can send {event.entries_per_contingent} entr{'y' if event.entries_per_contingent == 1 else 'ies'} to this event, and you have already sent {len(others)}")
    taken = {m.member_id for o in others for m in o.members}
    if any(i in taken for i in ids):
        raise HTTPException(status_code=400, detail="Someone you chose is already in another entry for this event")


def _enterable(db: Session, fest: models.Fest, c: models.Contingent, staff: bool) -> List[schemas.EnterableEvent]:
    events = db.query(models.Event).filter(models.Event.fest_id == fest.id, models.Event.contingent_entries.is_(True), models.Event.status == models.StatusEnum.approved).order_by(models.Event.date, models.Event.id).all()
    counts = {}
    for e in db.query(models.ContingentEntry).filter(models.ContingentEntry.contingent_id == c.id, models.ContingentEntry.status == "confirmed").all():
        counts[e.event_id] = counts.get(e.event_id, 0) + 1
    out = []
    for e in events:
        reason = _closed_reason(e, staff)
        used = counts.get(e.id, 0)
        if not reason and used >= e.entries_per_contingent:
            reason = "You have sent as many entries as this event allows"
        out.append(schemas.EnterableEvent(
            event_id=e.id, title=e.title, date=e.date, time=e.time, end_time=e.end_time, location=e.location, span_days=e.span_days or 1, is_team_event=bool(e.is_team_event),
            team_min=e.team_min, team_max=e.team_max, entries_per_contingent=e.entries_per_contingent, entry_fee=rupees(e.entry_fee_paise), entry_fee_per=e.entry_fee_per,
            deadline=e.entry_deadline, open=reason is None, closed_reason=reason, my_entries=used,
        ))
    return out


# ─── routes ───────────────────────────────────────────────────────────────────

@router.get("/{slug}/entries/mine", response_model=Optional[schemas.MyEntries])
def my_entries(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    c = _my_contingent(db, fest, user)
    if not c:
        return None
    rows = db.query(models.ContingentEntry).filter(models.ContingentEntry.contingent_id == c.id, models.ContingentEntry.status != "withdrawn").order_by(models.ContingentEntry.id).all()
    out = []
    for e in rows:
        ids = [m.member_id for m in e.members]
        out.append(_entry_out(db, e, True, _clash_warnings(db, c, e.event, ids, e.id) if e.status == "confirmed" else []))
    return schemas.MyEntries(contingent_id=c.id, events=_enterable(db, fest, c, False), entries=out)


@router.get("/{slug}/entries", response_model=List[schemas.EntryOut])
def all_entries(slug: str, event_id: Optional[int] = None, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    if not _staff(db, fest, user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can see every entry")
    q = db.query(models.ContingentEntry).filter(models.ContingentEntry.fest_id == fest.id)
    if event_id is not None:
        q = q.filter(models.ContingentEntry.event_id == event_id)
    return [_entry_out(db, e, True) for e in q.order_by(models.ContingentEntry.event_id, models.ContingentEntry.id).all()]


@router.post("/{slug}/entries", response_model=schemas.EntryOut, status_code=status.HTTP_201_CREATED)
def enter_event(slug: str, data: schemas.EntryIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    staff = _staff(db, fest, user)
    if staff and data.contingent_id is not None:
        c = db.query(models.Contingent).filter(models.Contingent.id == data.contingent_id, models.Contingent.fest_id == fest.id).first()
        if not c:
            raise HTTPException(status_code=404, detail="Contingent not found")
    else:
        c = _my_contingent(db, fest, user)
        if not c:
            raise HTTPException(status_code=403 if not staff else 400, detail="Only a contingent's leaders and the committee can enter events" if not staff else "Say which contingent is entering")
        if data.contingent_id is not None and data.contingent_id != c.id:
            raise HTTPException(status_code=403, detail="You can only enter events for your own contingent")
    event = db.query(models.Event).filter(models.Event.id == data.event_id, models.Event.fest_id == fest.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found in this fest")
    _check(db, fest, c, event, data.member_ids, staff, None)
    entry = models.ContingentEntry(fest_id=fest.id, contingent_id=c.id, event_id=event.id, status="confirmed", created_by_id=user.id)
    entry.members = [models.ContingentEntryMember(member_id=i) for i in data.member_ids]
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _entry_out(db, entry, True, _clash_warnings(db, c, event, data.member_ids, entry.id))


def _my_entry(db: Session, fest: models.Fest, entry_id: int, user):
    e = db.query(models.ContingentEntry).filter(models.ContingentEntry.id == entry_id, models.ContingentEntry.fest_id == fest.id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Entry not found")
    staff = _staff(db, fest, user)
    if not staff and not _role(e.contingent, user):
        raise HTTPException(status_code=403, detail="Only this contingent's leaders and the committee can change its entries")
    return e, staff


@router.put("/{slug}/entries/{entry_id}", response_model=schemas.EntryOut)
def change_entry(slug: str, entry_id: int, data: schemas.EntryUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    e, staff = _my_entry(db, fest, entry_id, user)
    if e.status != "confirmed":
        raise HTTPException(status_code=400, detail="This entry is no longer active")
    _check(db, fest, e.contingent, e.event, data.member_ids, staff, e)
    e.members = [models.ContingentEntryMember(member_id=i) for i in data.member_ids]
    db.commit()
    db.refresh(e)
    return _entry_out(db, e, True, _clash_warnings(db, e.contingent, e.event, data.member_ids, e.id))


@router.delete("/{slug}/entries/{entry_id}", response_model=schemas.EntryOut)
def withdraw_entry(slug: str, entry_id: int, reason: Optional[str] = Query(default=None, max_length=300), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """A leader withdraws their entry (until the deadline). The committee can remove one at any time, and the leader is told why."""
    fest = _fest(db, slug)
    e, staff = _my_entry(db, fest, entry_id, user)
    if e.status != "confirmed":
        raise HTTPException(status_code=400, detail="This entry is no longer active")
    own = _role(e.contingent, user) is not None
    if own and not staff:
        if e.event.entry_deadline and date.today() > e.event.entry_deadline:
            raise HTTPException(status_code=400, detail="Entries are closed, so this one can only be removed by the committee")
        e.status = "withdrawn"
    else:
        e.status, e.note = "removed", (reason or "").strip() or None
        notices.notify(db, e.contingent.leader_user_id, "contingent", f"Your entry in {e.event.title} was removed", f"The committee removed {money.label(e.contingent)}'s entry in {e.event.title}." + (f" Reason: {e.note}" if e.note else ""))
    db.commit()
    db.refresh(e)
    return _entry_out(db, e, True)
