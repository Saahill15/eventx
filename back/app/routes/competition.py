"""
The competition between colleges: standings, points, event results, rules and penalties, awards, and a leader's own view.

  GET    /api/fests/{slug}/competition/settings              the fest's scoring rules (director and core team)
  PUT    /api/fests/{slug}/competition/settings              change them
  GET    /api/fests/{slug}/competition/leaderboard           standings and awards (public once the committee says so)
  GET    /api/fests/{slug}/competition/ledger                every points entry (committee), optionally for one contingent
  POST   /api/fests/{slug}/competition/adjustments           add or take off points by hand, with a reason (committee)
  GET    /api/fests/{slug}/competition/events                every event with its points and results (committee)
  PUT    /api/fests/{slug}/competition/events/{id}/results   record who placed where; points follow
  GET|POST|PATCH|DELETE .../competition/rules                the rules and what breaking them costs
  GET|POST .../competition/penalties, DELETE .../{id}        apply a penalty, or lift it after an appeal
  GET|POST|PATCH|DELETE .../competition/awards               the fest's prizes (plus POST .../awards/usual for the usual ones)
  GET    /api/fests/{slug}/competition/mine                  a contingent leader's own points, meets, auctions and penalties
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import competition as comp
from app import models, schemas
from app.auth.dependencies import get_current_user, get_optional_user
from app.database import get_db
from app.permissions import can_view_fest, is_fest_staff

router = APIRouter()
MAX_RULES, MAX_AWARDS = 100, 40


# ─── helpers ──────────────────────────────────────────────────────────────────

def _fest(db: Session, slug: str) -> models.Fest:
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not fest:
        raise HTTPException(status_code=404, detail="Fest not found")
    return fest


def _staff(db: Session, fest: models.Fest, user) -> None:
    if not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can do that")


def _contingent(db: Session, fest: models.Fest, contingent_id: int, approved_only: bool = True) -> models.Contingent:
    c = db.query(models.Contingent).filter(models.Contingent.id == contingent_id, models.Contingent.fest_id == fest.id).first()
    if not c or (approved_only and c.status != "approved"):
        raise HTTPException(status_code=400, detail="That contingent is not taking part in this fest")
    return c


def _event(db: Session, fest: models.Fest, event_id: int) -> models.Event:
    e = db.query(models.Event).filter(models.Event.id == event_id, models.Event.fest_id == fest.id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Event not found in this fest")
    return e


def my_contingent_of(db: Session, fest: models.Fest, user) -> Optional[models.Contingent]:
    rows = db.query(models.Contingent).filter(models.Contingent.fest_id == fest.id, models.Contingent.status == "approved").order_by(models.Contingent.id).all()
    for c in rows:
        if c.leader_user_id == user.id or any(a.user_id == user.id for a in c.assistants):
            return c
    return None


def entry_out(e: models.PointsEntry) -> schemas.PointsEntryOut:
    return schemas.PointsEntryOut(id=e.id, contingent_id=e.contingent_id, contingent_label=comp.label(e.contingent), points=e.points, kind=e.kind, reason=e.reason, created_at=e.created_at)


# ─── settings ─────────────────────────────────────────────────────────────────

@router.get("/{slug}/competition/settings", response_model=schemas.CompetitionSettingsOut)
def get_settings(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    out = comp.settings_out(comp.get_settings(db, fest))
    db.commit()
    return out


@router.put("/{slug}/competition/settings", response_model=schemas.CompetitionSettingsOut)
def update_settings(slug: str, data: schemas.CompetitionSettingsIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    row = comp.get_settings(db, fest)
    updates = data.model_dump(exclude_unset=True)
    for field in ("starting_points", "ranking_basis", "public_leaderboard"):
        if updates.get(field) is not None:
            setattr(row, field, updates[field])
    if updates.get("default_placing_points") is not None:
        row.default_placing_points = updates["default_placing_points"]
    if updates.get("default_task_points") is not None:
        row.default_task_points = updates["default_task_points"]
    db.commit()
    return comp.settings_out(row)


# ─── leaderboard ──────────────────────────────────────────────────────────────

@router.get("/{slug}/competition/leaderboard", response_model=schemas.LeaderboardOut)
def leaderboard(slug: str, db: Session = Depends(get_db), user=Depends(get_optional_user)):
    fest = _fest(db, slug)
    if not can_view_fest(db, fest, user):
        raise HTTPException(status_code=404, detail="Fest not found")
    settings = comp.get_settings(db, fest)
    if not settings.public_leaderboard and not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="The leaderboard is not public yet")
    rows, colleges = comp.standings(db, fest)
    awards = comp.all_awards(db, fest)
    db.commit()
    return schemas.LeaderboardOut(ranking_basis=settings.ranking_basis, contingents=rows, colleges=colleges, awards=awards)


# ─── ledger ───────────────────────────────────────────────────────────────────

@router.get("/{slug}/competition/ledger", response_model=List[schemas.PointsEntryOut])
def ledger(slug: str, contingent_id: Optional[int] = None, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    q = db.query(models.PointsEntry).filter(models.PointsEntry.fest_id == fest.id)
    if contingent_id is not None:
        q = q.filter(models.PointsEntry.contingent_id == contingent_id)
    return [entry_out(e) for e in q.order_by(models.PointsEntry.created_at.desc(), models.PointsEntry.id.desc()).limit(500).all()]


@router.post("/{slug}/competition/adjustments", response_model=schemas.PointsEntryOut, status_code=status.HTTP_201_CREATED)
def adjust(slug: str, data: schemas.AdjustIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    c = _contingent(db, fest, data.contingent_id)
    entry = models.PointsEntry(fest_id=fest.id, contingent_id=c.id, points=data.points, kind="adjustment", reason=data.reason, created_by_id=user.id)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry_out(entry)


# ─── event results ────────────────────────────────────────────────────────────

def _results_out(db: Session, event: models.Event) -> schemas.EventResultsOut:
    scheme = event.points_scheme or {}
    penalties = comp.active_penalties(db, event.fest_id)
    out = comp.disqualified_everywhere(penalties) | comp.disqualified_from(penalties, event.id)
    rows = db.query(models.EventResult).filter(models.EventResult.event_id == event.id).order_by(models.EventResult.place, models.EventResult.id).all()
    return schemas.EventResultsOut(
        event_id=event.id, title=event.title, points_scheme=event.points_scheme,
        results=[schemas.EventResultOut(contingent_id=r.contingent_id, contingent_label=comp.label(r.contingent), place=r.place,
                                        points=0 if r.contingent_id in out else int(scheme.get(str(r.place), 0)), note=r.note, disqualified=r.contingent_id in out) for r in rows],
    )


@router.get("/{slug}/competition/events", response_model=List[schemas.EventResultsOut])
def scored_events(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    events = db.query(models.Event).filter(models.Event.fest_id == fest.id, models.Event.points_scheme.isnot(None)).order_by(models.Event.date, models.Event.id).all()
    return [_results_out(db, e) for e in events]


@router.put("/{slug}/competition/events/{event_id}/results", response_model=schemas.EventResultsOut)
def record_results(slug: str, event_id: int, data: schemas.EventResultsIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """The whole result of an event, replacing what was there. Points follow the event's points for each place."""
    fest = _fest(db, slug)
    _staff(db, fest, user)
    event = _event(db, fest, event_id)
    if not event.points_scheme:
        raise HTTPException(status_code=400, detail="This event is not scored. Set its points first.")
    seen = set()
    for r in data.results:
        if r.contingent_id in seen:
            raise HTTPException(status_code=400, detail="A contingent can only appear once in a result")
        seen.add(r.contingent_id)
        _contingent(db, fest, r.contingent_id)
    db.query(models.EventResult).filter(models.EventResult.event_id == event.id).delete(synchronize_session=False)
    for r in data.results:
        db.add(models.EventResult(event_id=event.id, contingent_id=r.contingent_id, place=r.place, note=r.note))
    db.flush()
    comp.rebuild_event_entries(db, event, user.id)
    db.commit()
    return _results_out(db, event)


# ─── rules ────────────────────────────────────────────────────────────────────

def _rule_out(db: Session, r: models.CompetitionRule) -> schemas.RuleOut:
    event = db.query(models.Event).filter(models.Event.id == r.event_id).first() if r.event_id else None
    return schemas.RuleOut(id=r.id, event_id=r.event_id, event_title=event.title if event else None, title=r.title, description=r.description, penalty_points=r.penalty_points, disqualifies=bool(r.disqualifies))


@router.post("/{slug}/competition/rules/usual", response_model=List[schemas.RuleOut], status_code=status.HTTP_201_CREATED)
def add_usual_rules(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """
    A usual set of rules to start from (late arrival, unsporting behaviour, damage, unfair means, violence). Nothing about them is fixed:
    every one can be edited or deleted, and the points are only suggestions. Ones the fest already has (same title) are skipped.
    """
    fest = _fest(db, slug)
    _staff(db, fest, user)
    have = {r.title.lower() for r in db.query(models.CompetitionRule).filter(models.CompetitionRule.fest_id == fest.id).all()}
    count = db.query(models.CompetitionRule).filter(models.CompetitionRule.fest_id == fest.id).count()
    for title, description, points, disqualifies in comp.USUAL_RULES:
        if title.lower() not in have and count < MAX_RULES:
            db.add(models.CompetitionRule(fest_id=fest.id, title=title, description=description, penalty_points=points, disqualifies=disqualifies))
            count += 1
    db.commit()
    return [_rule_out(db, r) for r in db.query(models.CompetitionRule).filter(models.CompetitionRule.fest_id == fest.id).order_by(models.CompetitionRule.id).all()]


@router.get("/{slug}/competition/rules", response_model=List[schemas.RuleOut])
def list_rules(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    return [_rule_out(db, r) for r in db.query(models.CompetitionRule).filter(models.CompetitionRule.fest_id == fest.id).order_by(models.CompetitionRule.id).all()]


@router.post("/{slug}/competition/rules", response_model=schemas.RuleOut, status_code=status.HTTP_201_CREATED)
def add_rule(slug: str, data: schemas.RuleIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    if db.query(models.CompetitionRule).filter(models.CompetitionRule.fest_id == fest.id).count() >= MAX_RULES:
        raise HTTPException(status_code=400, detail=f"A fest can have at most {MAX_RULES} rules")
    if data.event_id is not None:
        _event(db, fest, data.event_id)
    row = models.CompetitionRule(fest_id=fest.id, event_id=data.event_id, title=data.title, description=data.description or None, penalty_points=data.penalty_points, disqualifies=data.disqualifies)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _rule_out(db, row)


def _rule(db: Session, fest: models.Fest, rule_id: int) -> models.CompetitionRule:
    row = db.query(models.CompetitionRule).filter(models.CompetitionRule.id == rule_id, models.CompetitionRule.fest_id == fest.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Rule not found")
    return row


@router.patch("/{slug}/competition/rules/{rule_id}", response_model=schemas.RuleOut)
def update_rule(slug: str, rule_id: int, data: schemas.RuleUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    row = _rule(db, fest, rule_id)
    updates = data.model_dump(exclude_unset=True)
    if "event_id" in updates and updates["event_id"] is not None:
        _event(db, fest, updates["event_id"])
    for field in ("title", "penalty_points", "disqualifies", "event_id"):
        if field in updates and (field == "event_id" or updates[field] is not None):
            setattr(row, field, updates[field])
    if "description" in updates:
        row.description = updates["description"] or None
    db.commit()
    return _rule_out(db, row)


@router.delete("/{slug}/competition/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(slug: str, rule_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    row = _rule(db, fest, rule_id)
    # Penalties already given stay on record; they just no longer point at a rule
    db.query(models.ContingentPenalty).filter(models.ContingentPenalty.rule_id == row.id).update({"rule_id": None}, synchronize_session=False)
    db.delete(row)
    db.commit()


# ─── penalties ────────────────────────────────────────────────────────────────

def penalty_out(db: Session, p: models.ContingentPenalty) -> schemas.PenaltyOut:
    event = db.query(models.Event).filter(models.Event.id == p.event_id).first() if p.event_id else None
    return schemas.PenaltyOut(id=p.id, contingent_id=p.contingent_id, contingent_label=comp.label(p.contingent), rule_id=p.rule_id, rule_title=p.rule.title if p.rule else None,
                              event_id=p.event_id, event_title=event.title if event else None, points=p.points, disqualified=bool(p.disqualified), reason=p.reason,
                              created_at=p.created_at, revoked=p.revoked_at is not None)


@router.get("/{slug}/competition/penalties", response_model=List[schemas.PenaltyOut])
def list_penalties(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    rows = db.query(models.ContingentPenalty).filter(models.ContingentPenalty.fest_id == fest.id).order_by(models.ContingentPenalty.created_at.desc(), models.ContingentPenalty.id.desc()).all()
    return [penalty_out(db, p) for p in rows]


@router.post("/{slug}/competition/penalties", response_model=schemas.PenaltyOut, status_code=status.HTTP_201_CREATED)
def apply_penalty(slug: str, data: schemas.PenaltyIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Take points off a contingent and/or disqualify it, from one event or from the whole competition. A rule fills in the usual amounts."""
    fest = _fest(db, slug)
    _staff(db, fest, user)
    c = _contingent(db, fest, data.contingent_id)
    rule = _rule(db, fest, data.rule_id) if data.rule_id is not None else None
    event_id = data.event_id if data.event_id is not None else (rule.event_id if rule else None)
    event = _event(db, fest, event_id) if event_id is not None else None
    points = data.points if data.points is not None else (rule.penalty_points if rule else 0)
    disqualified = data.disqualified if data.disqualified is not None else (bool(rule.disqualifies) if rule else False)
    reason = data.reason or (rule.title if rule else "")
    if not reason:
        raise HTTPException(status_code=400, detail="Say why: a penalty needs a reason, or a rule to point at")
    if points == 0 and not disqualified:
        raise HTTPException(status_code=400, detail="A penalty takes off points, disqualifies, or both")
    p = models.ContingentPenalty(fest_id=fest.id, contingent_id=c.id, rule_id=rule.id if rule else None, event_id=event_id, points=points, disqualified=disqualified, reason=reason, created_by_id=user.id)
    db.add(p)
    db.flush()
    if points:
        where = f" ({event.title})" if event else ""
        db.add(models.PointsEntry(fest_id=fest.id, contingent_id=c.id, points=-points, kind="penalty", reason=f"Penalty{where}: {reason}"[:300], penalty_id=p.id, event_id=None, created_by_id=user.id))
    db.flush()
    _refresh_results_after_penalty(db, fest, event, user.id)
    db.commit()
    db.refresh(p)
    return penalty_out(db, p)


def _refresh_results_after_penalty(db: Session, fest: models.Fest, event: Optional[models.Event], user_id: int) -> None:
    """A disqualification changes whose event points count: from one event, or from all of them."""
    events = [event] if event else db.query(models.Event).filter(models.Event.fest_id == fest.id, models.Event.points_scheme.isnot(None)).all()
    for e in events:
        comp.rebuild_event_entries(db, e, user_id)


@router.delete("/{slug}/competition/penalties/{penalty_id}", response_model=schemas.PenaltyOut)
def lift_penalty(slug: str, penalty_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """An appeal succeeded: the penalty stops counting, its points come back, and a disqualified result counts again."""
    fest = _fest(db, slug)
    _staff(db, fest, user)
    p = db.query(models.ContingentPenalty).filter(models.ContingentPenalty.id == penalty_id, models.ContingentPenalty.fest_id == fest.id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Penalty not found")
    if p.revoked_at is not None:
        raise HTTPException(status_code=400, detail="This penalty was already lifted")
    from datetime import datetime
    p.revoked_at = datetime.utcnow()
    db.query(models.PointsEntry).filter(models.PointsEntry.penalty_id == p.id).delete(synchronize_session=False)
    db.flush()
    event = db.query(models.Event).filter(models.Event.id == p.event_id).first() if p.event_id else None
    if p.disqualified:
        _refresh_results_after_penalty(db, fest, event, user.id)
    db.commit()
    return penalty_out(db, p)


# ─── awards ───────────────────────────────────────────────────────────────────

USUAL_AWARDS = [("Best College", "college", 1), ("Runner-up College", "college", 2), ("Third Place College", "college", 3)]


def _award(db: Session, fest: models.Fest, award_id: int) -> models.Award:
    row = db.query(models.Award).filter(models.Award.id == award_id, models.Award.fest_id == fest.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Award not found")
    return row


@router.get("/{slug}/competition/awards", response_model=List[schemas.AwardOut])
def list_awards(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    return comp.all_awards(db, fest)


@router.post("/{slug}/competition/awards", response_model=schemas.AwardOut, status_code=status.HTTP_201_CREATED)
def add_award(slug: str, data: schemas.AwardIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    if db.query(models.Award).filter(models.Award.fest_id == fest.id).count() >= MAX_AWARDS:
        raise HTTPException(status_code=400, detail=f"A fest can have at most {MAX_AWARDS} awards")
    if data.event_id is not None:
        _event(db, fest, data.event_id)
    if data.winner_contingent_id is not None:
        _contingent(db, fest, data.winner_contingent_id)
    last = db.query(models.Award).filter(models.Award.fest_id == fest.id).count()
    row = models.Award(fest_id=fest.id, title=data.title, basis=data.basis, rank=data.rank, event_id=data.event_id, winner_contingent_id=data.winner_contingent_id, position=last)
    db.add(row)
    db.commit()
    db.refresh(row)
    rows, colleges = comp.standings(db, fest)
    return comp.award_out(db, row, rows, colleges)


@router.post("/{slug}/competition/awards/usual", response_model=List[schemas.AwardOut], status_code=status.HTTP_201_CREATED)
def add_usual_awards(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Best college, runner-up and third place. Ones the fest already has (same title) are skipped, so it is safe to press twice."""
    fest = _fest(db, slug)
    _staff(db, fest, user)
    have = {a.title.lower() for a in db.query(models.Award).filter(models.Award.fest_id == fest.id).all()}
    n = db.query(models.Award).filter(models.Award.fest_id == fest.id).count()
    for title, basis, rank in USUAL_AWARDS:
        if title.lower() not in have:
            db.add(models.Award(fest_id=fest.id, title=title, basis=basis, rank=rank, position=n))
            n += 1
    db.commit()
    return comp.all_awards(db, fest)


@router.patch("/{slug}/competition/awards/{award_id}", response_model=schemas.AwardOut)
def update_award(slug: str, award_id: int, data: schemas.AwardUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    row = _award(db, fest, award_id)
    updates = data.model_dump(exclude_unset=True)
    if updates.get("title") is not None:
        row.title = updates["title"]
    if updates.get("rank") is not None:
        row.rank = updates["rank"]
    if "event_id" in updates and row.basis == "event":
        if updates["event_id"] is None:
            raise HTTPException(status_code=400, detail="Choose the event for this award")
        _event(db, fest, updates["event_id"])
        row.event_id = updates["event_id"]
    if "winner_contingent_id" in updates and row.basis == "custom":
        if updates["winner_contingent_id"] is not None:
            _contingent(db, fest, updates["winner_contingent_id"])
        row.winner_contingent_id = updates["winner_contingent_id"]
    db.commit()
    db.refresh(row)
    rows, colleges = comp.standings(db, fest)
    return comp.award_out(db, row, rows, colleges)


@router.delete("/{slug}/competition/awards/{award_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_award(slug: str, award_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    db.delete(_award(db, fest, award_id))
    db.commit()


# ─── a contingent leader's own view ───────────────────────────────────────────

@router.get("/{slug}/competition/mine", response_model=Optional[schemas.CompetitionMine])
def my_competition(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    c = my_contingent_of(db, fest, user)
    if not c:
        return None
    settings = comp.get_settings(db, fest)
    rows, _ = comp.standings(db, fest)
    me = next((r for r in rows if r.contingent_id == c.id), None)
    entries = db.query(models.PointsEntry).filter(models.PointsEntry.fest_id == fest.id, models.PointsEntry.contingent_id == c.id).order_by(models.PointsEntry.created_at.desc(), models.PointsEntry.id.desc()).all()
    penalties = db.query(models.ContingentPenalty).filter(models.ContingentPenalty.contingent_id == c.id).order_by(models.ContingentPenalty.created_at.desc()).all()

    from app.routes.cl_meets import my_auctions, my_meets  # the meets and auctions have their own rules about what a leader may see
    placed = []
    for res in db.query(models.EventResult).filter(models.EventResult.contingent_id == c.id).all():
        e = db.query(models.Event).filter(models.Event.id == res.event_id).first()
        if e and e.fest_id == fest.id:
            out = comp.disqualified_everywhere(comp.active_penalties(db, fest.id)) | comp.disqualified_from(comp.active_penalties(db, fest.id), e.id)
            placed.append(schemas.EventResultOut(contingent_id=c.id, contingent_label=e.title, place=res.place, points=0 if c.id in out else int((e.points_scheme or {}).get(str(res.place), 0)), note=res.note, disqualified=c.id in out))
    db.commit()
    return schemas.CompetitionMine(
        contingent_id=c.id, name=c.name, code=c.code, college_name=c.college_name, balance=me.balance if me else settings.starting_points,
        starting_points=settings.starting_points, breakdown=me.breakdown if me else schemas.Breakdown(), rank=me.rank if (me and settings.public_leaderboard) else None,
        disqualified=bool(me and me.disqualified), ledger=[entry_out(e) for e in entries], penalties=[penalty_out(db, p) for p in penalties if p.revoked_at is None],
        meets=my_meets(db, fest, c), auctions=my_auctions(db, fest, c), events=placed,
    )
