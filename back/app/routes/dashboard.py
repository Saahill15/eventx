"""
The organiser's home page, in one call.

  GET /api/dashboard   the fests the person is on, what needs them, their tasks, and what is coming up

The numbers a committee can see (registrations, passes) are only filled in for the director and core team; everyone else on a
fest still sees it, their own tasks and the meetings they are invited to.
"""

from datetime import date, datetime, timedelta
from typing import Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import contingent_money, finance, models, schemas
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.fest_review import fest_checklist_items
from app.permissions import FEST_STAFF_ROLES

router = APIRouter()

HORIZON_DAYS = 14
MAX_ATTENTION, MAX_TASKS, MAX_UPCOMING = 12, 8, 14


def _roles(db: Session, user: models.User) -> Dict[int, models.FestMember]:
    """The person's place in each fest. An admin sees every fest as an admin, with no membership row."""
    rows = db.query(models.FestMember).filter(models.FestMember.user_id == user.id).all()
    return {m.fest_id: m for m in rows}


@router.get("", response_model=schemas.DashboardOut)
def organiser_dashboard(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    is_admin = user.role == models.RoleEnum.admin
    members = _roles(db, user)
    fests = db.query(models.Fest).order_by(models.Fest.created_at.desc()).all() if is_admin else [
        f for f in db.query(models.Fest).filter(models.Fest.id.in_(list(members) or [0])).order_by(models.Fest.created_at.desc()).all()
    ]
    today = date.today()
    horizon = today + timedelta(days=HORIZON_DAYS)

    out_fests: List[schemas.DashFest] = []
    attention: List[schemas.DashAttention] = []
    upcoming: List[schemas.DashUpcoming] = []
    my_tasks: List[schemas.DashTask] = []

    for fest in fests:
        member = members.get(fest.id)
        role = "admin" if is_admin else member.role.value
        staff = is_admin or (member is not None and member.role in FEST_STAFF_ROLES)
        events = db.query(models.Event).filter(models.Event.fest_id == fest.id).order_by(models.Event.date).all()

        card = schemas.DashFest(
            id=fest.id, slug=fest.slug, name=fest.name, tagline=fest.tagline, banner_url=fest.banner_url, logo_url=fest.logo_url,
            college_name=fest.college.name if fest.college else None, status=fest.status.value if hasattr(fest.status, "value") else str(fest.status),
            review_status=fest.review_status or "draft", my_role=role, start_date=fest.start_date, end_date=fest.end_date,
            days_count=fest.days_count, dates_tba=bool(fest.dates_tba), events=len(events),
        )

        if staff:
            regs = db.query(models.EventRegistration.event_id, models.EventRegistration.approval_status).filter(
                models.EventRegistration.event_id.in_([e.id for e in events] or [0])).all()
            passes = db.query(models.FestPass).filter(models.FestPass.fest_id == fest.id).all()
            card.registered = sum(1 for _, a in regs if a == models.RegApprovalStatusEnum.approved)
            card.pending = sum(1 for _, a in regs if a == models.RegApprovalStatusEnum.pending)
            card.passes_issued = len(passes)
            card.passes_checked_in = sum(1 for p in passes if p.checked_in)
            if card.status != "live":
                items = fest_checklist_items(fest, events, db.query(models.FestMember).filter(models.FestMember.fest_id == fest.id).count())
                todo = [i for i in items if not i["done"]]
                nxt = next((i for i in todo if i["required"]), todo[0] if todo else None)
                card.setup = schemas.DashSetup(done=len(items) - len(todo), total=len(items), next_label=nxt["label"] if nxt else None, next_tab=nxt["tab"] if nxt else None)

            # ── what needs this person ──
            review = card.review_status
            if review in ("changes_requested", "rejected") and card.status != "live":
                attention.append(schemas.DashAttention(
                    kind=review, tone="red", fest_slug=fest.slug, fest_name=fest.name,
                    title="HiveOut asked for changes" if review == "changes_requested" else "HiveOut did not approve this fest",
                    detail=fest.review_note, tab="overview"))
            if review == "approved" and card.status != "live":
                attention.append(schemas.DashAttention(kind="approved", tone="green", fest_slug=fest.slug, fest_name=fest.name, title="Approved. Make it live when you are ready", tab="overview"))
            if card.pending:
                attention.append(schemas.DashAttention(
                    kind="approvals", tone="amber", fest_slug=fest.slug, fest_name=fest.name,
                    title=f"{card.pending} registration{'s' if card.pending != 1 else ''} to approve", tab="registrations"))
            # Money: spend requests waiting for a decision, and budget lines that have gone over
            waiting_requests = db.query(models.Expense).filter(models.Expense.fest_id == fest.id, models.Expense.status == "pending").count()
            if waiting_requests:
                attention.append(schemas.DashAttention(kind="spend_requests", tone="amber", fest_slug=fest.slug, fest_name=fest.name,
                                                       title=f"{waiting_requests} spend request{'s' if waiting_requests != 1 else ''} to decide", tab="finance"))
            spent = finance.spent_by_line(db, fest.id)
            over = [l for l in db.query(models.BudgetLine).filter(models.BudgetLine.fest_id == fest.id).all() if spent.get(l.id, {}).get("committed", 0) > l.planned_paise]
            if over:
                attention.append(schemas.DashAttention(kind="over_budget", tone="red", fest_slug=fest.slug, fest_name=fest.name,
                                                       title=f"{len(over)} budget line{'s are' if len(over) != 1 else ' is'} over budget", detail=", ".join(l.title for l in over[:2]) + ("…" if len(over) > 2 else ""), tab="finance"))
            # Visiting colleges waiting on the committee: accommodation to place, and fees past their due date
            cs = db.query(models.ContingentSettings).filter(models.ContingentSettings.fest_id == fest.id, models.ContingentSettings.enabled.is_(True)).first()
            if cs:
                waiting = db.query(models.AccommodationRequest).filter(models.AccommodationRequest.fest_id == fest.id, models.AccommodationRequest.status == "requested").count()
                if waiting:
                    attention.append(schemas.DashAttention(kind="accommodation", tone="amber", fest_slug=fest.slug, fest_name=fest.name,
                                                           title=f"{waiting} accommodation request{'s' if waiting != 1 else ''} to place", tab="colleges"))
                if cs.fees_due_on and date.today() > cs.fees_due_on:
                    late = [c for c in db.query(models.Contingent).filter(models.Contingent.fest_id == fest.id, models.Contingent.status == "approved").all()
                            if contingent_money.statement(db, fest, c).balance > 0]
                    if late:
                        attention.append(schemas.DashAttention(kind="fees_overdue", tone="red", fest_slug=fest.slug, fest_name=fest.name,
                                                               title=f"{len(late)} college{'s have' if len(late) != 1 else ' has'} not paid by the due date", detail=", ".join(c.name or c.college_name for c in late[:2]) + ("…" if len(late) > 2 else ""), tab="colleges"))
            for e in events:
                if e.cancelled or not e.requires_registration or e.registration_state not in ("not_open", "closed"):
                    continue
                if e.registration_state == "closed" and e.registration_mode != "closed":
                    continue  # it closed on its own at the deadline, as planned
                if e.date.date() <= horizon and (e.date.date() + timedelta(days=(e.span_days or 1) - 1)) >= today:
                    attention.append(schemas.DashAttention(
                        kind="registration_closed", tone="amber", fest_slug=fest.slug, fest_name=fest.name,
                        title=f"Registration for {e.title} is {'not open yet' if e.registration_state == 'not_open' else 'closed'}",
                        detail=f"The event starts {e.date.strftime('%a %d %b').replace(' 0', ' ')}.", tab="events"))

        # ── events coming up (the committee sees all of its events, not just approved ones) ──
        if staff or member is not None:
            for e in events:
                if e.cancelled:
                    continue
                first, last = e.date.date(), e.date.date() + timedelta(days=(e.span_days or 1) - 1)
                if last < today or first > horizon:
                    continue
                day_no = (today - first).days + 1
                upcoming.append(schemas.DashUpcoming(
                    kind="event", fest_slug=fest.slug, fest_name=fest.name, title=e.title,
                    when=e.date if first >= today else datetime.combine(today, datetime.min.time()), time=e.time or None,
                    detail=(f"day {day_no} of {e.span_days}" if first < today else None) or (e.location or None), tab="events"))

        # ── meetings: all of them for the core team, only the invited for everyone else ──
        if member is not None or is_admin:
            q = db.query(models.FestMeeting).filter(models.FestMeeting.fest_id == fest.id, models.FestMeeting.starts_at >= datetime.combine(today, datetime.min.time()),
                                                    models.FestMeeting.starts_at <= datetime.combine(horizon, datetime.max.time()))
            for mtg in q.order_by(models.FestMeeting.starts_at).all():
                if not staff and not any(a.member_id == (member.id if member else -1) for a in mtg.attendees):
                    continue
                upcoming.append(schemas.DashUpcoming(kind="meeting", fest_slug=fest.slug, fest_name=fest.name, title=mtg.title, when=mtg.starts_at, time=mtg.starts_at.strftime("%H:%M"), detail=mtg.location or None, tab="meetings"))

        # ── my own tasks ──
        if member is not None:
            tasks = db.query(models.FestTask).filter(models.FestTask.fest_id == fest.id, models.FestTask.assignee_member_id == member.id, models.FestTask.status != "done").all()
            for t in tasks:
                my_tasks.append(schemas.DashTask(id=t.id, fest_slug=fest.slug, fest_name=fest.name, title=t.title, status=t.status, due_date=t.due_date, overdue=t.overdue))
            overdue = [t for t in tasks if t.overdue]
            if overdue:
                attention.append(schemas.DashAttention(
                    kind="overdue", tone="red", fest_slug=fest.slug, fest_name=fest.name,
                    title=f"{len(overdue)} task{'s' if len(overdue) != 1 else ''} of yours {'are' if len(overdue) != 1 else 'is'} overdue",
                    detail=", ".join(t.title for t in overdue[:2]) + ("…" if len(overdue) > 2 else ""), tab="tasks"))

        out_fests.append(card)

    tone_order = {"red": 0, "amber": 1, "green": 2}
    attention.sort(key=lambda a: tone_order.get(a.tone, 3))
    my_tasks.sort(key=lambda t: (t.due_date is None, t.due_date or today, t.id))
    upcoming.sort(key=lambda u: u.when)
    # Live fests first, then the ones still being built
    out_fests.sort(key=lambda f: (f.status != "live", ))
    return schemas.DashboardOut(fests=out_fests, attention=attention[:MAX_ATTENTION], my_tasks=my_tasks[:MAX_TASKS], coming_up=upcoming[:MAX_UPCOMING])
