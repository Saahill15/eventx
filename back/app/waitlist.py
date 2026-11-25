"""
The waiting list for a full event.

When an event has run out of seats and its committee allows it, people can join a queue. Whenever a seat opens up (someone cancels,
a registration is turned down, the limit is raised) the first person in the queue is offered it: they are registered the same way
they would have been had there been room, at the price and with the code they chose, and they are told. If their ticket or code no
longer works, or they have become ineligible, they are taken off with a plain reason and the next person is tried.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models, notices, pricing, schemas


def waiting(db: Session, event_id: int) -> List[models.WaitlistEntry]:
    return db.query(models.WaitlistEntry).filter(models.WaitlistEntry.event_id == event_id, models.WaitlistEntry.status == "waiting").order_by(models.WaitlistEntry.created_at, models.WaitlistEntry.id).all()


def position_of(db: Session, entry: models.WaitlistEntry) -> Optional[int]:
    if entry.status != "waiting":
        return None
    return [e.id for e in waiting(db, entry.event_id)].index(entry.id) + 1


def is_full(db: Session, event: models.Event) -> bool:
    from app.routes import fest_events as fe
    return event.registration_limit is not None and fe._seats_taken(db, event) >= event.registration_limit


def _drop(db: Session, entry: models.WaitlistEntry, event: models.Event, reason: str) -> None:
    entry.status, entry.note = "removed", reason
    notices.notify(db, entry.user_id, "waitlist", f"We could not give you a seat in {event.title}", f"A seat opened up, but it could not be given to you: {reason}.")


def promote_one(db: Session, event: models.Event, entry: models.WaitlistEntry) -> bool:
    """Register this person from the queue. Whether there is room is the caller's business (the committee can admit past the limit). Returns True if they got in; otherwise they are taken off with a reason."""
    from app.routes import fest_events as fe
    from app.routes.event_questions import validate_answers
    user = entry.user
    fest_pass = db.query(models.FestPass).filter(models.FestPass.user_id == user.id, models.FestPass.fest_id == event.fest_id, models.FestPass.status == models.FestPassStatusEnum.approved).first()
    if not fest_pass:
        _drop(db, entry, event, "you no longer hold an entry pass for this fest")
        return False
    if fe._existing_registration(db, fest_pass, event.id):
        _drop(db, entry, event, "you are already registered for it")
        return False
    if event.students_only and not user.is_student_verified:
        _drop(db, entry, event, "it is for verified students and you are not verified at the moment")
        return False
    try:
        quote = fe._quote_for(db, event, user, entry.ticket_tier_id, entry.promo_code)
        answers = validate_answers(event, [schemas.AnswerIn(**a) for a in (entry.answers or [])])
        if event.is_team_event:
            name = (entry.team_name or "").strip()
            if not name:
                raise HTTPException(status_code=400, detail="there was no team name")
            if db.query(models.Team).filter(models.Team.event_id == event.id, models.Team.name.ilike(name)).first():
                raise HTTPException(status_code=400, detail="a team with that name now exists")
    except HTTPException as exc:
        _drop(db, entry, event, str(exc.detail).rstrip(".").lower() if isinstance(exc.detail, str) else "your choices no longer work")
        return False

    team = None
    if event.is_team_event:
        team = models.Team(event_id=event.id, name=entry.team_name.strip(), code=fe._new_code(db), leader_user_id=user.id, created_at=datetime.utcnow())
        db.add(team)
        db.flush()
    registration = fe._new_registration(event, fest_pass, user, team_id=team.id if team else None, quote=quote)
    db.add(registration)
    db.flush()
    fe._save_answers(db, registration, answers)
    entry.status, entry.promoted_at = "promoted", datetime.utcnow()
    waiting_approval = registration.approval_status == models.RegApprovalStatusEnum.pending
    if registration.awaiting_payment:
        body = f"A seat opened up in {event.title} and it is held for you. Pay within 30 minutes to keep it, from My passes."
    else:
        body = f"A seat opened up in {event.title} and it is yours. " + ("The organisers will confirm it." if waiting_approval else "You are registered.")
    if team:
        body += f" Your team code is {team.code}: share it with the others."
    notices.notify(db, user.id, "waitlist", f"You are in: {event.title}", body)
    return True


def promote(db: Session, event: models.Event) -> int:
    """Offer every free seat to the queue in order. Run whenever a seat may have opened. Returns how many people got in."""
    if event.registration_limit is None or event.cancelled or event.registration_state in ("closed", "not_open", "scheduled"):
        return 0
    got_in = 0
    while is_full(db, event) is False:
        queue = waiting(db, event.id)
        if not queue:
            break
        if promote_one(db, event, queue[0]):
            got_in += 1
        db.flush()
    return got_in
