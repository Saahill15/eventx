from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.auth.dependencies import require_organizer
from app.permissions import is_fest_staff

router = APIRouter()


def _can_manage_event(db: Session, event: models.Event, user) -> bool:
    if user.role == models.RoleEnum.admin:
        return True
    if event.event_type == models.EventTypeEnum.city:
        return event.organizer_id == user.id
    return is_fest_staff(db, event.fest_id, user)


def _get_managed_committee(db: Session, committee_id: int, user) -> models.Committee:
    committee = db.query(models.Committee).filter(models.Committee.id == committee_id).first()
    if not committee or not _can_manage_event(db, committee.event, user):
        raise HTTPException(status_code=404, detail="Committee not found")
    return committee


@router.post("/{event_id}/committees", response_model=schemas.CommitteeOut)
def create_committee(event_id: int, data: schemas.CommitteeCreate, db: Session = Depends(get_db), current_user=Depends(require_organizer)):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event or not _can_manage_event(db, event, current_user):
        raise HTTPException(status_code=404, detail="Event not found")
    c = models.Committee(event_id=event_id, name=data.name)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c

@router.post("/committees/{committee_id}/departments", response_model=schemas.DepartmentOut)
def create_department(committee_id: int, data: schemas.DepartmentCreate, db: Session = Depends(get_db), current_user=Depends(require_organizer)):
    _get_managed_committee(db, committee_id, current_user)
    d = models.Department(committee_id=committee_id, name=data.name)
    db.add(d)
    db.commit()
    db.refresh(d)
    return d

@router.post("/departments/{department_id}/members")
def add_member(department_id: int, data: schemas.MemberAdd, db: Session = Depends(get_db), current_user=Depends(require_organizer)):
    department = db.query(models.Department).filter(models.Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    _get_managed_committee(db, department.committee_id, current_user)
    if not db.query(models.User).filter(models.User.id == data.user_id).first():
        raise HTTPException(status_code=404, detail="User not found")
    m = models.DepartmentMember(department_id=department_id, user_id=data.user_id, role=data.role)
    db.add(m)
    db.commit()
    return {"message": "Member added"}
