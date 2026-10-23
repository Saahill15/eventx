"""
Routes for Fest Event Registration.
Mounted under /api/fest-events by main.py.

  POST   /api/fest-events/{event_id}/register   → register for a fest event
  GET    /api/fest-events/{event_id}/registrations → list registrations (privileged)
  GET    /api/fest-events/my-registrations        → current user's registrations
"""

import csv
import io
import secrets
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models, schemas
from app.auth.dependencies import get_current_user
from app.permissions import is_fest_member, is_fest_staff
from app.routes.event_questions import validate_answers

router = APIRouter()


# ─── Shared registration rules ───────────────────────────────────────────────

def _open_fest_event(db: Session, event_id: int, user: models.User) -> models.Event:
    """The event, if this person may register for it right now."""
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event or event.status != models.StatusEnum.approved:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.event_type != models.EventTypeEnum.fest:
        raise HTTPException(status_code=400, detail="Registration is only available for fest events")
    if event.cancelled:
        raise HTTPException(status_code=400, detail="This event has been cancelled")
    if not event.requires_registration:
        raise HTTPException(status_code=400, detail="This event does not require registration")
    if event.students_only and not user.is_student_verified:
        raise HTTPException(status_code=403, detail="This event is for verified students. Verify your student status in your profile first.")
    return event


def _approved_pass(db: Session, event: models.Event, user: models.User) -> models.FestPass:
    fest_pass = (
        db.query(models.FestPass)
        .filter(
            models.FestPass.user_id == user.id,
            models.FestPass.fest_id == event.fest_id,
            models.FestPass.status == models.FestPassStatusEnum.approved,
        )
        .first()
    )
    if not fest_pass:
        raise HTTPException(status_code=400, detail="You must hold an approved entry pass for this fest before registering for events")
    return fest_pass


def _existing_registration(db: Session, fest_pass: models.FestPass, event_id: int):
    return (
        db.query(models.EventRegistration)
        .filter(models.EventRegistration.fest_pass_id == fest_pass.id, models.EventRegistration.event_id == event_id)
        .first()
    )


def _active(q):
    return q.filter(models.EventRegistration.approval_status.in_([models.RegApprovalStatusEnum.approved, models.RegApprovalStatusEnum.pending]))


def _seats_taken(db: Session, event: models.Event) -> int:
    """Registrations still in play. For a team event the limit counts teams, so this counts teams."""
    q = _active(db.query(models.EventRegistration).filter(models.EventRegistration.event_id == event.id))
    if event.is_team_event:
        return q.filter(models.EventRegistration.team_id.isnot(None)).with_entities(models.EventRegistration.team_id).distinct().count()
    return q.count()


def _new_registration(event: models.Event, fest_pass: models.FestPass, user: models.User, approval=None, team_id=None) -> models.EventRegistration:
    """A registration with the right approval and payment state. Payment is simulated and always succeeds for now."""
    if approval is None:
        if event.is_paid or event.approval_mode == models.ApprovalModeEnum.auto:
            approval = models.RegApprovalStatusEnum.approved
        else:
            approval = models.RegApprovalStatusEnum.pending
    if event.is_paid:
        payment = models.RegPaymentStatusEnum.paid
        # Verified students get the student price when the event has one
        amount_due = event.student_price if (user.is_student_verified and event.student_price is not None) else event.price
    else:
        payment, amount_due = models.RegPaymentStatusEnum.unpaid, 0.0
    return models.EventRegistration(
        fest_pass_id=fest_pass.id, event_id=event.id, approval_status=approval, payment_status=payment, amount_due=amount_due, team_id=team_id,
    )


def _save_answers(db: Session, registration: models.EventRegistration, answers) -> None:
    for question, value in answers:
        db.add(models.RegistrationAnswer(registration_id=registration.id, question_id=question.id, answer=value))


# ─── POST /fest-events/{event_id}/register ───────────────────────────────────

@router.post("/{event_id}/register", response_model=schemas.EventRegistrationOut, status_code=status.HTTP_201_CREATED)
def register_for_event(
    event_id: int,
    data: Optional[schemas.RegisterIn] = Body(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Register the current user for a fest event. Needs an approved fest pass; answers the event's questions.
    Paid events are confirmed at once (payment is simulated), free ones by the event's approval mode.
    Registering again returns the existing registration.
    """
    event = _open_fest_event(db, event_id, current_user)
    if event.is_team_event:
        raise HTTPException(status_code=400, detail="This is a team event. Create a team, or join one with its code.")
    fest_pass = _approved_pass(db, event, current_user)
    existing = _existing_registration(db, fest_pass, event_id)
    if existing:
        return existing

    answers = validate_answers(event, data.answers if data else [])
    if event.registration_limit is not None and _seats_taken(db, event) >= event.registration_limit:
        raise HTTPException(status_code=400, detail="Registration full")

    registration = _new_registration(event, fest_pass, current_user)
    db.add(registration)
    db.flush()
    _save_answers(db, registration, answers)
    db.commit()
    db.refresh(registration)
    return registration


# ─── Teams ───────────────────────────────────────────────────────────────────

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # no 0/O or 1/I, so a code read aloud is not misheard


def _new_code(db: Session) -> str:
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        if not db.query(models.Team).filter(models.Team.code == code).first():
            return code


def _team_status(team: models.Team) -> str:
    """A team's approval status is its leader's (members always follow the leader's)."""
    lead = next((r for r in team.registrations if r.fest_pass and r.fest_pass.user_id == team.leader_user_id), None)
    return lead.approval_status.value if lead else "pending"


def _team_out(team: models.Team, viewer: models.User, staff: bool) -> schemas.TeamOut:
    event = team.event
    members = sorted(team.registrations, key=lambda r: (not r.is_team_leader, r.created_at or datetime.min))
    size = len([r for r in members if r.approval_status != models.RegApprovalStatusEnum.rejected])
    return schemas.TeamOut(
        id=team.id, event_id=team.event_id, name=team.name, code=team.code, size=size,
        team_min=event.team_min, team_max=event.team_max, complete=size >= (event.team_min or 1), status=_team_status(team),
        i_am_leader=team.leader_user_id == viewer.id,
        members=[schemas.TeamMemberOut(
            registration_id=r.id, name=r.user_name, email=r.user_email if staff else None, is_leader=r.is_team_leader,
            approval_status=r.approval_status.value, attended=bool(r.attended),
        ) for r in members],
    )


@router.post("/{event_id}/teams", response_model=schemas.TeamOut, status_code=status.HTTP_201_CREATED)
def create_team(event_id: int, data: schemas.TeamCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Start a team for a team event. You become its leader, answer the event's questions, and get a code to share."""
    event = _open_fest_event(db, event_id, current_user)
    if not event.is_team_event:
        raise HTTPException(status_code=400, detail="This is not a team event")
    fest_pass = _approved_pass(db, event, current_user)
    if _existing_registration(db, fest_pass, event_id):
        raise HTTPException(status_code=400, detail="You are already registered for this event")
    if db.query(models.Team).filter(models.Team.event_id == event_id, func.lower(models.Team.name) == data.name.lower()).first():
        raise HTTPException(status_code=400, detail="A team with that name already exists for this event")
    answers = validate_answers(event, data.answers)
    if event.registration_limit is not None and _seats_taken(db, event) >= event.registration_limit:
        raise HTTPException(status_code=400, detail="Registration full: no more teams can join")

    team = models.Team(event_id=event_id, name=data.name, code=_new_code(db), leader_user_id=current_user.id, created_at=datetime.utcnow())
    db.add(team)
    db.flush()
    registration = _new_registration(event, fest_pass, current_user, team_id=team.id)
    db.add(registration)
    db.flush()
    _save_answers(db, registration, answers)
    db.commit()
    db.refresh(team)
    return _team_out(team, current_user, staff=False)


@router.post("/teams/join", response_model=schemas.TeamOut)
def join_team(data: schemas.TeamJoin, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Join a team with the code its leader shared. You answer the event's questions for yourself."""
    team = db.query(models.Team).filter(models.Team.code == data.code).first()
    if not team:
        raise HTTPException(status_code=404, detail="No team with that code")
    event = _open_fest_event(db, team.event_id, current_user)
    fest_pass = _approved_pass(db, event, current_user)
    if _existing_registration(db, fest_pass, event.id):
        raise HTTPException(status_code=400, detail="You are already registered for this event")
    status_now = _team_status(team)
    if status_now == "rejected":
        raise HTTPException(status_code=400, detail="This team was not approved, so it cannot take new members")
    size = len([r for r in team.registrations if r.approval_status != models.RegApprovalStatusEnum.rejected])
    if event.team_max and size >= event.team_max:
        raise HTTPException(status_code=400, detail=f"This team is full ({event.team_max} people)")
    answers = validate_answers(event, data.answers)

    registration = _new_registration(event, fest_pass, current_user, approval=models.RegApprovalStatusEnum(status_now), team_id=team.id)
    db.add(registration)
    db.flush()
    _save_answers(db, registration, answers)
    db.commit()
    db.refresh(team)
    return _team_out(team, current_user, staff=False)


@router.get("/{event_id}/my-team", response_model=schemas.TeamOut)
def my_team(event_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    registration = (
        db.query(models.EventRegistration)
        .join(models.FestPass, models.EventRegistration.fest_pass_id == models.FestPass.id)
        .filter(models.EventRegistration.event_id == event_id, models.FestPass.user_id == current_user.id, models.EventRegistration.team_id.isnot(None))
        .first()
    )
    if not registration:
        raise HTTPException(status_code=404, detail="You are not in a team for this event")
    return _team_out(registration.team, current_user, staff=False)


@router.get("/{event_id}/teams", response_model=List[schemas.TeamOut])
def list_teams(event_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Every team for the event, with its members (committee only)."""
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_staff(db, event, current_user)
    teams = db.query(models.Team).filter(models.Team.event_id == event_id).order_by(models.Team.created_at).all()
    return [_team_out(t, current_user, staff=True) for t in teams]


def _decide_team(team_id: int, approve: bool, db: Session, user: models.User) -> schemas.TeamOut:
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    event = db.query(models.Event).filter(models.Event.id == team.event_id).first()
    _require_event_staff(db, event, user)
    pending = [r for r in team.registrations if r.approval_status == models.RegApprovalStatusEnum.pending]
    if not pending:
        raise HTTPException(status_code=400, detail="Only pending teams can be decided")
    for r in pending:
        r.approval_status = models.RegApprovalStatusEnum.approved if approve else models.RegApprovalStatusEnum.rejected
    db.commit()
    db.refresh(team)
    return _team_out(team, user, staff=True)


@router.post("/teams/{team_id}/approve", response_model=schemas.TeamOut)
def approve_team(team_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return _decide_team(team_id, True, db, current_user)


@router.post("/teams/{team_id}/reject", response_model=schemas.TeamOut)
def reject_team(team_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return _decide_team(team_id, False, db, current_user)


# ─── helpers ─────────────────────────────────────────────────────────────────

def _require_event_staff(db: Session, event: models.Event, user: models.User):
    if event.event_type != models.EventTypeEnum.fest:
        raise HTTPException(status_code=400, detail="Not a fest event")
    if not is_fest_staff(db, event.fest_id, user):
        raise HTTPException(status_code=403, detail="Forbidden")


def _registrations_for(db: Session, event_id: int):
    return (
        db.query(models.EventRegistration)
        .filter(models.EventRegistration.event_id == event_id)
        .order_by(models.EventRegistration.created_at)
        .all()
    )


def _csv_cell(value) -> str:
    """Neutralise spreadsheet formulas in user-supplied text (CSV injection)."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


# ─── DELETE /fest-events/{event_id}/register ─────────────────────────────────

@router.delete("/{event_id}/register", status_code=status.HTTP_204_NO_CONTENT)
def cancel_my_registration(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Cancel the current user's registration. Frees the seat. Not possible once they have been checked in."""
    registration = (
        db.query(models.EventRegistration)
        .join(models.FestPass, models.EventRegistration.fest_pass_id == models.FestPass.id)
        .filter(models.EventRegistration.event_id == event_id, models.FestPass.user_id == current_user.id)
        .first()
    )
    if not registration:
        raise HTTPException(status_code=404, detail="You are not registered for this event")
    if registration.attended:
        raise HTTPException(status_code=400, detail="You have already attended this event")
    team = registration.team
    if team and team.leader_user_id == current_user.id:
        # A leader leaving breaks up the team: everyone's registration goes, unless someone has already attended
        if any(r.attended for r in team.registrations):
            raise HTTPException(status_code=400, detail="Someone in your team has already attended, so the team cannot be broken up")
        for r in list(team.registrations):
            db.delete(r)
        db.flush()
        db.delete(team)
    else:
        db.delete(registration)
    db.commit()


# ─── POST /fest-events/{event_id}/check-in ───────────────────────────────────

@router.post("/{event_id}/check-in", response_model=schemas.EventCheckInOut)
def check_in_to_event(
    event_id: int,
    data: schemas.QrCodeIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Mark a student as present at one event, by their fest pass QR code (any committee member)."""
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event or event.event_type != models.EventTypeEnum.fest:
        raise HTTPException(status_code=404, detail="Event not found")
    if not is_fest_member(db, event.fest_id, current_user):
        raise HTTPException(status_code=403, detail="Only this fest's committee can check people in")

    fest_pass = (
        db.query(models.FestPass)
        .filter(models.FestPass.qr_code == data.qr_code, models.FestPass.fest_id == event.fest_id)
        .first()
    )
    if not fest_pass:
        raise HTTPException(status_code=404, detail="No pass with that code for this fest")
    if fest_pass.status != models.FestPassStatusEnum.approved:
        raise HTTPException(status_code=400, detail="Pass is blocked: entry denied")

    if event.requires_registration:
        registration = (
            db.query(models.EventRegistration)
            .filter(models.EventRegistration.fest_pass_id == fest_pass.id, models.EventRegistration.event_id == event_id)
            .first()
        )
        if not registration:
            raise HTTPException(status_code=400, detail="This student is not registered for the event")
        if registration.approval_status != models.RegApprovalStatusEnum.approved:
            raise HTTPException(status_code=400, detail="Registration is not approved yet")
    else:
        # Open events have no registration: record attendance on demand
        registration = (
            db.query(models.EventRegistration)
            .filter(models.EventRegistration.fest_pass_id == fest_pass.id, models.EventRegistration.event_id == event_id)
            .first()
        )
        if not registration:
            registration = models.EventRegistration(
                fest_pass_id=fest_pass.id, event_id=event_id,
                approval_status=models.RegApprovalStatusEnum.approved, payment_status=models.RegPaymentStatusEnum.unpaid,
            )
            db.add(registration)
            db.flush()

    if registration.attended:
        raise HTTPException(status_code=400, detail="Already checked in to this event")
    registration.attended = True
    registration.attended_at = datetime.utcnow()
    registration.attended_by = current_user.id
    db.commit()
    db.refresh(registration)
    return schemas.EventCheckInOut(
        registration_id=registration.id, user_name=registration.user_name,
        attended=True, attended_at=registration.attended_at,
    )


# ─── GET /fest-events/{event_id}/registrations ───────────────────────────────

@router.get("/{event_id}/registrations", response_model=List[schemas.EventRegistrationDetailOut])
def list_event_registrations(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    List all registrations for a fest event, with who registered.
    Requires: admin OR owner/core member of the fest.
    """
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_staff(db, event, current_user)
    return _registrations_for(db, event_id)


# ─── GET /fest-events/{event_id}/registrations.csv ───────────────────────────

@router.get("/{event_id}/registrations.csv")
def export_event_registrations(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Download the registrations as a CSV file (same permission as the list)."""
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _require_event_staff(db, event, current_user)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    questions = list(event.questions)
    team_cols = ["Team", "Team leader"] if event.is_team_event else []
    writer.writerow(["Name", "Email"] + team_cols + ["Approval", "Payment", "Amount due (INR)", "Checked in at fest", "Attended this event", "Registered at"] + [_csv_cell(q.label) for q in questions])
    for r in _registrations_for(db, event_id):
        by_question = {a.question_id: a.answer for a in r.answers}
        team_cells = [_csv_cell(r.team_name), "yes" if r.is_team_leader else "no"] if event.is_team_event else []
        writer.writerow([
            _csv_cell(r.user_name), _csv_cell(r.user_email)] + team_cells + [
            r.approval_status.value, r.payment_status.value,
            "" if r.amount_due is None else f"{r.amount_due:g}",
            "yes" if r.checked_in else "no",
            "yes" if r.attended else "no",
            r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
        ] + [_csv_cell(by_question.get(q.id, "")) for q in questions])
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="registrations-event-{event_id}.csv"'},
    )


# ─── POST /fest-events/registrations/{registration_id}/approve | reject ──────

def _decide(registration_id: int, approve: bool, db: Session, user: models.User):
    registration = db.query(models.EventRegistration).filter(models.EventRegistration.id == registration_id).first()
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")
    _require_event_staff(db, registration.event, user)
    if registration.team_id is not None:
        raise HTTPException(status_code=400, detail="This person is in a team: approve or reject the whole team")
    if registration.approval_status != models.RegApprovalStatusEnum.pending:
        raise HTTPException(status_code=400, detail="Only pending registrations can be decided")
    registration.approval_status = (
        models.RegApprovalStatusEnum.approved if approve else models.RegApprovalStatusEnum.rejected
    )
    db.commit()
    db.refresh(registration)
    return registration


@router.post("/registrations/{registration_id}/approve", response_model=schemas.EventRegistrationDetailOut)
def approve_registration(registration_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return _decide(registration_id, True, db, current_user)


@router.post("/registrations/{registration_id}/reject", response_model=schemas.EventRegistrationDetailOut)
def reject_registration(registration_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return _decide(registration_id, False, db, current_user)


# ─── GET /fest-events/my-registrations ───────────────────────────────────────

@router.get("/my-registrations", response_model=List[schemas.EventRegistrationOut])
def my_registrations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return all event registrations belonging to the current user (via their FestPasses)."""
    pass_ids = [fp.id for fp in db.query(models.FestPass).filter(
        models.FestPass.user_id == current_user.id
    ).all()]

    if not pass_ids:
        return []

    return (
        db.query(models.EventRegistration)
        .filter(models.EventRegistration.fest_pass_id.in_(pass_ids))
        .order_by(models.EventRegistration.created_at.desc())
        .all()
    )
