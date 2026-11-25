"""The master schedule of a fest: every event by day and venue, and where two events want the same venue at the same time."""

from collections import defaultdict
from datetime import date as date_type, timedelta
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


def days_of(e) -> List[Tuple[date_type, int]]:
    """Every day an event is on, with which of its days that is (1 for the first). An event that runs several days repeats at the same times each day."""
    first = e.date.date()
    return [(first + timedelta(days=i), i + 1) for i in range(max(getattr(e, "span_days", 1) or 1, 1))]


def clashing_with(events: List, day: date_type, start: Optional[str], end: Optional[str], location: Optional[str], skip_id: Optional[int] = None, span_days: int = 1) -> List:
    """The existing events that would clash with something at this place and time, on any of the days it runs."""
    mine, key = span(start, end), venue_key(location)
    if mine is None or not key:
        return []
    wanted = {day + timedelta(days=i) for i in range(max(span_days, 1))}
    out = []
    for e in events:
        if e.id == skip_id or e.cancelled or venue_key(e.location) != key:
            continue
        if not wanted & {d for d, _ in days_of(e)}:
            continue
        theirs = span(e.time, e.end_time)
        if theirs is not None and overlaps(mine, theirs):
            out.append(e)
    return out


def build_schedule(events: List, fest_days: Optional[List[date_type]] = None) -> Dict:
    """
    Group events by day, find every pair that clashes, and list the ones that cannot be placed yet (no time or no venue).
    When the fest's days are known every one is listed, empty or not, numbered from 1: that is the timeline.
    """
    live = [e for e in events if not e.cancelled]
    clash_ids: Dict[Tuple[int, date_type], List[int]] = defaultdict(list)
    clashes = []
    for i, a in enumerate(live):
        for b in live[i + 1:]:
            if not venue_key(a.location) or venue_key(a.location) != venue_key(b.location):
                continue
            sa, sb = span(a.time, a.end_time), span(b.time, b.end_time)
            if sa is None or sb is None or not overlaps(sa, sb):
                continue
            shared = sorted({d for d, _ in days_of(a)} & {d for d, _ in days_of(b)})
            for d in shared:
                clash_ids[(a.id, d)].append(b.id)
                clash_ids[(b.id, d)].append(a.id)
                clashes.append({"date": d, "venue": " ".join(a.location.split()), "first_id": a.id, "second_id": b.id})

    def item(e, d: date_type, n: int) -> Dict:
        return {
            "id": e.id, "title": e.title, "date": d, "time": e.time, "end_time": e.end_time, "location": e.location, "category": e.category,
            "cancelled": e.cancelled, "clash_ids": clash_ids.get((e.id, d), []), "span_days": getattr(e, "span_days", 1) or 1, "day_of_event": n,
        }

    by_day: Dict[date_type, List] = defaultdict(list)
    order = lambda e: (minutes(e.time) if minutes(e.time) is not None else DAY_END + 1, e.id)  # noqa: E731
    for e in sorted(events, key=lambda e: (e.date, *order(e))):
        for d, n in days_of(e):
            by_day[d].append(item(e, d, n))
    for items in by_day.values():
        items.sort(key=lambda i: (minutes(i["time"]) if minutes(i["time"]) is not None else DAY_END + 1, i["id"]))

    numbered = {d: n + 1 for n, d in enumerate(fest_days or [])}
    every_day = sorted(set(by_day) | set(numbered))
    unscheduled = [item(e, e.date.date(), 1) for e in live if minutes(e.time) is None or not venue_key(e.location)]
    spellings: Dict[str, str] = {}
    for e in sorted(events, key=lambda e: (e.date, e.id)):
        if venue_key(e.location):
            spellings.setdefault(venue_key(e.location), " ".join(e.location.split()))  # one entry per venue, spelt the way it was first written
    return {
        "days": [{"date": d, "day_number": numbered.get(d), "items": by_day.get(d, [])} for d in every_day],
        "venues": sorted(spellings.values(), key=str.lower), "clashes": clashes, "unscheduled": unscheduled,
    }
