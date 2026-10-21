"""Custom registration questions an event can ask, and the checks applied to a student's answers."""

from typing import Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth.dependencies import get_current_user, get_optional_user
from app.database import get_db
from app.permissions import can_view_event, is_fest_staff
from app.routes.events import _assert_fest_editable

router = APIRouter()


@router.get("/{event_id}/questions", response_model=List[schemas.QuestionOut])
def get_questions(event_id: int, db: Session = Depends(get_db), current_user=Depends(get_optional_user)):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event or not can_view_event(db, event, current_user):
        raise HTTPException(status_code=404, detail="Event not found")
    return event.questions


@router.put("/{event_id}/questions", response_model=List[schemas.QuestionOut])
def put_questions(event_id: int, data: schemas.QuestionsPut, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Replace the event's questions. Once people have registered, existing questions cannot be changed or removed,
    and new ones must be optional (so earlier registrations stay valid).
    """
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event or event.event_type != models.EventTypeEnum.fest:
        raise HTTPException(status_code=404, detail="Event not found")
    if not is_fest_staff(db, event.fest_id, current_user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can change questions")
    _assert_fest_editable(db, event.fest_id, current_user)

    has_registrations = db.query(models.EventRegistration).filter(models.EventRegistration.event_id == event_id).count() > 0
    existing = {q.id: q for q in event.questions}

    if has_registrations:
        kept_ids = {q.id for q in data.questions if q.id is not None}
        if kept_ids != set(existing):
            raise HTTPException(status_code=400, detail="People have registered, so existing questions cannot be removed")
        for q in data.questions:
            if q.id is None:
                if q.required:
                    raise HTTPException(status_code=400, detail="People have registered, so new questions must be optional")
            else:
                old = existing[q.id]
                if (old.label, old.kind, old.required, old.options or None) != (q.label, q.kind, q.required, q.options):
                    raise HTTPException(status_code=400, detail=f"People have registered, so '{old.label}' cannot be changed")
    else:
        for q in data.questions:
            if q.id is not None and q.id not in existing:
                raise HTTPException(status_code=400, detail="Unknown question")

    keep = {q.id for q in data.questions if q.id is not None}
    for qid, q in existing.items():
        if qid not in keep:
            db.delete(q)
    db.flush()
    for position, q in enumerate(data.questions):
        if q.id is not None:
            row = existing[q.id]
            row.label, row.kind, row.required, row.options, row.position = q.label, q.kind, q.required, q.options, position
        else:
            db.add(models.EventQuestion(event_id=event_id, label=q.label, kind=q.kind, required=q.required, options=q.options, position=position))
    db.commit()
    db.refresh(event)
    return event.questions


def validate_answers(event: models.Event, answers: List[schemas.AnswerIn]) -> List[Tuple[models.EventQuestion, str]]:
    """Check a student's answers against the event's questions. Returns (question, answer) pairs worth storing."""
    questions: Dict[int, models.EventQuestion] = {q.id: q for q in event.questions}
    given: Dict[int, str] = {}
    for a in answers:
        if a.question_id not in questions:
            raise HTTPException(status_code=400, detail="You answered a question this event does not ask")
        if a.question_id in given:
            raise HTTPException(status_code=400, detail="Each question can be answered once")
        given[a.question_id] = a.value

    out = []
    for q in event.questions:
        value = (given.get(q.id) or "").strip()
        if not value:
            if q.required:
                raise HTTPException(status_code=400, detail=f"Please answer: {q.label}")
            continue
        if q.kind == "choice" and value not in (q.options or []):
            raise HTTPException(status_code=400, detail=f"Pick one of the options for: {q.label}")
        if q.kind == "yes_no":
            value = value.lower()
            if value not in ("yes", "no"):
                raise HTTPException(status_code=400, detail=f"Answer yes or no for: {q.label}")
        out.append((q, value))
    return out
