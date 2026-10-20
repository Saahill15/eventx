from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app import models, schemas
from app.auth.dependencies import require_admin

router = APIRouter()


@router.get("/", response_model=List[schemas.CollegeOut])
def get_colleges(db: Session = Depends(get_db)):
    return db.query(models.College).order_by(models.College.name).all()


@router.get("/{college_id}", response_model=schemas.CollegeOut)
def get_college(college_id: int, db: Session = Depends(get_db)):
    college = db.query(models.College).filter(models.College.id == college_id).first()
    if not college:
        raise HTTPException(status_code=404, detail="College not found")
    return college


@router.post("/", response_model=schemas.CollegeOut)
def create_college(data: schemas.CollegeCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    existing = db.query(models.College).filter(models.College.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="College already exists")
    college = models.College(**data.model_dump())
    db.add(college)
    db.commit()
    db.refresh(college)
    return college


@router.put("/{college_id}", response_model=schemas.CollegeOut)
def update_college(college_id: int, data: schemas.CollegeCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    college = db.query(models.College).filter(models.College.id == college_id).first()
    if not college:
        raise HTTPException(status_code=404, detail="College not found")
    if data.name != college.name and db.query(models.College).filter(models.College.name == data.name).first():
        raise HTTPException(status_code=400, detail="College already exists")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(college, k, v)
    db.commit()
    db.refresh(college)
    return college


@router.delete("/{college_id}")
def delete_college(college_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    college = db.query(models.College).filter(models.College.id == college_id).first()
    if not college:
        raise HTTPException(status_code=404, detail="College not found")
    # Unlink events before deleting
    db.query(models.Event).filter(models.Event.college_id == college_id).update({"college_id": None})
    db.delete(college)
    db.commit()
    return {"message": "College deleted"}


@router.get("/{college_id}/events", response_model=List[schemas.EventOut])
def get_college_events(college_id: int, db: Session = Depends(get_db)):
    college = db.query(models.College).filter(models.College.id == college_id).first()
    if not college:
        raise HTTPException(status_code=404, detail="College not found")
    return (
        db.query(models.Event)
        .filter(models.Event.college_id == college_id, models.Event.status == "approved")
        .order_by(models.Event.date.desc())
        .all()
    )
