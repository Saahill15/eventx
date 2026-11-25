"""
Certificates.

The committee writes the wording of each kind of certificate (participation, winner, appreciation) with {name}, {event}, {fest},
{college}, {date} and {award} filled in for each person, and signs it with up to three names. It then issues them: to everyone who
attended an event, to the people in a visiting college's entries, or to one person at a time (the winner of a competition). Each
certificate keeps its own copy of the wording and carries a short code, so anyone can check it is genuine and a mistake can be revoked.

  GET|POST   /api/fests/{slug}/certificate-templates               the wordings (committee); POST .../usual adds a usual set
  PATCH|DELETE .../certificate-templates/{id}
  POST       /api/fests/{slug}/certificates/issue-attended         to everyone who attended an event
  POST       /api/fests/{slug}/certificates/issue-entries          to the people in a visiting college's entries for an event
  POST       /api/fests/{slug}/certificates                        to one person
  GET        /api/fests/{slug}/certificates                        everything issued (committee); POST .../{id}/revoke
  GET        /api/users/me/certificates                            my own
  GET        /api/certificates/{code}                              check a certificate (public)
"""

import re
import secrets
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, notices, schemas
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.permissions import is_fest_staff

router = APIRouter()
me_router = APIRouter()
public_router = APIRouter()

MAX_TEMPLATES = 40
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # no 0/O or 1/I: a code read aloud is not misheard
USUAL = [
    ("participation", "Certificate of Participation", "This is to certify that {name} took part in {event} at {fest}, held on {date}."),
    ("winner", "Certificate of Achievement", "This is to certify that {name} secured {award} in {event} at {fest}, held on {date}."),
    ("appreciation", "Certificate of Appreciation", "In recognition of the valuable contribution of {name} to {fest}."),
]


# ─── helpers ──────────────────────────────────────────────────────────────────

def _fest(db: Session, slug: str) -> models.Fest:
    f = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    if not f:
        raise HTTPException(status_code=404, detail="Fest not found")
    return f


def _staff(db: Session, fest: models.Fest, user) -> None:
    if not is_fest_staff(db, fest.id, user):
        raise HTTPException(status_code=403, detail="Only the fest's director or core team can do that")


def _event(db: Session, fest: models.Fest, event_id: Optional[int]) -> Optional[models.Event]:
    if event_id is None:
        return None
    e = db.query(models.Event).filter(models.Event.id == event_id, models.Event.fest_id == fest.id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Event not found in this fest")
    return e


def _template(db: Session, fest: models.Fest, template_id: int, event: Optional[models.Event] = None) -> models.CertificateTemplate:
    t = db.query(models.CertificateTemplate).filter(models.CertificateTemplate.id == template_id, models.CertificateTemplate.fest_id == fest.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Certificate wording not found")
    if event is not None and t.event_id is not None and t.event_id != event.id:
        raise HTTPException(status_code=400, detail="That wording is written for a different event")
    return t


def fill(text: str, name: str, event: Optional[models.Event], fest: models.Fest, college: Optional[str], award: Optional[str]) -> str:
    """Put the details into {name}, {event}, {fest}, {college}, {date} and {award}. Anything else in braces is left as written."""
    values = {"name": name, "event": event.title if event else "", "fest": fest.name, "college": college or "", "award": award or "",
              "date": event.date.strftime("%d %B %Y").lstrip("0") if event else (fest.start_date.strftime("%d %B %Y").lstrip("0") if fest.start_date else "")}
    return re.sub(r"\{(name|event|fest|college|date|award)\}", lambda m: values[m.group(1)], text)


def _code(db: Session) -> str:
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(10))
        if not db.query(models.Certificate.id).filter(models.Certificate.code == code).first():
            return code


def template_out(db: Session, t: models.CertificateTemplate) -> schemas.CertTemplateOut:
    ev = db.query(models.Event).filter(models.Event.id == t.event_id).first() if t.event_id else None
    return schemas.CertTemplateOut(id=t.id, event_id=t.event_id, event_title=ev.title if ev else None, kind=t.kind, title=t.title, body=t.body, signatories=[schemas.Signatory(**s) for s in (t.signatories or [])])


def certificate_out(c: models.Certificate) -> schemas.CertificateOut:
    return schemas.CertificateOut(
        id=c.id, code=c.code, kind=c.kind, recipient_name=c.recipient_name, college_name=c.college_name, award_text=c.award_text, title=c.title, body=c.body,
        signatories=[schemas.Signatory(**s) for s in (c.signatories or [])], fest_name=c.fest_name, event_title=c.event_title, issued_at=c.issued_at,
        revoked=c.revoked_at is not None, revoked_reason=c.revoked_reason, has_account=c.user_id is not None,
    )


def _issue(db: Session, fest: models.Fest, template: models.CertificateTemplate, event: Optional[models.Event], name: str, issuer: models.User,
           user_id: Optional[int] = None, college: Optional[str] = None, award: Optional[str] = None) -> models.Certificate:
    c = models.Certificate(
        fest_id=fest.id, event_id=event.id if event else None, user_id=user_id, kind=template.kind, code=_code(db), recipient_name=name, college_name=college, award_text=award,
        title=fill(template.title, name, event, fest, college, award)[:120], body=fill(template.body, name, event, fest, college, award)[:1200], signatories=list(template.signatories or []),
        fest_name=fest.name, event_title=event.title if event else None, issued_by_id=issuer.id,
    )
    db.add(c)
    db.flush()
    if user_id:
        notices.notify(db, user_id, "certificate", f"Your certificate: {c.title}", f"{fest.name} has issued you a {c.title.lower()}" + (f" for {event.title}" if event else "") + ". Find it under My passes, or check it with the code " + c.code + ".")
    return c


# ─── wordings ─────────────────────────────────────────────────────────────────

@router.get("/{slug}/certificate-templates", response_model=List[schemas.CertTemplateOut])
def list_templates(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    return [template_out(db, t) for t in db.query(models.CertificateTemplate).filter(models.CertificateTemplate.fest_id == fest.id).order_by(models.CertificateTemplate.id).all()]


@router.post("/{slug}/certificate-templates", response_model=schemas.CertTemplateOut, status_code=status.HTTP_201_CREATED)
def add_template(slug: str, data: schemas.CertTemplateIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    if db.query(models.CertificateTemplate).filter(models.CertificateTemplate.fest_id == fest.id).count() >= MAX_TEMPLATES:
        raise HTTPException(status_code=400, detail=f"A fest can have at most {MAX_TEMPLATES} certificate wordings")
    _event(db, fest, data.event_id)
    t = models.CertificateTemplate(fest_id=fest.id, event_id=data.event_id, kind=data.kind, title=data.title, body=data.body, signatories=[s.model_dump() for s in data.signatories])
    db.add(t)
    db.commit()
    db.refresh(t)
    return template_out(db, t)


@router.post("/{slug}/certificate-templates/usual", response_model=List[schemas.CertTemplateOut], status_code=status.HTTP_201_CREATED)
def add_usual_templates(slug: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """A usual wording for each kind to start from. Kinds the fest already has a wording for (for the whole fest) are skipped."""
    fest = _fest(db, slug)
    _staff(db, fest, user)
    have = {t.kind for t in db.query(models.CertificateTemplate).filter(models.CertificateTemplate.fest_id == fest.id, models.CertificateTemplate.event_id.is_(None)).all()}
    for kind, title, body in USUAL:
        if kind not in have:
            db.add(models.CertificateTemplate(fest_id=fest.id, kind=kind, title=title, body=body, signatories=[]))
    db.commit()
    return list_templates(slug, db, user)


@router.patch("/{slug}/certificate-templates/{template_id}", response_model=schemas.CertTemplateOut)
def update_template(slug: str, template_id: int, data: schemas.CertTemplateUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    t = _template(db, fest, template_id)
    u = data.model_dump(exclude_unset=True)
    for field in ("title", "body", "kind"):
        if u.get(field) is not None:
            setattr(t, field, u[field])
    if "event_id" in u:
        _event(db, fest, u["event_id"])
        t.event_id = u["event_id"]
    if u.get("signatories") is not None:
        t.signatories = u["signatories"]
    db.commit()
    return template_out(db, t)


@router.delete("/{slug}/certificate-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(slug: str, template_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    db.delete(_template(db, fest, template_id))   # certificates already issued keep their own copy of the wording
    db.commit()


# ─── issuing ──────────────────────────────────────────────────────────────────

def _already(db: Session, fest: models.Fest, event: Optional[models.Event], kind: str, user_id: Optional[int], name: str, college: Optional[str]) -> bool:
    q = db.query(models.Certificate.id).filter(models.Certificate.fest_id == fest.id, models.Certificate.kind == kind, models.Certificate.revoked_at.is_(None),
                                               models.Certificate.event_id == (event.id if event else None))
    if user_id:
        return q.filter(models.Certificate.user_id == user_id).first() is not None
    return q.filter(func.lower(models.Certificate.recipient_name) == name.lower(), func.coalesce(models.Certificate.college_name, "") == (college or "")).first() is not None


@router.post("/{slug}/certificates/issue-attended", response_model=schemas.IssueResult, status_code=status.HTTP_201_CREATED)
def issue_attended(slug: str, data: schemas.IssueAttendedIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """A certificate for everyone checked in to the event who does not have this kind of certificate for it yet."""
    fest = _fest(db, slug)
    _staff(db, fest, user)
    event = _event(db, fest, data.event_id)
    t = _template(db, fest, data.template_id, event)
    issued = skipped = 0
    regs = db.query(models.EventRegistration).filter(models.EventRegistration.event_id == event.id, models.EventRegistration.attended.is_(True)).all()
    for r in regs:
        person = r.fest_pass.user if r.fest_pass else None
        if not person:
            continue
        if _already(db, fest, event, t.kind, person.id, person.name, None):
            skipped += 1
            continue
        _issue(db, fest, t, event, person.name, user, user_id=person.id)
        issued += 1
    db.commit()
    return schemas.IssueResult(issued=issued, skipped=skipped)


@router.post("/{slug}/certificates/issue-entries", response_model=schemas.IssueResult, status_code=status.HTTP_201_CREATED)
def issue_entries(slug: str, data: schemas.IssueEntriesIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """A certificate for each person in a visiting college's confirmed entries for the event. They need no HiveOut account."""
    fest = _fest(db, slug)
    _staff(db, fest, user)
    event = _event(db, fest, data.event_id)
    t = _template(db, fest, data.template_id, event)
    issued = skipped = 0
    for entry in db.query(models.ContingentEntry).filter(models.ContingentEntry.event_id == event.id, models.ContingentEntry.status == "confirmed").all():
        for m in entry.members:
            if not m.member:
                continue
            college = entry.contingent.college_name
            if _already(db, fest, event, t.kind, None, m.member.name, college):
                skipped += 1
                continue
            _issue(db, fest, t, event, m.member.name, user, college=college, award=data.award_text or None)
            issued += 1
    db.commit()
    return schemas.IssueResult(issued=issued, skipped=skipped)


@router.post("/{slug}/certificates", response_model=schemas.CertificateOut, status_code=status.HTTP_201_CREATED)
def issue_one(slug: str, data: schemas.IssueOneIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    event = _event(db, fest, data.event_id)
    t = _template(db, fest, data.template_id, event)
    person = db.query(models.User).filter(func.lower(models.User.email) == data.email.lower()).first() if data.email else None
    if data.email and not person:
        raise HTTPException(status_code=404, detail="No HiveOut account has that email. Leave it empty to issue by name only.")
    c = _issue(db, fest, t, event, data.recipient_name, user, user_id=person.id if person else None, college=data.college_name or None, award=data.award_text or None)
    db.commit()
    db.refresh(c)
    return certificate_out(c)


@router.get("/{slug}/certificates", response_model=List[schemas.CertificateOut])
def list_certificates(slug: str, event_id: Optional[int] = None, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    fest = _fest(db, slug)
    _staff(db, fest, user)
    q = db.query(models.Certificate).filter(models.Certificate.fest_id == fest.id)
    if event_id is not None:
        q = q.filter(models.Certificate.event_id == event_id)
    return [certificate_out(c) for c in q.order_by(models.Certificate.issued_at.desc(), models.Certificate.id.desc()).limit(1000).all()]


@router.post("/{slug}/certificates/{certificate_id}/revoke", response_model=schemas.CertificateOut)
def revoke(slug: str, certificate_id: int, data: schemas.RevokeIn, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Withdraw a certificate that was issued by mistake. Its code then says it is no longer valid."""
    fest = _fest(db, slug)
    _staff(db, fest, user)
    c = db.query(models.Certificate).filter(models.Certificate.id == certificate_id, models.Certificate.fest_id == fest.id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if c.revoked_at is not None:
        raise HTTPException(status_code=400, detail="This certificate was already withdrawn")
    c.revoked_at, c.revoked_reason = datetime.utcnow(), data.reason
    db.commit()
    return certificate_out(c)


# ─── the person's own, and checking one ───────────────────────────────────────

@me_router.get("/certificates", response_model=List[schemas.CertificateOut])
def my_certificates(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    rows = db.query(models.Certificate).filter(models.Certificate.user_id == user.id, models.Certificate.revoked_at.is_(None)).order_by(models.Certificate.issued_at.desc(), models.Certificate.id.desc()).all()
    return [certificate_out(c) for c in rows]


@public_router.get("/certificates/{code}", response_model=schemas.CertificateCheck)
def check(code: str, db: Session = Depends(get_db)):
    """Anyone with a certificate's code can see whether it is genuine, and what it says."""
    c = db.query(models.Certificate).filter(models.Certificate.code == code.strip().upper()).first()
    if not c:
        return schemas.CertificateCheck(valid=False)
    return schemas.CertificateCheck(valid=c.revoked_at is None, revoked=c.revoked_at is not None, certificate=certificate_out(c))
