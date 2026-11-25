"""
The competition between colleges: points, standings, awards, the name auction and event results.

A contingent's points are a ledger. Its balance is the fest's starting points plus every entry for it: what it won at CL
meet tasks, what it paid for a name, what its students won in events, penalties and the committee's corrections. Nothing
is stored as a running total, so a balance can always be explained entry by entry, and undoing something is deleting its entries.

Only approved contingents take part. A contingent disqualified from the whole competition keeps its points but is left out of
the rankings and the awards.
"""

from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app import models, schemas

# The usual setup. Only a starting point: every number here is a default the committee can change, and none of it is applied
# until they ask for it (or is used as anything but a suggestion).
DEFAULT_PLACING_POINTS = [100, 60, 30]
DEFAULT_TASK_POINTS = [200, 100, 50]
USUAL_RULES = [
    # (title, description, points taken off, disqualifies)
    ("Late arrival", "Not at the venue at the time given for the event or task.", 20, False),
    ("Unsporting behaviour", "Disrespect towards other contingents, judges or the committee.", 50, False),
    ("Damage to property", "Damage to equipment or the venue.", 30, False),
    ("Use of unfair means", "Cheating, copying, or breaking the rules of an event.", 0, True),
    ("Violence or abuse", "Physical violence or serious abuse. Removes the contingent from the whole competition.", 0, True),
]
KIND_BUCKET = {"meet_task": "meet_tasks", "auction": "auction", "event_result": "event_points", "penalty": "penalties", "adjustment": "adjustments"}


# ─── settings ────────────────────────────────────────────────────────────────

def get_settings(db: Session, fest: models.Fest) -> models.CompetitionSettings:
    """The fest's competition settings, created with the usual defaults the first time they are needed."""
    row = db.query(models.CompetitionSettings).filter(models.CompetitionSettings.fest_id == fest.id).first()
    if not row:
        row = models.CompetitionSettings(fest_id=fest.id, starting_points=500, ranking_basis="total", public_leaderboard=False,
                                         default_placing_points=list(DEFAULT_PLACING_POINTS), default_task_points=list(DEFAULT_TASK_POINTS))
        db.add(row)
        db.flush()
    return row


def settings_out(row: models.CompetitionSettings) -> schemas.CompetitionSettingsOut:
    return schemas.CompetitionSettingsOut(
        starting_points=row.starting_points, ranking_basis=row.ranking_basis, public_leaderboard=bool(row.public_leaderboard),
        default_placing_points=list(row.default_placing_points or DEFAULT_PLACING_POINTS),
        default_task_points=list(row.default_task_points or DEFAULT_TASK_POINTS),
    )


def label(c: Optional[models.Contingent]) -> Optional[str]:
    """How a contingent is named in lists: its name if it has one, else its college."""
    if c is None:
        return None
    return c.name or c.college_name


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def participants(db: Session, fest_id: int) -> List[models.Contingent]:
    return db.query(models.Contingent).filter(models.Contingent.fest_id == fest_id, models.Contingent.status == "approved").order_by(models.Contingent.id).all()


# ─── disqualification ────────────────────────────────────────────────────────

def active_penalties(db: Session, fest_id: int) -> List[models.ContingentPenalty]:
    return db.query(models.ContingentPenalty).filter(models.ContingentPenalty.fest_id == fest_id, models.ContingentPenalty.revoked_at.is_(None)).all()


def disqualified_everywhere(penalties: List[models.ContingentPenalty]) -> set:
    return {p.contingent_id for p in penalties if p.disqualified and p.event_id is None}


def disqualified_from(penalties: List[models.ContingentPenalty], event_id: int) -> set:
    return {p.contingent_id for p in penalties if p.disqualified and p.event_id == event_id}


# ─── balances and standings ──────────────────────────────────────────────────

def breakdowns(db: Session, fest_id: int) -> Dict[int, schemas.Breakdown]:
    rows = db.query(models.PointsEntry.contingent_id, models.PointsEntry.kind, models.PointsEntry.points).filter(models.PointsEntry.fest_id == fest_id).all()
    out: Dict[int, schemas.Breakdown] = {}
    for contingent_id, kind, points in rows:
        b = out.setdefault(contingent_id, schemas.Breakdown())
        bucket = KIND_BUCKET.get(kind, "adjustments")
        setattr(b, bucket, getattr(b, bucket) + points)
    return out


def balance_of(db: Session, fest: models.Fest, contingent_id: int) -> int:
    start = get_settings(db, fest).starting_points
    total = sum(p for (p,) in db.query(models.PointsEntry.points).filter(models.PointsEntry.fest_id == fest.id, models.PointsEntry.contingent_id == contingent_id).all())
    return start + total


def _rank(items: List[Tuple[object, int]]) -> Dict[object, int]:
    """Competition ranking: equal scores share a rank and the next one skips (1, 1, 3)."""
    ranks, last_score, last_rank = {}, None, 0
    for i, (key, score) in enumerate(sorted(items, key=lambda t: -t[1]), start=1):
        if score != last_score:
            last_rank, last_score = i, score
        ranks[key] = last_rank
    return ranks


def standings(db: Session, fest: models.Fest) -> Tuple[List[schemas.ContingentStanding], List[schemas.CollegeStanding]]:
    settings = get_settings(db, fest)
    contingents = participants(db, fest.id)
    out = breakdowns(db, fest.id)
    penalties = active_penalties(db, fest.id)
    out_of = disqualified_everywhere(penalties)

    rows: List[schemas.ContingentStanding] = []
    for c in contingents:
        b = out.get(c.id, schemas.Breakdown())
        balance = settings.starting_points + b.meet_tasks + b.auction + b.event_points + b.penalties + b.adjustments
        score = balance if settings.ranking_basis == "total" else b.event_points + b.penalties
        rows.append(schemas.ContingentStanding(
            contingent_id=c.id, name=c.name, code=c.code, college_name=c.college_name, score=score, balance=balance,
            starting_points=settings.starting_points, breakdown=b, disqualified=c.id in out_of,
        ))
    ranked = [r for r in rows if not r.disqualified]
    ranks = _rank([(r.contingent_id, r.score) for r in ranked])
    for r in ranked:
        r.rank = ranks[r.contingent_id]
    rows.sort(key=lambda r: (r.disqualified, r.rank or 10**6, (r.name or r.college_name).lower()))

    # Colleges: every contingent of a college counts toward it
    groups: Dict[str, dict] = {}
    by_id = {c.id: c for c in contingents}
    for r in ranked:
        c = by_id[r.contingent_id]
        key = f"id:{c.college_id}" if c.college_id else f"name:{c.college_name.strip().lower()}"
        g = groups.setdefault(key, {"college_name": c.college_name, "score": 0, "names": []})
        g["score"] += r.score
        g["names"].append(r.name or r.college_name)
    college_ranks = _rank([(k, g["score"]) for k, g in groups.items()])
    colleges = [schemas.CollegeStanding(college_name=g["college_name"], rank=college_ranks[k], score=g["score"], contingents=len(g["names"]), contingent_names=g["names"]) for k, g in groups.items()]
    colleges.sort(key=lambda c: (c.rank or 10**6, c.college_name.lower()))
    return rows, colleges


# ─── awards ──────────────────────────────────────────────────────────────────

def award_out(db: Session, award: models.Award, contingent_rows: List[schemas.ContingentStanding], colleges: List[schemas.CollegeStanding]) -> schemas.AwardOut:
    winners: List[schemas.AwardWinner] = []
    if award.basis == "college":
        winners = [schemas.AwardWinner(name=c.college_name, college_name=c.college_name) for c in colleges if c.rank == award.rank]
    elif award.basis == "contingent":
        winners = [schemas.AwardWinner(contingent_id=r.contingent_id, name=r.name or r.college_name, college_name=r.college_name) for r in contingent_rows if r.rank == award.rank]
    elif award.basis == "event" and award.event_id:
        out = disqualified_everywhere(active_penalties(db, award.fest_id)) | disqualified_from(active_penalties(db, award.fest_id), award.event_id)
        for res in db.query(models.EventResult).filter(models.EventResult.event_id == award.event_id, models.EventResult.place == award.rank).all():
            if res.contingent_id not in out and res.contingent.status == "approved":
                winners.append(schemas.AwardWinner(contingent_id=res.contingent_id, name=label(res.contingent), college_name=res.contingent.college_name))
    elif award.basis == "custom" and award.winner:
        winners = [schemas.AwardWinner(contingent_id=award.winner.id, name=label(award.winner), college_name=award.winner.college_name)]
    event = db.query(models.Event).filter(models.Event.id == award.event_id).first() if award.event_id else None
    return schemas.AwardOut(id=award.id, title=award.title, basis=award.basis, rank=award.rank, event_id=award.event_id, event_title=event.title if event else None,
                            winner_contingent_id=award.winner_contingent_id, winners=winners)


def all_awards(db: Session, fest: models.Fest) -> List[schemas.AwardOut]:
    rows, colleges = standings(db, fest)
    awards = db.query(models.Award).filter(models.Award.fest_id == fest.id).order_by(models.Award.position, models.Award.id).all()
    return [award_out(db, a, rows, colleges) for a in awards]


# ─── event results become points ─────────────────────────────────────────────

def rebuild_event_entries(db: Session, event: models.Event, user_id: Optional[int] = None) -> None:
    """
    Make the points entries for an event match its results: one entry per placed contingent, worth what the event's points say
    for that place, except for contingents disqualified from this event or from the whole competition. Run after the results
    change and after a penalty is applied or lifted, so an appeal that succeeds puts the points straight back.
    """
    db.query(models.PointsEntry).filter(models.PointsEntry.event_id == event.id, models.PointsEntry.kind == "event_result").delete(synchronize_session=False)
    scheme = event.points_scheme or {}
    penalties = active_penalties(db, event.fest_id)
    out = disqualified_everywhere(penalties) | disqualified_from(penalties, event.id)
    for res in db.query(models.EventResult).filter(models.EventResult.event_id == event.id).all():
        pts = int(scheme.get(str(res.place), 0))
        if pts and res.contingent_id not in out:
            db.add(models.PointsEntry(fest_id=event.fest_id, contingent_id=res.contingent_id, points=pts, kind="event_result", event_id=event.id,
                                      reason=f"{event.title}: {ordinal(res.place)} place", created_by_id=user_id))


# ─── the name auction ────────────────────────────────────────────────────────

def decide_auction(db: Session, auction: models.NameAuction, fest: models.Fest) -> List[Tuple[models.AuctionName, models.Contingent, int]]:
    """
    Who wins which name. Take the highest bid of all (the earlier bidder wins a tie), give that contingent that name, and take both
    out of the running; repeat. So a contingent wins at most one name even if it bid the most on several, and the next best bidder
    takes the others. A bid the contingent can no longer afford, or from one that is not taking part, does not count.
    """
    penalties = active_penalties(db, fest.id)
    out = disqualified_everywhere(penalties)
    approved = {c.id: c for c in participants(db, fest.id)}
    balances: Dict[int, int] = {cid: balance_of(db, fest, cid) for cid in approved}
    bids = []
    for name in auction.names:
        for b in name.bids:
            if b.contingent_id in approved and b.contingent_id not in out and b.amount >= auction.min_bid and b.amount <= balances[b.contingent_id]:
                bids.append((name, b))
    bids.sort(key=lambda t: (-t[1].amount, t[1].created_at, t[1].id))
    taken_names, taken_contingents, result = set(), set(), []
    for name, b in bids:
        if name.id in taken_names or b.contingent_id in taken_contingents:
            continue
        taken_names.add(name.id)
        taken_contingents.add(b.contingent_id)
        result.append((name, approved[b.contingent_id], b.amount))
    return result
