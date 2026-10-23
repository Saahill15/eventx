"""Rules for custom short addresses such as hiveout.in/mood-indigo."""

import re
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app import models

MIN_LENGTH = 3
MAX_LENGTH = 40
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# A short name sits at the top level of the site, so it may not take the name of a page of the site, or anything that could
# pass for the site or its team. Add a name here whenever the website gets a new top-level page (a test fails if that is forgotten).
RESERVED_SHORT_NAMES = {
    # pages and routes of the site
    "admin", "dashboard", "events", "event", "fests", "fest", "login", "logout", "signup", "register", "forgot-password", "reset-password", "profile", "my-passes", "my-pass",
    "committee", "organiser", "organisers", "organizer", "organizers", "api", "all", "mine", "new", "search", "explore", "notifications",
    "colleges", "college", "cities", "city", "passes", "pass", "tickets", "settings", "account", "robots", "sitemap", "favicon", "static", "assets",
    # names that could pass for the site or its team
    "hiveout", "eventx", "support", "help", "about", "terms", "privacy", "contact", "pricing", "careers", "blog", "press", "security",
    "status", "docs", "app", "www", "mail", "home", "index", "null", "undefined",
}


def clean(name: str) -> str:
    return (name or "").strip().lower()


def check_name(db: Session, name: str, own: Optional[Tuple[str, int]] = None) -> Optional[str]:
    """Why this name cannot be used ('invalid', 'reserved', 'taken'), or None when it is free.
    `own` is the (type, id) asking, so holding the name already does not count as taken."""
    if not (MIN_LENGTH <= len(name) <= MAX_LENGTH) or not NAME_RE.fullmatch(name):
        return "invalid"
    if name in RESERVED_SHORT_NAMES:
        return "reserved"
    row = db.query(models.ShortLink).filter(models.ShortLink.name == name).first()
    if row and (row.target_type, row.target_id) != own:
        return "taken"
    return None


MESSAGES = {
    "invalid": f"Use {MIN_LENGTH} to {MAX_LENGTH} lowercase letters, numbers and single hyphens.",
    "reserved": "That name is used by the site itself. Please choose another.",
    "taken": "That name is already taken.",
}
