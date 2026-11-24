"""
Committee meetings: schedule one, share the agenda, record attendance and what was decided, and turn the follow-ups into tasks.

  GET    /api/fests/{slug}/meetings?when=upcoming|past   the meetings (any committee member), soonest first (past: latest first)
  POST   /api/fests/{slug}/meetings                      schedule one and tell the people invited (director or core team)
  GET    /api/fests/{slug}/meetings/{id}                 one meeting with its invitees and the action items it produced
  PATCH  /api/fests/{slug}/meetings/{id}                 change the details, agenda, minutes or who is invited
  PUT    /api/fests/{slug}/meetings/{id}/attendance      record who came
  DELETE /api/fests/{slug}/meetings/{id}                 cancel and tell the people invited; its action items stay
Action items are ordinary tasks that carry the meeting's id (create them with POST /tasks and meeting_id).
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import models, notices, schemas
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.permissions import is_fest_member, is_fest_staff

router = APIRouter()

MAX_MEETINGS = 300


def _fest(db: Session, slug: str) -> models.Fest:
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    return fest


def _meeting(db: Session, fest: models.Fest, meeting_id: int) -> models.FestMeeting:
    m = db.query(models.FestMeeting).filter(models.FestMeeting.id == meeting_id, models.FestMeeting.fest_id == fest.id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return m


def _members(db: Session, fest: models.Fest, ids: Optional[List[int]]) -> List[models.FestMember]:
    """The committee members behind these ids; everyone when ids is None. Refuses ids from outside this fest."""
    everyone = db.query(models.FestMember).filter(models.FestMember.fest_id == fest.id).all()
    if ids is None:
        return everyone
    by_id = {m.id: m for m in everyone}
    unknown = [i for i in ids if i not in by_id]
    if unknown:
        raise HTTPException(status_code=400, detail="Some of the people invited are not on this fest's committee")
    return [by_id[i] for i in dict.fromkeys(ids)]


def _out(db: Session, m: models.FestMeeting) -> dict:
    actions = db.query(models.FestTask).filter(models.FestTask.meeting_id == m.id).all()
    return {**schemas.MeetingOut.model_validate(m).model_dump(), "action_count": len(actions), "open_action_count": len([t for t in actions if t.status != "done"])}


def _detail(db: Session, m: models.FestMeeting) -> schemas.MeetingDetail:
    actions = db.query(models.FestTask).filter(models.FestTask.meeting_id == m.id).order_by(models.FestTask.id).all()
    attendees = sorted(m.attendees, key=lambda a: (a.user_name or "").lower())
    base = _out(db, m)
    return schemas.MeetingDetail(**base, attendees=[schemas.MeetingAttendeeOut.model_validate(a) for a in attendees], actions=[schemas.TaskOut.model_validate(t) for t in actions])


def _when(dt: datetime) -> str:
    return dt.strftime("%a %d %b, %I:%M %p").replace(" 0", " ")


def _tell(db: Session, fest: models.Fest, meeting: models.FestMeeting, members: List[models.FestMember], skip_user_id: int, headline: str) -> None:
    where = f" at {meeting.location}" if meeting.location else ""
    for member in members:
        if member.user_id == skip_user_id:
            continue
        notices.notify(db, member.user_id, "meeting", f"{headline}: {meeting.title}"[:120], f"{fest.name}: {_when(meeting.starts_at)}{where}."[:500])


@router.get("/{slug}/meetings", response_model=List[schemas.MeetingOut])
def list_meetings(slug: str, when: str = Query(default="upcoming", pattern="^(upcoming|past)$"), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    if not is_fest_member(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's committee can see its meetings")
    q = db.query(models.FestMeeting).filter(models.FestMeeting.fest_id == fest.id)
    now = datetime.now()
    q = q.filter(models.FestMeeting.starts_at >= now).order_by(models.FestMeeting.starts_at) if when == "upcoming" else q.filter(models.FestMeeting.starts_at < now).order_by(models.FestMeeting.starts_at.desc())
    return [_out(db, m) for m in q.all()]


@router.post("/{slug}/meetings", response_model=schemas.MeetingDetail, status_code=status.HTTP_201_CREATED)
def add_meeting(slug: str, data: schemas.MeetingIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    if not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can schedule meetings")
    if db.query(models.FestMeeting).filter(models.FestMeeting.fest_id == fest.id).count() >= MAX_MEETINGS:
        raise HTTPException(status_code=400, detail=f"A fest can have at most {MAX_MEETINGS} meetings")
    invited = _members(db, fest, data.member_ids)
    meeting = models.FestMeeting(fest_id=fest.id, title=data.title, starts_at=data.starts_at.replace(tzinfo=None), location=data.location or None, agenda=data.agenda or None, created_by_id=user.id)
    meeting.attendees = [models.FestMeetingAttendee(member_id=m.id) for m in invited]
    db.add(meeting)
    db.flush()
    _tell(db, fest, meeting, invited, user.id, "New meeting")
    db.commit()
    db.refresh(meeting)
    return _detail(db, meeting)


@router.get("/{slug}/meetings/{meeting_id}", response_model=schemas.MeetingDetail)
def get_meeting(slug: str, meeting_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    if not is_fest_member(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's committee can see its meetings")
    return _detail(db, _meeting(db, fest, meeting_id))


@router.patch("/{slug}/meetings/{meeting_id}", response_model=schemas.MeetingDetail)
def update_meeting(slug: str, meeting_id: int, data: schemas.MeetingUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    if not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can change meetings")
    meeting = _meeting(db, fest, meeting_id)
    updates = data.model_dump(exclude_unset=True)
    moved = False
    if "title" in updates:
        if not updates["title"]:
            raise HTTPException(status_code=400, detail="A meeting needs a title")
        meeting.title = updates["title"]
    if "starts_at" in updates and updates["starts_at"] is not None:
        new_time = updates["starts_at"].replace(tzinfo=None)
        moved = moved or new_time != meeting.starts_at
        meeting.starts_at = new_time
    if "location" in updates:
        new_place = updates["location"] or None
        moved = moved or new_place != meeting.location
        meeting.location = new_place
    if "agenda" in updates:
        meeting.agenda = updates["agenda"] or None
    if "minutes" in updates:
        meeting.minutes = updates["minutes"] or None

    newly_invited: List[models.FestMember] = []
    if "member_ids" in updates and updates["member_ids"] is not None:
        wanted = _members(db, fest, updates["member_ids"])
        keep = {m.id for m in wanted}
        have = {a.member_id for a in meeting.attendees}
        meeting.attendees = [a for a in meeting.attendees if a.member_id in keep]
        for m in wanted:
            if m.id not in have:
                meeting.attendees.append(models.FestMeetingAttendee(member_id=m.id))
                newly_invited.append(m)
    db.flush()
    if newly_invited:
        _tell(db, fest, meeting, newly_invited, user.id, "New meeting")
    if moved:
        _tell(db, fest, meeting, [a.member for a in meeting.attendees if a.member and a.member not in newly_invited], user.id, "Meeting changed")
    db.commit()
    db.refresh(meeting)
    return _detail(db, meeting)


@router.put("/{slug}/meetings/{meeting_id}/attendance", response_model=schemas.MeetingDetail)
def record_attendance(slug: str, meeting_id: int, data: schemas.MeetingAttendance, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    if not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can record attendance")
    meeting = _meeting(db, fest, meeting_id)
    invited = {a.member_id for a in meeting.attendees}
    if any(i not in invited for i in data.attended_member_ids):
        raise HTTPException(status_code=400, detail="Attendance can only be recorded for people who were invited")
    came = set(data.attended_member_ids)
    for a in meeting.attendees:
        a.attended = a.member_id in came
    db.commit()
    db.refresh(meeting)
    return _detail(db, meeting)


@router.delete("/{slug}/meetings/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_meeting(slug: str, meeting_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    if not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can cancel meetings")
    meeting = _meeting(db, fest, meeting_id)
    if meeting.starts_at > datetime.now():
        _tell(db, fest, meeting, [a.member for a in meeting.attendees if a.member], user.id, "Meeting cancelled")
    # The follow-ups it produced are real work, so they stay, just no longer tied to a meeting that is gone
    db.query(models.FestTask).filter(models.FestTask.meeting_id == meeting.id).update({"meeting_id": None}, synchronize_session=False)
    db.delete(meeting)
    db.commit()
