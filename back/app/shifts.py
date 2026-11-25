"""Duty roster logic shared by the shift routes and the dashboard."""

from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app import models

ARRIVE_EARLY = timedelta(minutes=30)   # "I am here" opens this long before a duty starts


def state_of(shift: models.Shift, now: datetime) -> str:
    if shift.ends_at <= now:
        return "over"
    return "now" if shift.starts_at <= now else "upcoming"


def clash(db: Session, member_id: int, starts_at: datetime, ends_at: datetime, ignore_shift_id: Optional[int] = None) -> Optional[models.Shift]:
    """Another duty of this person that overlaps these hours, if any."""
    q = (
        db.query(models.Shift).join(models.ShiftAssignment, models.ShiftAssignment.shift_id == models.Shift.id)
        .filter(models.ShiftAssignment.member_id == member_id, models.Shift.starts_at < ends_at, models.Shift.ends_at > starts_at)
    )
    if ignore_shift_id is not None:
        q = q.filter(models.Shift.id != ignore_shift_id)
    return q.first()


def when_text(shift: models.Shift) -> str:
    day = shift.starts_at.strftime("%a %d %b").replace(" 0", " ")
    return f"{day}, {shift.starts_at.strftime('%I:%M %p').lstrip('0')} to {shift.ends_at.strftime('%I:%M %p').lstrip('0')}"


def upcoming_shifts(db: Session, fest_id: int, now: datetime) -> List[models.Shift]:
    return db.query(models.Shift).filter(models.Shift.fest_id == fest_id, models.Shift.ends_at > now).order_by(models.Shift.starts_at, models.Shift.id).all()


def gaps_within(db: Session, fest_id: int, now: datetime, days: int) -> List[models.Shift]:
    """Duties starting in the next few days that still need people."""
    horizon = now + timedelta(days=days)
    return [s for s in upcoming_shifts(db, fest_id, now) if s.starts_at <= horizon and s.filled < s.needed]
