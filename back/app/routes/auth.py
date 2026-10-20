import time
from collections import defaultdict, deque
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from app.database import get_db
from app import models, schemas
from app.auth.jwt import create_token

router = APIRouter()
pwd = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__truncate_error=False,  # truncate >72 bytes to avoid backend ValueError
)

# ─── Failed-login throttle ────────────────────────────────────────────────────
# In-memory and per process: slows password guessing without extra infrastructure.
MAX_FAILED_LOGINS = 10
LOGIN_WINDOW_SECONDS = 300
_failed_logins = defaultdict(deque)

def _throttle_key(request: Request, email: str) -> str:
    client = request.client.host if request.client else "unknown"
    return f"{client}|{email}"

def _recent_failures(key: str) -> deque:
    attempts = _failed_logins[key]
    cutoff = time.monotonic() - LOGIN_WINDOW_SECONDS
    while attempts and attempts[0] < cutoff:
        attempts.popleft()
    return attempts

def reset_login_throttle():
    _failed_logins.clear()


def _find_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(func.lower(models.User.email) == email.lower()).first()

def _token_response(user: models.User):
    token = create_token({"sub": str(user.id), "role": user.role})
    return {"access_token": token, "token_type": "bearer", "role": user.role, "interests_set": user.interests_set}


@router.post("/signup", response_model=schemas.Token)
def signup(data: schemas.SignupEmail, db: Session = Depends(get_db)):
    if _find_user_by_email(db, data.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = models.User(
        name=data.name,
        email=data.email,
        hashed_password=pwd.hash(data.password),
        auth_provider=models.AuthProviderEnum.email,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_response(user)

@router.post("/login", response_model=schemas.Token)
def login(data: schemas.LoginEmail, request: Request, db: Session = Depends(get_db)):
    key = _throttle_key(request, data.email)
    failures = _recent_failures(key)
    if len(failures) >= MAX_FAILED_LOGINS:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in a few minutes.")

    user = _find_user_by_email(db, data.email)
    if not user or not user.hashed_password or not pwd.verify(data.password, user.hashed_password):
        failures.append(time.monotonic())
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.is_active is False:
        raise HTTPException(status_code=403, detail="Account disabled")

    failures.clear()
    return _token_response(user)
