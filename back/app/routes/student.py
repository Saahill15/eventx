"""
Student verification. A verification lasts one year.

  GET  /api/users/me/student                  where the current user stands
  POST /api/users/me/student/email            send a code to a college email address
  POST /api/users/me/student/email/confirm    enter the code
  POST /api/users/me/student/proof            upload a document for an admin to review
"""

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth.dependencies import get_current_user
from app.auth.jwt import SECRET_KEY
from app.database import get_db
from app.mailer import MailFailed, MailNotConfigured, send_email

router = APIRouter()

VERIFICATION_DAYS = 365
RENEW_WINDOW_DAYS = 30          # may verify again this close to expiry
CODE_MINUTES = 15
MAX_CODE_ATTEMPTS = 5
MAX_REQUESTS_PER_HOUR = 5
MAX_PROOF_BYTES = 5 * 1024 * 1024
ACADEMIC_SUFFIXES = (".ac.in", ".edu.in", ".edu")
DOCUMENT_TYPES = {"id_card", "fee_receipt", "enrollment_form", "other"}
SIGNATURES = {  # file type -> (mime type, leading bytes)
    "jpeg": ("image/jpeg", b"\xff\xd8\xff"),
    "png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    "pdf": ("application/pdf", b"%PDF"),
}


def _hash_code(user_id: int, code: str) -> str:
    return hmac.new(SECRET_KEY.encode(), f"{user_id}:{code}".encode(), hashlib.sha256).hexdigest()


def _now() -> datetime:
    return datetime.utcnow()


def verify_user(db: Session, user: models.User, college_id: Optional[int]) -> None:
    """Mark the user as a verified student for a year. The caller commits."""
    user.student_verified_until = _now() + timedelta(days=VERIFICATION_DAYS)
    if college_id:
        user.college_id = college_id


def _can_verify(user: models.User) -> bool:
    if not user.is_student_verified:
        return True
    return user.student_verified_until - _now() <= timedelta(days=RENEW_WINDOW_DAYS)


def _guard_new_attempt(db: Session, user: models.User) -> None:
    if not _can_verify(user):
        raise HTTPException(status_code=400, detail=f"You are verified until {user.student_verified_until:%d %b %Y}. You can renew in the last {RENEW_WINDOW_DAYS} days.")
    recent = (
        db.query(models.StudentVerification)
        .filter(models.StudentVerification.user_id == user.id, models.StudentVerification.created_at > _now() - timedelta(hours=1))
        .count()
    )
    if recent >= MAX_REQUESTS_PER_HOUR:
        raise HTTPException(status_code=429, detail="Too many attempts. Try again in an hour.")


def college_for_email(db: Session, email: str) -> Optional[models.College]:
    domain = email.rsplit("@", 1)[-1].lower()
    for college in db.query(models.College).filter(models.College.email_domains.isnot(None)).all():
        for known in (college.email_domains or "").split(","):
            known = known.strip()
            if known and (domain == known or domain.endswith("." + known)):
                return college
    return None


@router.get("", response_model=schemas.StudentStatus)
def my_status(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    pending = (
        db.query(models.StudentVerification)
        .filter(models.StudentVerification.user_id == current_user.id, models.StudentVerification.status == models.VerificationStatusEnum.pending)
        .order_by(models.StudentVerification.created_at.desc())
        .first()
    )
    rejected = (
        db.query(models.StudentVerification)
        .filter(
            models.StudentVerification.user_id == current_user.id,
            models.StudentVerification.status == models.VerificationStatusEnum.rejected,
            models.StudentVerification.method == models.VerificationMethodEnum.proof,
        )
        .order_by(models.StudentVerification.created_at.desc())
        .first()
    )
    last = (
        db.query(models.StudentVerification)
        .filter(models.StudentVerification.user_id == current_user.id)
        .order_by(models.StudentVerification.created_at.desc())
        .first()
    )
    return schemas.StudentStatus(
        verified=current_user.is_student_verified,
        verified_until=current_user.student_verified_until,
        college_id=current_user.college_id,
        can_verify=_can_verify(current_user),
        pending=schemas.PendingVerification(id=pending.id, method=pending.method.value, created_at=pending.created_at, email=pending.email, document_type=pending.document_type) if pending else None,
        last_rejection=rejected.reject_reason if rejected and last and last.id == rejected.id else None,
    )


@router.post("/email")
def request_email_code(data: schemas.StudentEmailRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    _guard_new_attempt(db, current_user)

    college = college_for_email(db, data.email)
    if college is None:
        if not data.email.endswith(ACADEMIC_SUFFIXES):
            raise HTTPException(status_code=400, detail="That does not look like a college email. Use a college address, or upload a document instead.")
        if data.college_id is None:
            raise HTTPException(status_code=400, detail="Choose your college so we can match it to this email.")
        college = db.query(models.College).filter(models.College.id == data.college_id).first()
        if college is None:
            raise HTTPException(status_code=400, detail="College not found")

    # One college email can verify one account at a time
    taken = (
        db.query(models.StudentVerification)
        .join(models.User, models.User.id == models.StudentVerification.user_id)
        .filter(
            models.StudentVerification.email == data.email,
            models.StudentVerification.status == models.VerificationStatusEnum.approved,
            models.StudentVerification.user_id != current_user.id,
            models.User.student_verified_until > _now(),
        )
        .first()
    )
    if taken:
        raise HTTPException(status_code=400, detail="That email already verifies another account.")

    # A new code replaces any earlier unfinished one (the old record is kept so the hourly limit still counts it)
    db.query(models.StudentVerification).filter(
        models.StudentVerification.user_id == current_user.id,
        models.StudentVerification.status == models.VerificationStatusEnum.pending,
        models.StudentVerification.method == models.VerificationMethodEnum.email,
    ).update({"status": models.VerificationStatusEnum.rejected, "reject_reason": "Replaced by a newer code", "code_hash": None})

    code = f"{secrets.randbelow(10**6):06d}"
    record = models.StudentVerification(
        user_id=current_user.id, method=models.VerificationMethodEnum.email, status=models.VerificationStatusEnum.pending,
        college_id=college.id, email=data.email, code_hash=_hash_code(current_user.id, code),
        code_expires_at=_now() + timedelta(minutes=CODE_MINUTES), created_at=_now(),
    )
    db.add(record)
    db.flush()
    try:
        send_email(
            data.email,
            "Your HiveOut verification code",
            f"Your HiveOut code is {code}. It works for {CODE_MINUTES} minutes.\n\nIf you did not ask for this, ignore this email.",
        )
    except MailNotConfigured:
        db.rollback()
        raise HTTPException(status_code=503, detail="Email sending is not set up yet. Upload a document instead.")
    except MailFailed:
        db.rollback()
        raise HTTPException(status_code=502, detail="We could not send the email. Try again, or upload a document instead.")
    db.commit()
    return {"message": "Code sent", "expires_in_minutes": CODE_MINUTES}


@router.post("/email/confirm", response_model=schemas.StudentStatus)
def confirm_email_code(data: schemas.StudentCodeConfirm, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    record = (
        db.query(models.StudentVerification)
        .filter(
            models.StudentVerification.user_id == current_user.id,
            models.StudentVerification.method == models.VerificationMethodEnum.email,
            models.StudentVerification.status == models.VerificationStatusEnum.pending,
        )
        .order_by(models.StudentVerification.created_at.desc())
        .first()
    )
    if record is None:
        raise HTTPException(status_code=400, detail="Ask for a code first.")
    if record.code_expires_at < _now():
        raise HTTPException(status_code=400, detail="That code has expired. Ask for a new one.")
    if record.attempts >= MAX_CODE_ATTEMPTS:
        raise HTTPException(status_code=400, detail="Too many wrong codes. Ask for a new one.")
    if not hmac.compare_digest(record.code_hash or "", _hash_code(current_user.id, data.code)):
        record.attempts += 1
        db.commit()
        raise HTTPException(status_code=400, detail="That code is not right.")

    record.status = models.VerificationStatusEnum.approved
    record.reviewed_at = _now()
    record.code_hash = None
    verify_user(db, current_user, record.college_id)
    db.commit()
    return my_status(db, current_user)


def _sniff(data: bytes) -> Optional[str]:
    for _, (mime, head) in SIGNATURES.items():
        if data.startswith(head):
            return mime
    return None


@router.post("/proof", response_model=schemas.StudentStatus)
async def upload_proof(
    college_id: int = Form(...),
    document_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _guard_new_attempt(db, current_user)
    if document_type not in DOCUMENT_TYPES:
        raise HTTPException(status_code=400, detail="Choose what kind of document this is.")
    if not db.query(models.College).filter(models.College.id == college_id).first():
        raise HTTPException(status_code=400, detail="College not found")
    already = (
        db.query(models.StudentVerification)
        .filter(
            models.StudentVerification.user_id == current_user.id,
            models.StudentVerification.method == models.VerificationMethodEnum.proof,
            models.StudentVerification.status == models.VerificationStatusEnum.pending,
        )
        .first()
    )
    if already:
        raise HTTPException(status_code=400, detail="Your document is already waiting for review.")

    content = await file.read(MAX_PROOF_BYTES + 1)
    if len(content) > MAX_PROOF_BYTES:
        raise HTTPException(status_code=400, detail="That file is too large. The limit is 5 MB.")
    if len(content) < 100:
        raise HTTPException(status_code=400, detail="That file looks empty.")
    mime = _sniff(content)
    if mime is None:
        raise HTTPException(status_code=400, detail="Upload a JPEG or PNG photo, or a PDF.")

    db.add(models.StudentVerification(
        user_id=current_user.id, method=models.VerificationMethodEnum.proof, status=models.VerificationStatusEnum.pending,
        college_id=college_id, document_type=document_type, document_name=os.path.basename(file.filename or "document")[:255],
        document_mime=mime, document_data=content, created_at=_now(),
    ))
    db.commit()
    return my_status(db, current_user)
