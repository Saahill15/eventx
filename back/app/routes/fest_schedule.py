"""
The master schedule: every event of the fest by day and venue, with clashes marked.

  GET /api/fests/{slug}/schedule                                           the schedule (any committee member)
  GET /api/fests/{slug}/schedule/check?day=&time=&end_time=&location=&exclude_event_id=
                                                                          would an event here clash with an existing one? (used while editing an event)
"""

from datetime import date
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
    _, events = _fest_and_events(db, slug, user)
    return build_schedule(events)


@router.get("/{slug}/schedule/check", response_model=schemas.ClashCheckOut)
def check_clash(
    slug: str,
    day: date,
    time: Optional[str] = None,
    end_time: Optional[str] = None,
    location: Optional[str] = None,
    exclude_event_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _, events = _fest_and_events(db, slug, user)
    hits = clashing_with(events, day, time, end_time, location, exclude_event_id)
    return {"clashes": build_schedule(hits)["days"][0]["items"] if hits else []}
