from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth.jwt import decode_token
from app.auth.sessions import check_session
from app import models

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def _user_from_token(token: str, db: Session):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(models.User).filter(models.User.id == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if user.is_active is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    # Tokens without a live server-side session are refused (signed out, timed out, or issued before sessions existed)
    user.current_sid = check_session(db, payload.get("sid"), user).id
    return user

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    return _user_from_token(token, db)

def get_optional_user(token: Optional[str] = Depends(optional_oauth2_scheme), db: Session = Depends(get_db)):
    """The logged-in user, or None for anonymous visitors. A bad token still counts as anonymous."""
    if not token:
        return None
    try:
        return _user_from_token(token, db)
    except HTTPException:
        return None

def require_organizer(current_user=Depends(get_current_user)):
    if current_user.role not in ["organizer", "admin"]:
        raise HTTPException(status_code=403, detail="Organizer access required")
    return current_user

def require_admin(current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
