"""Account notices (the bell icon) and the invitation email that goes with them."""

import logging
import os
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app import models, schemas
from app.mailer import MailFailed, MailNotConfigured, send_email

log = logging.getLogger("hiveout.notices")

ROLE_NAMES = {"core": "core team", "volunteer": "volunteer", "owner": "festival director"}


def notify(db: Session, user_id: int, kind: str, title: str, body: str, invite_id: Optional[int] = None) -> None:
    db.add(models.AccountNotice(
        user_id=user_id, kind=kind, title=title, body=body, invite_id=invite_id, created_at=datetime.utcnow(),
    ))


def invite_email_text(name: str, fest_name: str, role: str, inviter: str) -> str:
    site = os.getenv("SITE_URL", "http://localhost:3000").rstrip("/")
    return (
        f"Hi {name},\n\n"
        f"{inviter} has invited you to join the {fest_name} team as {ROLE_NAMES.get(role, role)}.\n\n"
        f"Sign in to HiveOut and open the bell icon to accept or decline: {site}\n\n"
        "Nothing changes until you accept. If you did not expect this, you can ignore it.\n"
    )


def send_invite_email(to: str, name: str, fest_name: str, role: str, inviter: str) -> bool:
    """Returns False when the email could not be sent. The invitation still stands either way."""
    try:
        send_email(to, f"Invitation to join {fest_name}", invite_email_text(name, fest_name, role, inviter))
        return True
    except (MailFailed, MailNotConfigured) as exc:
        log.warning("Invitation email to %s not sent: %s", to, exc)
        return False


def invite_out(inv: models.FestInvite) -> "schemas.FestInviteOut":
    return schemas.FestInviteOut(
        id=inv.id, fest_id=inv.fest_id, fest_slug=inv.fest.slug if inv.fest else None, fest_name=inv.fest.name if inv.fest else None,
        user_id=inv.user_id, user_name=inv.user.name if inv.user else None, user_email=inv.user.email if inv.user else None,
        role=inv.role, status=inv.status, invited_by_name=inv.inviter.name if inv.inviter else None,
        created_at=inv.created_at, decided_at=inv.decided_at,
    )
