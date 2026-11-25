"""
The master schedule: every event of the fest by day and venue, with clashes marked.

  GET /api/fests/{slug}/schedule                                           the schedule (any committee member)
  GET /api/fests/{slug}/schedule/check?day=&time=&end_time=&location=&exclude_event_id=&span_days=
                                                                          would an event here clash with an existing one? (used while editing an event)
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.permissions import is_fest_member
from app.schedule import build_schedule, clashing_with

router = APIRouter()


def _fest_and_events(db: Session, slug: str, user):
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    if not is_fest_member(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's committee can see its schedule")
    events = db.query(models.Event).filter(models.Event.fest_id == fest.id, models.Event.status != models.StatusEnum.rejected).all()
    return fest, events


@router.get("/{slug}/schedule", response_model=schemas.ScheduleOut)
def get_schedule(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest, events = _fest_and_events(db, slug, user)
    days = [fest.start_date + timedelta(days=i) for i in range(fest.days_count)] if fest.start_date and fest.days_count else None
    return build_schedule(events, days)


@router.get("/{slug}/schedule/check", response_model=schemas.ClashCheckOut)
def check_clash(
    slug: str,
    day: date,
    time: Optional[str] = None,
    end_time: Optional[str] = None,
    location: Optional[str] = None,
    exclude_event_id: Optional[int] = None,
    span_days: int = 1,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _, events = _fest_and_events(db, slug, user)
    hits = clashing_with(events, day, time, end_time, location, exclude_event_id, span_days)
    first = {}
    for h in hits:
        first[h.id] = h
    # one entry per clashing event, shown on its first day
    items = [i for d in build_schedule(list(first.values()))["days"] for i in d["items"] if i["day_of_event"] == 1]
    return {"clashes": items}
