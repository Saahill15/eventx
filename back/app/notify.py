"""
Messages the site sends to people outside a request, such as a password reset link.

There is no mail service connected yet, so each message is written to the server log. To send real email later,
change only the functions below (for example call app.mailer.send_email); nothing else needs to know.
"""

import logging
import os

log = logging.getLogger("hiveout.notify")


def site_url() -> str:
    return os.getenv("SITE_URL", "http://localhost:3000").rstrip("/")


def show_links_in_responses() -> bool:
    """Development only: hand the link back to the page as well, so it can be tested without email.
    Needs APP_ENV=development to be set explicitly, so a server with no APP_ENV never does this."""
    return os.getenv("APP_ENV") == "development"


def send_password_reset(email: str, link: str) -> None:
    log.warning("Password reset link for %s (email is not connected yet): %s", email, link)
