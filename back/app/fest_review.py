"""Rules for what a fest must contain before an admin can review it."""

from typing import List

from app import models

REQUIRED_FEST_FIELDS = (
    ("name", "name"), ("tagline", "tagline"), ("description", "description"),
    ("start_date", "start date"), ("end_date", "end date"),
    ("campus_address", "campus address"), ("map_url", "map link"), ("banner_url", "banner image"),
    ("contact_name", "committee contact name"), ("contact_email", "committee contact email"), ("contact_phone", "committee contact phone"),
)


def fest_missing(fest: models.Fest, events: List[models.Event]) -> List[str]:
    """Everything that still needs filling in before the fest can be submitted. Empty list = ready."""
    missing = []
    for attr, label in REQUIRED_FEST_FIELDS:
        value = getattr(fest, attr)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(label)
    if fest.start_date and fest.end_date and fest.end_date < fest.start_date:
        missing.append("end date (it is before the start date)")

    if not events:
        missing.append("at least one event")
    for e in events:
        gaps = [label for label, value in (("venue", e.location), ("start time", e.time), ("end time", e.end_time), ("description", e.description)) if not (value or "").strip()]
        if gaps:
            missing.append(f"event '{e.title}': " + ", ".join(gaps))
        if fest.start_date and fest.end_date and not (fest.start_date <= e.date.date() <= fest.end_date):
            missing.append(f"event '{e.title}' is dated outside the fest's start and end dates")
    return missing
