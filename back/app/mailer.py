"""Send transactional email through Brevo's HTTP API. Keys come from the environment and are never logged."""

import json
import logging
import os
import urllib.error
import urllib.request

log = logging.getLogger("hiveout.mail")

BREVO_URL = "https://api.brevo.com/v3/smtp/email"


class MailNotConfigured(Exception):
    """No Brevo key or sender address is set."""


class MailFailed(Exception):
    """Brevo could not be reached or refused the message."""


def send_email(to: str, subject: str, text: str) -> None:
    api_key = os.getenv("BREVO_API_KEY", "")
    sender = os.getenv("MAIL_FROM_EMAIL", "")
    if not api_key or not sender:
        # In local development there is no mail service: show the message in the server log instead
        if os.getenv("APP_ENV", "development") == "development":
            log.warning("Email not configured; would have sent to %s: %s\n%s", to, subject, text)
            return
        raise MailNotConfigured("BREVO_API_KEY and MAIL_FROM_EMAIL must be set")

    payload = {
        "sender": {"email": sender, "name": os.getenv("MAIL_FROM_NAME", "HiveOut")},
        "to": [{"email": to}],
        "subject": subject,
        "textContent": text,
    }
    request = urllib.request.Request(
        BREVO_URL,
        data=json.dumps(payload).encode(),
        headers={"api-key": api_key, "content-type": "application/json", "accept": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=10).close()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise MailFailed("The email service did not accept the message") from exc
