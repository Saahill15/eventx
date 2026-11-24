"""Rules for what a fest must contain before an admin can review it."""

from typing import List

from app import models

# The tagline and the map link are optional: the public page builds a map link from the campus address when there is none
REQUIRED_FEST_FIELDS = (
    ("name", "name"), ("description", "description"),
    ("start_date", "start date"), ("end_date", "end date"),
    ("campus_address", "campus address"), ("banner_url", "banner image"),
    ("contact_name", "committee contact name"), ("contact_email", "committee contact email"), ("contact_phone", "committee contact phone"),
)


def dates_coming_soon(fest: models.Fest) -> bool:
    """The committee said its dates are not fixed yet (and has not entered any since)."""
    return bool(getattr(fest, "dates_tba", False)) and not (fest.start_date or fest.end_date)


def events_blocked_reason(fest: models.Fest):
    """Events are dated inside the fest's dates, so a fest listed as "dates coming soon" cannot take events yet."""
    if dates_coming_soon(fest):
        return "This fest is listed as 'Dates coming soon'. Set the fest's dates first, then add events."
    return None


def fest_missing(fest: models.Fest, events: List[models.Event]) -> List[str]:
    """Everything that still needs filling in before the fest can be submitted. Empty list = ready."""
    missing = []
    tba = dates_coming_soon(fest)
    for attr, label in REQUIRED_FEST_FIELDS:
        if tba and attr in ("start_date", "end_date"):
            continue  # "dates coming soon": listed without dates
        value = getattr(fest, attr)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(label)
    if fest.start_date and fest.end_date and fest.end_date < fest.start_date:
        missing.append("end date (it is before the start date)")

    if not events and not tba:
        missing.append("at least one event")
    for e in events:
        gaps = [label for label, value in (("venue", e.location), ("start time", e.time), ("end time", e.end_time), ("description", e.description)) if not (value or "").strip()]
        if gaps:
            missing.append(f"event '{e.title}': " + ", ".join(gaps))
        if fest.start_date and fest.end_date and not (fest.start_date <= e.date.date() <= fest.end_date):
            missing.append(f"event '{e.title}' is dated outside the fest's start and end dates")
    return missing


def _present(value) -> bool:
    return value is not None and not (isinstance(value, str) and not value.strip())


def _flags(fest: models.Fest) -> dict:
    """What the admin asked to change, by field. Only meaningful while the fest is back with the organiser."""
    if fest.review_status not in ("changes_requested", "rejected"):
        return {}
    return {f.get("key"): f.get("note") for f in (fest.review_fields or []) if isinstance(f, dict)}


def fest_checklist_items(fest: models.Fest, events: List[models.Event], member_count: int) -> List[dict]:
    """
    The same rules as fest_missing, grouped into a handful of short tasks a committee can tick off in order.
    Each task says which tab of the fest manager finishes it. The optional ones never block sending for review.
    When HiveOut sent the fest back with notes on specific fields, those notes ride along on the matching task.
    """
    missing = fest_missing(fest, events)
    tba = dates_coming_soon(fest)
    event_problems = [m for m in missing if m == "at least one event" or m.startswith("event ")]
    dates_ok = _present(fest.start_date) and _present(fest.end_date) and fest.end_date >= fest.start_date
    flags = _flags(fest)
    items = [
        {"key": "dates", "label": "Set your dates", "done": dates_ok or tba, "required": True, "tab": "details",
         "hint": "Not final yet? Choose 'Dates coming soon' and your fest is listed without dates. Add them when you know."},
        {"key": "banner", "label": "Add a banner image", "done": _present(fest.banner_url), "required": True, "tab": "details",
         "hint": "This is the first thing students see."},
        {"key": "description", "label": "Describe your fest", "done": _present(fest.description), "required": True, "tab": "details"},
        {"key": "venue", "label": "Add the campus address", "done": _present(fest.campus_address), "required": True, "tab": "details",
         "hint": "A map link is added for you."},
        {"key": "contact", "label": "Confirm a contact for HiveOut", "done": all(_present(getattr(fest, a)) for a in ("contact_name", "contact_email", "contact_phone")),
         "required": True, "tab": "details", "hint": "Private. Starts as your own details; add a phone number so we can reach you."},
        {"key": "events", "label": "Add your first event", "done": bool(events) and not event_problems, "required": not tba, "tab": "events",
         "hint": "Events need dates, so add them once your fest's dates are set." if tba else None,
         "problems": [m for m in event_problems if m != "at least one event"]},
        {"key": "team", "label": "Invite your committee", "done": member_count > 1, "required": False, "tab": "team",
         "hint": "Optional. Core members help run it; volunteers can work the gate."},
    ]
    for item in items:
        item["flag"] = flags.get(item["key"])
    return items
