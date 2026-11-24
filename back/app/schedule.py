"""The master schedule of a fest: every event by day and venue, and where two events want the same venue at the same time."""

from collections import defaultdict
from datetime import date as date_type
from typing import Dict, List, Optional, Tuple

DAY_END = 24 * 60
DEFAULT_LENGTH = 60  # an event with no end time is assumed to take an hour


def minutes(value: Optional[str]) -> Optional[int]:
    """"14:30" -> 870. None for anything that is not a time."""
    try:
        h, m = (value or "").strip().split(":")[:2]
        h, m = int(h), int(m)
    except (ValueError, AttributeError):
        return None
    return h * 60 + m if 0 <= h < 24 and 0 <= m < 60 else None


def span(start: Optional[str], end: Optional[str]) -> Optional[Tuple[int, int]]:
    """When something starts and ends, in minutes. No end means an hour; an end at or before the start means it runs past midnight."""
    s = minutes(start)
    if s is None:
        return None
    e = minutes(end)
    if e is None:
        return s, min(s + DEFAULT_LENGTH, DAY_END)
    return (s, e) if e > s else (s, DAY_END)


def venue_key(location: Optional[str]) -> str:
    return " ".join((location or "").lower().split())


def overlaps(a: Tuple[int, int], b: Tuple[int, int]) -> bool:
    """Back-to-back is fine: one ending at 14:00 and another starting at 14:00 do not clash."""
    return a[0] < b[1] and b[0] < a[1]


def clashing_with(events: List, day: date_type, start: Optional[str], end: Optional[str], location: Optional[str], skip_id: Optional[int] = None) -> List:
    """The existing events that would clash with something at this place and time."""
    mine, key = span(start, end), venue_key(location)
    if mine is None or not key:
        return []
    out = []
    for e in events:
        if e.id == skip_id or e.cancelled or e.date.date() != day or venue_key(e.location) != key:
            continue
        theirs = span(e.time, e.end_time)
        if theirs is not None and overlaps(mine, theirs):
            out.append(e)
    return out


def build_schedule(events: List) -> Dict:
    """Group events by day, find every pair that clashes, and list the ones that cannot be placed yet (no time or no venue)."""
    live = [e for e in events if not e.cancelled]
    clash_ids: Dict[int, List[int]] = defaultdict(list)
    clashes = []
    for i, a in enumerate(live):
        for b in live[i + 1:]:
            if a.date.date() != b.date.date() or not venue_key(a.location) or venue_key(a.location) != venue_key(b.location):
                continue
            sa, sb = span(a.time, a.end_time), span(b.time, b.end_time)
            if sa is not None and sb is not None and overlaps(sa, sb):
                clash_ids[a.id].append(b.id)
                clash_ids[b.id].append(a.id)
                clashes.append({"date": a.date.date(), "venue": a.location.strip(), "first_id": a.id, "second_id": b.id})

    def item(e) -> Dict:
        return {
            "id": e.id, "title": e.title, "date": e.date.date(), "time": e.time, "end_time": e.end_time, "location": e.location,
            "category": e.category, "cancelled": e.cancelled, "clash_ids": clash_ids.get(e.id, []),
        }

    by_day: Dict[date_type, List] = defaultdict(list)
    for e in sorted(events, key=lambda e: (e.date, minutes(e.time) if minutes(e.time) is not None else DAY_END + 1, e.id)):
        by_day[e.date.date()].append(item(e))
    unscheduled = [item(e) for e in live if minutes(e.time) is None or not venue_key(e.location)]
    spellings: Dict[str, str] = {}
    for e in sorted(events, key=lambda e: (e.date, e.id)):
        if venue_key(e.location):
            spellings.setdefault(venue_key(e.location), " ".join(e.location.split()))  # one entry per venue, spelt the way it was first written
    venues = sorted(spellings.values(), key=str.lower)
    return {"days": [{"date": d, "items": items} for d, items in sorted(by_day.items())], "venues": venues, "clashes": clashes, "unscheduled": unscheduled}
