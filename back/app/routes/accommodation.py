"""
Accommodation for visiting colleges.

The committee lists the places it can put people up (a hostel block, a guest house) with how many each holds, who it is for and
what it costs per person per night. A contingent's leader asks for a place: how many boys, girls and others, and which nights.
The committee places them, and the stay is added to the contingent's fees.

  GET|PUT   /api/fests/{slug}/accommodation/settings          whether colleges can ask, and until when
  GET|POST  /api/fests/{slug}/accommodation/options           the places (committee); PATCH|DELETE .../options/{id}
  GET|PUT|DELETE /api/fests/{slug}/accommodation/mine         a leader's own request
  GET       /api/fests/{slug}/accommodation/requests          every request (committee)
  PUT       /api/fests/{slug}/accommodation/requests/{id}/allocations   place the people, replacing earlier placing
  POST      /api/fests/{slug}/accommodation/requests/{id}/decline       say there is no room, with a reason
"""

from datetime import date, datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import contingent_money as money
from app import models, notices, schemas
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.money import rupees, to_paise
from app.permissions import can_view_fest, is_fest_staff
from app.routes.contingents import _fest, _role

router = APIRouter()
MAX_OPTIONS = 50


class MyStay(BaseModel):
    contingent_id: int
    settings: schemas.AccomSettings
    request: Optional[schemas.StayRequestOut] = None


# ─── helpers ──────────────────────────────────────────────────────────────────

def _staff(db: Session, fest: models.Fest, user) -> None:
    if not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can do that")


def _settings_out(s: models.ContingentSettings) -> schemas.AccomSettings:
    open_ = bool(s.accommodation_enabled) and (s.accommodation_closes_on is None or date.today() <= s.accommodation_closes_on)
    return schemas.AccomSettings(enabled=bool(s.accommodation_enabled), closes_on=s.accommodation_closes_on, open=open_)


def _my_contingent(db: Session, fest: models.Fest, user) -> Optional[models.Contingent]:
    for c in db.query(models.Contingent).filter(models.Contingent.fest_id == fest.id, models.Contingent.status == "approved").order_by(models.Contingent.id).all():
        if _role(c, user):
            return c
    return None


def _used(db: Session, option_id: int, except_request_id: Optional[int] = None) -> int:
    q = db.query(func.coalesce(func.sum(models.AccommodationAllocation.people), 0)).filter(models.AccommodationAllocation.option_id == option_id)
    if except_request_id is not None:
        q = q.filter(models.AccommodationAllocation.request_id != except_request_id)
    return int(q.scalar() or 0)


def _option_out(db: Session, o: models.AccommodationOption) -> schemas.AccomOptionOut:
    used = _used(db, o.id)
    return schemas.AccomOptionOut(id=o.id, name=o.name, description=o.description, capacity=o.capacity, gender_policy=o.gender_policy, fee_per_night=rupees(o.fee_per_night_paise), allocated=used, free=max(o.capacity - used, 0))


def _request_out(r: models.AccommodationRequest) -> schemas.StayRequestOut:
    placed: Dict[str, int] = {"boys": 0, "girls": 0, "others": 0}
    for a in r.allocations:
        placed[a.grp] = placed.get(a.grp, 0) + a.people
    asked = {"boys": r.boys, "girls": r.girls, "others": r.others}
    c = r.contingent
    return schemas.StayRequestOut(
        id=r.id, contingent_id=r.contingent_id, contingent_label=money.label(c), college_name=c.college_name, boys=r.boys, girls=r.girls, others=r.others, people=r.people,
        arrival_date=r.arrival_date, departure_date=r.departure_date, nights=r.nights, notes=r.notes, status=r.status, decision_note=r.decision_note,
        allocations=[schemas.StayAllocationOut(option_id=a.option_id, option_name=a.option.name if a.option else "", group=a.grp, people=a.people, nights=r.nights,
                                                fee=rupees((a.option.fee_per_night_paise if a.option else 0) * a.people * r.nights)) for a in sorted(r.allocations, key=lambda x: x.id)],
        unplaced={g: max(asked[g] - placed.get(g, 0), 0) for g in asked}, fee=rupees(money.stay_fee_paise(r)) if r.status == "allocated" else 0,
    )


# ─── settings ─────────────────────────────────────────────────────────────────

@router.get("/{slug}/accommodation/settings", response_model=schemas.AccomSettings)
def get_settings(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    if not can_view_fest(db, fest, user):
        raise HTTPException(status_code=404, detail="Fest not found")
    out = _settings_out(money.settings_row(db, fest))
    db.commit()
    return out


@router.put("/{slug}/accommodation/settings", response_model=schemas.AccomSettings)
def put_settings(slug: str, data: schemas.AccomSettingsIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    s = money.settings_row(db, fest)
    updates = data.model_dump(exclude_unset=True)
    if updates.get("enabled") is not None:
        s.accommodation_enabled = updates["enabled"]
    if "closes_on" in updates:
        s.accommodation_closes_on = updates["closes_on"]
    db.commit()
    return _settings_out(s)


# ─── the places ───────────────────────────────────────────────────────────────

@router.get("/{slug}/accommodation/options", response_model=List[schemas.AccomOptionOut])
def list_options(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    return [_option_out(db, o) for o in db.query(models.AccommodationOption).filter(models.AccommodationOption.fest_id == fest.id).order_by(models.AccommodationOption.position, models.AccommodationOption.id).all()]


@router.post("/{slug}/accommodation/options", response_model=schemas.AccomOptionOut, status_code=status.HTTP_201_CREATED)
def add_option(slug: str, data: schemas.AccomOptionIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    n = db.query(models.AccommodationOption).filter(models.AccommodationOption.fest_id == fest.id).count()
    if n >= MAX_OPTIONS:
        raise HTTPException(status_code=400, detail=f"A fest can list at most {MAX_OPTIONS} places")
    o = models.AccommodationOption(fest_id=fest.id, name=data.name, description=data.description or None, capacity=data.capacity, gender_policy=data.gender_policy, fee_per_night_paise=to_paise(data.fee_per_night), position=n)
    db.add(o)
    db.commit()
    db.refresh(o)
    return _option_out(db, o)


def _option(db: Session, fest: models.Fest, option_id: int) -> models.AccommodationOption:
    o = db.query(models.AccommodationOption).filter(models.AccommodationOption.id == option_id, models.AccommodationOption.fest_id == fest.id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Place not found")
    return o


@router.patch("/{slug}/accommodation/options/{option_id}", response_model=schemas.AccomOptionOut)
def update_option(slug: str, option_id: int, data: schemas.AccomOptionUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    o = _option(db, fest, option_id)
    u = data.model_dump(exclude_unset=True)
    used = _used(db, o.id)
    if u.get("capacity") is not None and u["capacity"] < used:
        raise HTTPException(status_code=400, detail=f"{used} people are already placed here, so it cannot hold fewer than that")
    if u.get("gender_policy") in ("boys", "girls"):
        clash = {"boys": "girls", "girls": "boys"}[u["gender_policy"]]
        if db.query(models.AccommodationAllocation).filter(models.AccommodationAllocation.option_id == o.id, models.AccommodationAllocation.grp.in_([clash, "others"])).first():
            raise HTTPException(status_code=400, detail="People of another group are already placed here. Move them first.")
    for field in ("name", "capacity", "gender_policy"):
        if u.get(field) is not None:
            setattr(o, field, u[field])
    if "description" in u:
        o.description = u["description"] or None
    if u.get("fee_per_night") is not None:
        o.fee_per_night_paise = to_paise(u["fee_per_night"])
    db.commit()
    return _option_out(db, o)


@router.delete("/{slug}/accommodation/options/{option_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_option(slug: str, option_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    o = _option(db, fest, option_id)
    if _used(db, o.id):
        raise HTTPException(status_code=400, detail="People are placed here. Move them first, then delete it.")
    db.delete(o)
    db.commit()


# ─── a leader's own request ───────────────────────────────────────────────────

def _own(db: Session, fest: models.Fest, user) -> models.Contingent:
    c = _my_contingent(db, fest, user)
    if not c:
        raise HTTPException(status_code=403, detail="Only the leaders of an approved contingent can ask for accommodation")
    return c


@router.get("/{slug}/accommodation/mine", response_model=Optional[MyStay])
def my_request(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    c = _my_contingent(db, fest, user)
    if not c:
        return None
    r = db.query(models.AccommodationRequest).filter(models.AccommodationRequest.contingent_id == c.id).first()
    out = MyStay(contingent_id=c.id, settings=_settings_out(money.settings_row(db, fest)), request=_request_out(r) if r and r.status != "cancelled" else None)
    db.commit()
    return out


@router.put("/{slug}/accommodation/mine", response_model=schemas.StayRequestOut)
def ask_for_stay(slug: str, data: schemas.StayRequestIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    c = _own(db, fest, user)
    s = _settings_out(money.settings_row(db, fest))
    if not s.open:
        raise HTTPException(status_code=400, detail="Accommodation requests are not open" if not s.enabled else "Accommodation requests have closed")
    r = db.query(models.AccommodationRequest).filter(models.AccommodationRequest.contingent_id == c.id).first()
    if r and r.status == "allocated":
        raise HTTPException(status_code=400, detail="You have already been given a place. Ask the committee if something needs to change.")
    if not r:
        r = models.AccommodationRequest(fest_id=fest.id, contingent_id=c.id, arrival_date=data.arrival_date, departure_date=data.departure_date)
        db.add(r)
    r.boys, r.girls, r.others, r.arrival_date, r.departure_date, r.notes = data.boys, data.girls, data.others, data.arrival_date, data.departure_date, data.notes or None
    r.status, r.decision_note, r.decided_at, r.decided_by_id = "requested", None, None, None
    db.commit()
    db.refresh(r)
    return _request_out(r)


@router.delete("/{slug}/accommodation/mine", response_model=schemas.StayRequestOut)
def cancel_request(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    c = _own(db, fest, user)
    r = db.query(models.AccommodationRequest).filter(models.AccommodationRequest.contingent_id == c.id).first()
    if not r or r.status == "cancelled":
        raise HTTPException(status_code=404, detail="You have no request to cancel")
    for a in list(r.allocations):
        db.delete(a)  # a cancelled stay frees its places
    r.status = "cancelled"
    db.commit()
    db.refresh(r)
    return _request_out(r)


# ─── the committee's side ─────────────────────────────────────────────────────

@router.get("/{slug}/accommodation/requests", response_model=List[schemas.StayRequestOut])
def all_requests(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    rows = db.query(models.AccommodationRequest).filter(models.AccommodationRequest.fest_id == fest.id, models.AccommodationRequest.status != "cancelled").order_by(models.AccommodationRequest.id).all()
    return [_request_out(r) for r in rows]


def _request(db: Session, fest: models.Fest, request_id: int) -> models.AccommodationRequest:
    r = db.query(models.AccommodationRequest).filter(models.AccommodationRequest.id == request_id, models.AccommodationRequest.fest_id == fest.id).first()
    if not r or r.status == "cancelled":
        raise HTTPException(status_code=404, detail="Request not found")
    return r


@router.put("/{slug}/accommodation/requests/{request_id}/allocations", response_model=schemas.StayRequestOut)
def allocate(slug: str, request_id: int, data: schemas.StayAllocationsIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Place the people, replacing any earlier placing. Nobody can be placed twice, beyond what was asked, or past what a place holds."""
    fest = _fest(db, slug)
    _staff(db, fest, user)
    r = _request(db, fest, request_id)
    asked = {"boys": r.boys, "girls": r.girls, "others": r.others}
    totals: Dict[str, int] = {"boys": 0, "girls": 0, "others": 0}
    per_option: Dict[int, int] = {}
    seen = set()
    for a in data.allocations:
        o = _option(db, fest, a.option_id)
        if (a.option_id, a.group) in seen:
            raise HTTPException(status_code=400, detail="List each place and group once")
        seen.add((a.option_id, a.group))
        if o.gender_policy != "any" and o.gender_policy != a.group:
            raise HTTPException(status_code=400, detail=f"{o.name} is for {o.gender_policy} only")
        totals[a.group] += a.people
        per_option[o.id] = per_option.get(o.id, 0) + a.people
    for g, n in totals.items():
        if n > asked[g]:
            raise HTTPException(status_code=400, detail=f"You placed {n} {g}, but only {asked[g]} were asked for")
    for oid, n in per_option.items():
        o = _option(db, fest, oid)
        free = o.capacity - _used(db, oid, except_request_id=r.id)
        if n > free:
            raise HTTPException(status_code=400, detail=f"{o.name} has room for {max(free, 0)} more, and you placed {n}")
    for old in list(r.allocations):
        db.delete(old)
    db.flush()
    for a in data.allocations:
        db.add(models.AccommodationAllocation(request_id=r.id, option_id=a.option_id, grp=a.group, people=a.people))
    first = r.status != "allocated"
    r.status = "allocated" if data.allocations else "requested"
    r.decision_note, r.decided_by_id, r.decided_at = None, user.id, datetime.utcnow()
    db.flush()
    db.refresh(r)
    if data.allocations and first:
        notices.notify(db, r.contingent.leader_user_id, "contingent", "Your accommodation is arranged", f"{money.label(r.contingent)} has been given a place to stay for {r.nights} night{'s' if r.nights != 1 else ''}. The details and cost are on your page.")
    db.commit()
    db.refresh(r)
    return _request_out(r)


@router.post("/{slug}/accommodation/requests/{request_id}/decline", response_model=schemas.StayRequestOut)
def decline(slug: str, request_id: int, data: schemas.StayDeclineIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    r = _request(db, fest, request_id)
    for a in list(r.allocations):
        db.delete(a)
    r.status, r.decision_note, r.decided_by_id, r.decided_at = "declined", data.note, user.id, datetime.utcnow()
    notices.notify(db, r.contingent.leader_user_id, "contingent", "We could not arrange accommodation", f"The committee could not place {money.label(r.contingent)}. Reason: {data.note}")
    db.commit()
    db.refresh(r)
    return _request_out(r)
