"""
CL meets and the name auction.

A CL meet is a meeting of the contingent leaders before the fest. The committee runs tasks there; contingents that do well earn
points. At the end the committee auctions the names (and codes) it has chosen: contingents bid points, the highest bid wins the
name and only that winning bid is paid.

  GET|POST   /api/fests/{slug}/cl-meets                                   the meets (committee); schedule one
  PATCH|DELETE .../cl-meets/{id}                                          change or remove a meet (its points go with it)
  PUT        .../cl-meets/{id}/attendance                                 which contingents came
  POST       .../cl-meets/{id}/tasks                                      add a task; PATCH|DELETE .../tasks/{task_id}
  PUT        .../cl-meets/{id}/tasks/{task_id}/result                     award points for a task (replaces earlier awards for it)
  GET|POST   .../auctions                                                 the name auctions; make one
  PATCH|DELETE .../auctions/{id}                                          change or remove one
  POST       .../auctions/{id}/names | DELETE .../names/{name_id}         the names up for bidding
  POST       .../auctions/{id}/open | /close | /reopen                    run it; close pays the winning bids and sets the names; reopen undoes that
  PUT|DELETE .../auctions/{id}/names/{name_id}/bid                        bid (a leader for their own contingent, the committee for anyone)
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import competition as comp
from app import models, schemas
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.permissions import is_fest_staff
from app.routes.competition import _contingent, _fest, _staff, my_contingent_of

router = APIRouter()
MAX_MEETS, MAX_TASKS_PER_MEET, MAX_AUCTIONS, MAX_NAMES = 50, 50, 20, 100


# ─── builders ─────────────────────────────────────────────────────────────────

def task_out(db: Session, task: models.ClMeetTask, only: Optional[int] = None) -> schemas.ClMeetTaskOut:
    q = db.query(models.PointsEntry).filter(models.PointsEntry.meet_task_id == task.id)
    if only is not None:
        q = q.filter(models.PointsEntry.contingent_id == only)
    results = [schemas.TaskResultOut(contingent_id=e.contingent_id, contingent_label=comp.label(e.contingent), points=e.points) for e in q.order_by(models.PointsEntry.points.desc(), models.PointsEntry.id).all()]
    return schemas.ClMeetTaskOut(id=task.id, meet_id=task.meet_id, title=task.title, description=task.description, position=task.position, placing_points=task.placing_points, results=results)


def meet_out(db: Session, meet: models.ClMeet) -> schemas.ClMeetOut:
    return schemas.ClMeetOut(id=meet.id, fest_id=meet.fest_id, title=meet.title, starts_at=meet.starts_at, location=meet.location, notes=meet.notes,
                             tasks=[task_out(db, t) for t in meet.tasks], attended=sorted(a.contingent_id for a in meet.attendance))


def auction_out(db: Session, a: models.NameAuction) -> schemas.AuctionOut:
    names = []
    for n in a.names:
        bids = sorted(n.bids, key=lambda b: (-b.amount, b.created_at, b.id))
        names.append(schemas.AuctionNameOut(
            id=n.id, name=n.name, code=n.code, winner_contingent_id=n.winner_contingent_id, winner_label=comp.label(n.winner), winning_bid=n.winning_bid,
            bids=[schemas.BidOut(contingent_id=b.contingent_id, contingent_label=comp.label(b.contingent), amount=b.amount) for b in bids],
            top_bid=bids[0].amount if bids else None,
        ))
    return schemas.AuctionOut(id=a.id, fest_id=a.fest_id, meet_id=a.meet_id, title=a.title, status=a.status, min_bid=a.min_bid, show_highest_bid=bool(a.show_highest_bid), names=names)


def my_meets(db: Session, fest: models.Fest, c: models.Contingent) -> List[schemas.MyMeet]:
    """The meets as a leader sees them: what is on, and what their own contingent earned (never anyone else's)."""
    out = []
    for m in db.query(models.ClMeet).filter(models.ClMeet.fest_id == fest.id).order_by(models.ClMeet.starts_at).all():
        out.append(schemas.MyMeet(id=m.id, title=m.title, starts_at=m.starts_at, location=m.location, notes=m.notes,
                                  tasks=[task_out(db, t, only=c.id) for t in m.tasks], attended=any(a.contingent_id == c.id for a in m.attendance)))
    return out


def my_auctions(db: Session, fest: models.Fest, c: models.Contingent) -> List[schemas.MyAuction]:
    """Open and finished auctions as a leader sees them: their own bids, and the top bid only if the auction is not sealed."""
    out = []
    for a in db.query(models.NameAuction).filter(models.NameAuction.fest_id == fest.id, models.NameAuction.status.in_(["open", "closed"])).order_by(models.NameAuction.id).all():
        names = []
        for n in a.names:
            mine = next((b for b in n.bids if b.contingent_id == c.id), None)
            top = max((b.amount for b in n.bids), default=None)
            names.append(schemas.MyAuctionName(
                id=n.id, name=n.name, code=n.code, my_bid=mine.amount if mine else None,
                top_bid=top if (a.show_highest_bid or a.status == "closed") else None,
                winner_label=comp.label(n.winner) if a.status == "closed" else None, i_won=n.winner_contingent_id == c.id,
            ))
        out.append(schemas.MyAuction(id=a.id, title=a.title, status=a.status, min_bid=a.min_bid, show_highest_bid=bool(a.show_highest_bid), names=names))
    return out


# ─── lookups ──────────────────────────────────────────────────────────────────

def _meet(db: Session, fest: models.Fest, meet_id: int) -> models.ClMeet:
    m = db.query(models.ClMeet).filter(models.ClMeet.id == meet_id, models.ClMeet.fest_id == fest.id).first()
    if not m:
        raise HTTPException(status_code=404, detail="CL meet not found")
    return m


def _task(db: Session, meet: models.ClMeet, task_id: int) -> models.ClMeetTask:
    t = db.query(models.ClMeetTask).filter(models.ClMeetTask.id == task_id, models.ClMeetTask.meet_id == meet.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    return t


def _auction(db: Session, fest: models.Fest, auction_id: int) -> models.NameAuction:
    a = db.query(models.NameAuction).filter(models.NameAuction.id == auction_id, models.NameAuction.fest_id == fest.id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Auction not found")
    return a


def _name(a: models.NameAuction, name_id: int) -> models.AuctionName:
    n = next((x for x in a.names if x.id == name_id), None)
    if not n:
        raise HTTPException(status_code=404, detail="Name not found in this auction")
    return n


# ─── meets ────────────────────────────────────────────────────────────────────

@router.get("/{slug}/cl-meets", response_model=List[schemas.ClMeetOut])
def list_meets(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    return [meet_out(db, m) for m in db.query(models.ClMeet).filter(models.ClMeet.fest_id == fest.id).order_by(models.ClMeet.starts_at).all()]


@router.post("/{slug}/cl-meets", response_model=schemas.ClMeetOut, status_code=status.HTTP_201_CREATED)
def add_meet(slug: str, data: schemas.ClMeetIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    if db.query(models.ClMeet).filter(models.ClMeet.fest_id == fest.id).count() >= MAX_MEETS:
        raise HTTPException(status_code=400, detail=f"A fest can have at most {MAX_MEETS} CL meets")
    m = models.ClMeet(fest_id=fest.id, title=data.title, starts_at=data.starts_at, location=data.location or None, notes=data.notes or None, created_by_id=user.id)
    db.add(m)
    db.commit()
    db.refresh(m)
    return meet_out(db, m)


@router.patch("/{slug}/cl-meets/{meet_id}", response_model=schemas.ClMeetOut)
def update_meet(slug: str, meet_id: int, data: schemas.ClMeetUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    m = _meet(db, fest, meet_id)
    updates = data.model_dump(exclude_unset=True)
    if updates.get("title") is not None:
        m.title = updates["title"]
    if updates.get("starts_at") is not None:
        m.starts_at = updates["starts_at"]
    for field in ("location", "notes"):
        if field in updates:
            setattr(m, field, updates[field] or None)
    db.commit()
    return meet_out(db, m)


@router.delete("/{slug}/cl-meets/{meet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meet(slug: str, meet_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Removing a meet removes its tasks, and the points they gave out come off again."""
    fest = _fest(db, slug)
    _staff(db, fest, user)
    m = _meet(db, fest, meet_id)
    ids = [t.id for t in m.tasks]
    if ids:
        db.query(models.PointsEntry).filter(models.PointsEntry.meet_task_id.in_(ids)).delete(synchronize_session=False)
    db.query(models.NameAuction).filter(models.NameAuction.meet_id == m.id).update({"meet_id": None}, synchronize_session=False)
    db.delete(m)
    db.commit()


@router.put("/{slug}/cl-meets/{meet_id}/attendance", response_model=schemas.ClMeetOut)
def set_attendance(slug: str, meet_id: int, data: schemas.AttendanceIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    m = _meet(db, fest, meet_id)
    ids = set(data.contingent_ids)
    for cid in ids:
        _contingent(db, fest, cid)
    db.query(models.ClMeetAttendance).filter(models.ClMeetAttendance.meet_id == m.id).delete(synchronize_session=False)
    for cid in ids:
        db.add(models.ClMeetAttendance(meet_id=m.id, contingent_id=cid))
    db.commit()
    db.refresh(m)
    return meet_out(db, m)


# ─── tasks ────────────────────────────────────────────────────────────────────

@router.post("/{slug}/cl-meets/{meet_id}/tasks", response_model=schemas.ClMeetTaskOut, status_code=status.HTTP_201_CREATED)
def add_task(slug: str, meet_id: int, data: schemas.ClMeetTaskIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    m = _meet(db, fest, meet_id)
    if len(m.tasks) >= MAX_TASKS_PER_MEET:
        raise HTTPException(status_code=400, detail=f"A meet can have at most {MAX_TASKS_PER_MEET} tasks")
    t = models.ClMeetTask(meet_id=m.id, title=data.title, description=data.description or None, placing_points=data.placing_points, position=len(m.tasks))
    db.add(t)
    db.commit()
    db.refresh(t)
    return task_out(db, t)


@router.patch("/{slug}/cl-meets/{meet_id}/tasks/{task_id}", response_model=schemas.ClMeetTaskOut)
def update_task(slug: str, meet_id: int, task_id: int, data: schemas.ClMeetTaskUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    t = _task(db, _meet(db, fest, meet_id), task_id)
    updates = data.model_dump(exclude_unset=True)
    if updates.get("title") is not None:
        t.title = updates["title"]
    if "description" in updates:
        t.description = updates["description"] or None
    if "placing_points" in updates:
        t.placing_points = updates["placing_points"]
    db.commit()
    return task_out(db, t)


@router.delete("/{slug}/cl-meets/{meet_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(slug: str, meet_id: int, task_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    t = _task(db, _meet(db, fest, meet_id), task_id)
    db.query(models.PointsEntry).filter(models.PointsEntry.meet_task_id == t.id).delete(synchronize_session=False)
    db.delete(t)
    db.commit()


@router.put("/{slug}/cl-meets/{meet_id}/tasks/{task_id}/result", response_model=schemas.ClMeetTaskOut)
def task_result(slug: str, meet_id: int, task_id: int, data: schemas.TaskResultIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """What each contingent earned for a task. This replaces any earlier awards for the same task, so a mistake is fixed by sending it again."""
    fest = _fest(db, slug)
    _staff(db, fest, user)
    m = _meet(db, fest, meet_id)
    t = _task(db, m, task_id)
    seen = set()
    for a in data.awards:
        if a.contingent_id in seen:
            raise HTTPException(status_code=400, detail="A contingent can only appear once in a result")
        seen.add(a.contingent_id)
        _contingent(db, fest, a.contingent_id)
    db.query(models.PointsEntry).filter(models.PointsEntry.meet_task_id == t.id).delete(synchronize_session=False)
    for a in data.awards:
        if a.points:
            reason = f"{m.title}: {t.title}" + (f" ({a.note})" if a.note else "")
            db.add(models.PointsEntry(fest_id=fest.id, contingent_id=a.contingent_id, points=a.points, kind="meet_task", reason=reason[:300], meet_task_id=t.id, created_by_id=user.id))
    db.commit()
    return task_out(db, t)


# ─── auctions ─────────────────────────────────────────────────────────────────

@router.get("/{slug}/auctions", response_model=List[schemas.AuctionOut])
def list_auctions(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    return [auction_out(db, a) for a in db.query(models.NameAuction).filter(models.NameAuction.fest_id == fest.id).order_by(models.NameAuction.id).all()]


@router.post("/{slug}/auctions", response_model=schemas.AuctionOut, status_code=status.HTTP_201_CREATED)
def add_auction(slug: str, data: schemas.AuctionIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    if db.query(models.NameAuction).filter(models.NameAuction.fest_id == fest.id).count() >= MAX_AUCTIONS:
        raise HTTPException(status_code=400, detail=f"A fest can have at most {MAX_AUCTIONS} auctions")
    if data.meet_id is not None:
        _meet(db, fest, data.meet_id)
    a = models.NameAuction(fest_id=fest.id, meet_id=data.meet_id, title=data.title, min_bid=data.min_bid, show_highest_bid=data.show_highest_bid, status="draft")
    db.add(a)
    db.commit()
    db.refresh(a)
    return auction_out(db, a)


@router.patch("/{slug}/auctions/{auction_id}", response_model=schemas.AuctionOut)
def update_auction(slug: str, auction_id: int, data: schemas.AuctionUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    a = _auction(db, fest, auction_id)
    updates = data.model_dump(exclude_unset=True)
    if a.status == "closed" and set(updates) - {"title"}:
        raise HTTPException(status_code=400, detail="This auction is closed. Reopen it to change how it runs.")
    if updates.get("title") is not None:
        a.title = updates["title"]
    if updates.get("min_bid") is not None:
        a.min_bid = updates["min_bid"]
    if updates.get("show_highest_bid") is not None:
        a.show_highest_bid = updates["show_highest_bid"]
    if "meet_id" in updates:
        if updates["meet_id"] is not None:
            _meet(db, fest, updates["meet_id"])
        a.meet_id = updates["meet_id"]
    db.commit()
    return auction_out(db, a)


@router.delete("/{slug}/auctions/{auction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_auction(slug: str, auction_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    a = _auction(db, fest, auction_id)
    if a.status == "closed":
        raise HTTPException(status_code=400, detail="This auction is closed. Reopen it first so the points paid are given back.")
    db.delete(a)
    db.commit()


@router.post("/{slug}/auctions/{auction_id}/names", response_model=schemas.AuctionOut, status_code=status.HTTP_201_CREATED)
def add_name(slug: str, auction_id: int, data: schemas.AuctionNameIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    a = _auction(db, fest, auction_id)
    if a.status == "closed":
        raise HTTPException(status_code=400, detail="This auction is closed")
    if len(a.names) >= MAX_NAMES:
        raise HTTPException(status_code=400, detail=f"An auction can have at most {MAX_NAMES} names")
    for n in a.names:
        if n.name.lower() == data.name.lower() or (data.code and n.code and n.code.lower() == data.code.lower()):
            raise HTTPException(status_code=400, detail="That name or code is already in this auction")
    db.add(models.AuctionName(auction_id=a.id, name=data.name, code=data.code or None, position=len(a.names)))
    db.commit()
    db.refresh(a)
    return auction_out(db, a)


@router.delete("/{slug}/auctions/{auction_id}/names/{name_id}", response_model=schemas.AuctionOut)
def remove_name(slug: str, auction_id: int, name_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    a = _auction(db, fest, auction_id)
    if a.status == "closed":
        raise HTTPException(status_code=400, detail="This auction is closed")
    db.delete(_name(a, name_id))
    db.commit()
    db.refresh(a)
    return auction_out(db, a)


@router.post("/{slug}/auctions/{auction_id}/open", response_model=schemas.AuctionOut)
def open_auction(slug: str, auction_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    a = _auction(db, fest, auction_id)
    if a.status != "draft":
        raise HTTPException(status_code=400, detail="Only a draft auction can be opened")
    if not a.names:
        raise HTTPException(status_code=400, detail="Add at least one name before opening the auction")
    a.status, a.opened_at = "open", datetime.utcnow()
    db.commit()
    return auction_out(db, a)


@router.post("/{slug}/auctions/{auction_id}/close", response_model=schemas.AuctionOut)
def close_auction(slug: str, auction_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Decide the winners, take only the winning bids off their points, and give each winner its name (and code)."""
    fest = _fest(db, slug)
    _staff(db, fest, user)
    a = _auction(db, fest, auction_id)
    if a.status != "open":
        raise HTTPException(status_code=400, detail="Only an open auction can be closed")
    winners = comp.decide_auction(db, a, fest)
    # A name or code already worn by another contingent cannot be handed out a second time
    others = db.query(models.Contingent).filter(models.Contingent.fest_id == fest.id).all()
    for name, c, _amount in winners:
        for o in others:
            if o.id == c.id:
                continue
            if (o.name and o.name.lower() == name.name.lower()) or (name.code and o.code and o.code.lower() == name.code.lower()):
                raise HTTPException(status_code=400, detail=f"“{name.name}” is already used by {comp.label(o)}. Rename one of them first.")
    for name, c, amount in winners:
        name.winner_contingent_id, name.winning_bid = c.id, amount
        c.name = name.name
        if name.code:
            c.code = name.code
        db.add(models.PointsEntry(fest_id=fest.id, contingent_id=c.id, points=-amount, kind="auction", reason=f"Won the name “{name.name}” ({a.title})"[:300], auction_name_id=name.id, created_by_id=user.id))
    a.status, a.closed_at = "closed", datetime.utcnow()
    db.commit()
    db.refresh(a)
    return auction_out(db, a)


@router.post("/{slug}/auctions/{auction_id}/reopen", response_model=schemas.AuctionOut)
def reopen_auction(slug: str, auction_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Undo a close: the points paid come back, the names are taken off the contingents, and bidding is open again."""
    fest = _fest(db, slug)
    _staff(db, fest, user)
    a = _auction(db, fest, auction_id)
    if a.status != "closed":
        raise HTTPException(status_code=400, detail="Only a closed auction can be reopened")
    for n in a.names:
        db.query(models.PointsEntry).filter(models.PointsEntry.auction_name_id == n.id).delete(synchronize_session=False)
        if n.winner:
            if n.winner.name == n.name:
                n.winner.name = None
            if n.code and n.winner.code == n.code:
                n.winner.code = None
        n.winner_contingent_id = n.winning_bid = None
    a.status, a.closed_at = "open", None
    db.commit()
    db.refresh(a)
    return auction_out(db, a)


# ─── bids ─────────────────────────────────────────────────────────────────────

def _bidder(db: Session, fest: models.Fest, user, contingent_id: Optional[int]) -> models.Contingent:
    """Who the bid is for. A leader bids for their own contingent; the committee names the contingent."""
    mine = my_contingent_of(db, fest, user)
    if is_fest_staff(db, fest.id, user) and contingent_id is not None:
        return _contingent(db, fest, contingent_id)
    if mine is not None and (contingent_id is None or contingent_id == mine.id):
        return mine
    if is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=400, detail="Say which contingent is bidding")
    raise HTTPException(status_code=403, detail="Only a contingent's leaders and the committee can bid")


@router.put("/{slug}/auctions/{auction_id}/names/{name_id}/bid", response_model=schemas.MyAuctionName)
def place_bid(slug: str, auction_id: int, name_id: int, data: schemas.BidIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    a = _auction(db, fest, auction_id)
    n = _name(a, name_id)
    c = _bidder(db, fest, user, data.contingent_id)
    staff = is_fest_staff(db, fest.id, user)
    if a.status != "open":
        raise HTTPException(status_code=400, detail="This auction is not open for bids")
    if c.id in comp.disqualified_everywhere(comp.active_penalties(db, fest.id)):
        raise HTTPException(status_code=400, detail="This contingent is disqualified and cannot bid")
    if data.amount < a.min_bid:
        raise HTTPException(status_code=400, detail=f"The smallest bid is {a.min_bid} points")
    balance = comp.balance_of(db, fest, c.id)
    if data.amount > balance:
        raise HTTPException(status_code=400, detail=f"That is more than the {balance} points this contingent has")
    now = datetime.utcnow()
    bid = next((b for b in n.bids if b.contingent_id == c.id), None)
    if bid:
        if not staff and data.amount <= bid.amount:
            raise HTTPException(status_code=400, detail=f"A bid can only be raised. Your bid is {bid.amount}; withdraw it to start again.")
        bid.amount, bid.updated_at, bid.placed_by_id = data.amount, now, user.id
    else:
        db.add(models.AuctionBid(auction_name_id=n.id, contingent_id=c.id, amount=data.amount, placed_by_id=user.id, created_at=now, updated_at=now))
    db.commit()
    db.refresh(n)
    top = max((b.amount for b in n.bids), default=None)
    return schemas.MyAuctionName(id=n.id, name=n.name, code=n.code, my_bid=data.amount, top_bid=top if (a.show_highest_bid or staff) else None)


@router.delete("/{slug}/auctions/{auction_id}/names/{name_id}/bid", response_model=schemas.MyAuctionName)
def withdraw_bid(slug: str, auction_id: int, name_id: int, contingent_id: Optional[int] = Query(default=None), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    a = _auction(db, fest, auction_id)
    n = _name(a, name_id)
    c = _bidder(db, fest, user, contingent_id)
    if a.status != "open":
        raise HTTPException(status_code=400, detail="This auction is not open for bids")
    bid = next((b for b in n.bids if b.contingent_id == c.id), None)
    if not bid:
        raise HTTPException(status_code=404, detail="There is no bid to withdraw")
    db.delete(bid)
    db.commit()
    db.refresh(n)
    return schemas.MyAuctionName(id=n.id, name=n.name, code=n.code, my_bid=None)
