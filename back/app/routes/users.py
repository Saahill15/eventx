from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.auth.dependencies import get_current_user
from app.auth.sessions import revoke_user_sessions
from passlib.context import CryptContext

router = APIRouter()
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__truncate_error=False)

@router.get("/me", response_model=schemas.UserOut)
def get_me(current_user=Depends(get_current_user)):
    return current_user

@router.patch("/me", response_model=schemas.UserOut)
def update_profile(data: schemas.ProfileUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    updates = data.model_dump(exclude_unset=True)
    for part in ("first_name", "last_name"):
        if updates.get(part) is None:
            updates.pop(part, None)
    if "first_name" in updates or "last_name" in updates:
        first = updates.get("first_name", current_user.first_name or "")
        last = updates.get("last_name", current_user.last_name or "")
        updates["name"] = f"{first} {last}".strip()
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
    revoke_user_sessions(db, current_user.id, except_sid=current_user.current_sid)  # other devices must sign in again
    db.commit()
    return {"message": "Password changed"}


@router.post("/me/organizer-welcome/seen")
def organizer_welcome_seen(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """The person has seen the 'you are now an organiser' screen, so it is not shown again."""
    current_user.organizer_welcome_pending = False
    db.commit()
    return {"message": "OK"}


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
