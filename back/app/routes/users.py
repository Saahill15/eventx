from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.auth.dependencies import get_current_user
from passlib.context import CryptContext

router = APIRouter()
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__truncate_error=False)

@router.get("/me", response_model=schemas.UserOut)
def get_me(current_user=Depends(get_current_user)):
    return current_user

@router.patch("/me", response_model=schemas.UserOut)
def update_profile(data: schemas.ProfileUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    updates = data.model_dump(exclude_unset=True)
    if updates.get("name") is None:
        updates.pop("name", None)
    if updates.get("college_id") is not None and not db.query(models.College).filter(models.College.id == updates["college_id"]).first():
        raise HTTPException(status_code=400, detail="College not found")
    if updates.get("phone"):
        taken = db.query(models.User).filter(models.User.phone == updates["phone"], models.User.id != current_user.id).first()
        if taken:
            raise HTTPException(status_code=400, detail="That phone number is already in use")
    for field, value in updates.items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/password")
def change_password(data: schemas.PasswordChange, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if not current_user.hashed_password or not pwd.verify(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.hashed_password = pwd.hash(data.new_password)
    db.commit()
    return {"message": "Password changed"}


@router.post("/interests")
def set_interests(data: schemas.SetInterests, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    valid_ids = {i for (i,) in db.query(models.Interest.id).filter(models.Interest.id.in_(data.interest_ids)).all()}
    if len(valid_ids) != len(data.interest_ids):
        raise HTTPException(status_code=400, detail="Unknown interest id")
    db.query(models.UserInterest).filter(models.UserInterest.user_id == current_user.id).delete()
    for iid in data.interest_ids:
        db.add(models.UserInterest(user_id=current_user.id, interest_id=iid))
    current_user.interests_set = True
    db.commit()
    return {"message": "Interests saved"}

@router.get("/interests/all", response_model=list[schemas.InterestOut])
def get_all_interests(db: Session = Depends(get_db)):
    return db.query(models.Interest).all()

@router.get("/me/fest-passes", response_model=list[schemas.FestPassDetailOut])
def my_fest_passes(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return (
        db.query(models.FestPass)
        .filter(models.FestPass.user_id == current_user.id)
        .order_by(models.FestPass.created_at.desc())
        .all()
    )
