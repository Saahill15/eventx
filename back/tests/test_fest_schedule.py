"""The master schedule and clash detection."""

from datetime import date, datetime

from test_full import client, auth, reset_db, TestingSessionLocal  # noqa: F401
from test_committee_structure import Committee
from app import schedule


class FakeEvent:
    def __init__(self, id, day="2026-12-05", time=None, end=None, venue=None, cancelled=False, title="E"):
        self.id, self.title, self.time, self.end_time, self.location = id, title, time, end, venue
        self.date = datetime.fromisoformat(day)
        self.cancelled, self.category = cancelled, None


class TestTheMaths:
    def test_minutes_reads_times_and_refuses_the_rest(self):
        assert schedule.minutes("14:30") == 870 and schedule.minutes("00:00") == 0 and schedule.minutes("23:59") == 1439
        assert schedule.minutes("24:00") is None and schedule.minutes("9") is None and schedule.minutes("") is None and schedule.minutes(None) is None and schedule.minutes("ab:cd") is None

    def test_no_end_time_means_an_hour(self):
        assert schedule.span("10:00", None) == (600, 660)

    def test_an_end_at_or_before_the_start_runs_past_midnight(self):
        assert schedule.span("22:00", "01:00") == (1320, 1440) and schedule.span("10:00", "10:00") == (600, 1440)

    def test_a_late_event_with_no_end_stops_at_midnight(self):
        assert schedule.span("23:30", None) == (1410, 1440)

    def test_no_start_means_no_span(self):
        assert schedule.span(None, "12:00") is None

    def test_back_to_back_does_not_overlap_but_a_minute_does(self):
        assert not schedule.overlaps((600, 660), (660, 720))
        assert schedule.overlaps((600, 661), (660, 720))
        assert schedule.overlaps((600, 720), (630, 650))  # one inside the other

    def test_venue_names_compare_ignoring_case_and_spacing(self):
        assert schedule.venue_key("  Main   Stage ") == schedule.venue_key("main stage") and schedule.venue_key(None) == ""


class TestBuildingTheSchedule:
    def test_same_venue_overlapping_clashes_and_both_are_marked(self):
        s = schedule.build_schedule([FakeEvent(1, time="10:00", end="12:00", venue="Hall"), FakeEvent(2, time="11:00", end="13:00", venue="hall")])
        assert len(s["clashes"]) == 1
        items = {i["id"]: i for i in s["days"][0]["items"]}
        assert items[1]["clash_ids"] == [2] and items[2]["clash_ids"] == [1]

    def test_different_venues_do_not_clash(self):
        assert schedule.build_schedule([FakeEvent(1, time="10:00", end="12:00", venue="Hall A"), FakeEvent(2, time="10:00", end="12:00", venue="Hall B")])["clashes"] == []

    def test_different_days_do_not_clash(self):
        assert schedule.build_schedule([FakeEvent(1, "2026-12-05", "10:00", "12:00", "Hall"), FakeEvent(2, "2026-12-06", "10:00", "12:00", "Hall")])["clashes"] == []

    def test_back_to_back_in_one_venue_is_fine(self):
        assert schedule.build_schedule([FakeEvent(1, time="10:00", end="12:00", venue="Hall"), FakeEvent(2, time="12:00", end="14:00", venue="Hall")])["clashes"] == []

    def test_cancelled_events_never_clash(self):
        assert schedule.build_schedule([FakeEvent(1, time="10:00", end="12:00", venue="Hall"), FakeEvent(2, time="10:00", end="12:00", venue="Hall", cancelled=True)])["clashes"] == []

    def test_three_way_clash_is_reported_pairwise(self):
        s = schedule.build_schedule([FakeEvent(i, time="10:00", end="12:00", venue="Hall") for i in (1, 2, 3)])
        assert len(s["clashes"]) == 3

    def test_events_without_a_time_or_venue_are_listed_as_unscheduled_not_clashes(self):
        s = schedule.build_schedule([FakeEvent(1, venue="Hall"), FakeEvent(2, time="10:00"), FakeEvent(3, time="10:00", end="11:00", venue="Hall")])
        assert sorted(i["id"] for i in s["unscheduled"]) == [1, 2] and s["clashes"] == []

    def test_cancelled_events_are_shown_but_not_unscheduled(self):
        s = schedule.build_schedule([FakeEvent(1, cancelled=True)])
        assert s["unscheduled"] == [] and s["days"][0]["items"][0]["cancelled"] is True

    def test_days_and_times_are_in_order_with_untimed_last(self):
        s = schedule.build_schedule([FakeEvent(1, "2026-12-06", "09:00", venue="A"), FakeEvent(2, "2026-12-05", "15:00", venue="A"), FakeEvent(3, "2026-12-05", "09:00", venue="A"), FakeEvent(4, "2026-12-05", None, venue="A")])
        assert [d["date"] for d in s["days"]] == [date(2026, 12, 5), date(2026, 12, 6)]
        assert [i["id"] for i in s["days"][0]["items"]] == [3, 2, 4]

    def test_venues_are_listed_once_whatever_the_spelling(self):
        s = schedule.build_schedule([FakeEvent(1, venue="Hall"), FakeEvent(2, venue="hall "), FakeEvent(3, venue="Auditorium")])
        assert len(s["venues"]) == 2

    def test_an_empty_fest_has_an_empty_schedule(self):
        assert schedule.build_schedule([]) == {"days": [], "venues": [], "clashes": [], "unscheduled": []}


class TestTheSchedulePage(Committee):
    def setup_method(self):
        super().setup_method()
        self.fid = client.get("/api/fests/fest-one/manage", headers=auth(self.owner)).json()["id"]

    def event(self, title, time="18:00", end="20:00", location="Main Stage", day="2026-12-05", fid=None):
        return self.add_event(fid or self.fid, title=title, time=time, end_time=end, location=location, date=f"{day}T00:00:00")

    def sched(self, token=None, slug="fest-one"):
        r = client.get(f"/api/fests/{slug}/schedule", headers=auth(token or self.owner))
        assert r.status_code == 200, r.text
        return r.json()

    def test_events_are_grouped_by_day_with_their_times(self):
        self.event("Band battle")
        self.event("Quiz", day="2026-12-06", time="10:00", end="11:00", location="Room 2")
        s = self.sched()
        assert [d["date"] for d in s["days"]] == ["2026-12-05", "2026-12-06"]
        assert s["days"][0]["items"][0]["title"] == "Band battle" and s["venues"] == ["Main Stage", "Room 2"]

    def test_a_clash_is_reported_with_both_events(self):
        a = self.event("Band battle")["id"]
        b = self.event("Dance finals", time="19:00", end="21:00")["id"]
        s = self.sched()
        assert len(s["clashes"]) == 1 and {s["clashes"][0]["first_id"], s["clashes"][0]["second_id"]} == {a, b}
        assert all(i["clash_ids"] for i in s["days"][0]["items"])

    def test_a_clash_goes_away_when_one_event_is_cancelled(self):
        self.event("Band battle")
        b = self.event("Dance finals", time="19:00", end="21:00")["id"]
        client.post(f"/api/events/{b}/cancel", json={}, headers=auth(self.owner))
        assert self.sched()["clashes"] == []

    def test_every_committee_member_can_see_it_and_strangers_cannot(self):
        self.event("Band battle")
        for token in (self.owner, self.core, self.vol, self.admin):
            assert len(self.sched(token)["days"]) == 1
        assert client.get("/api/fests/fest-one/schedule", headers=auth(self.student)).status_code == 403

    def test_another_fests_events_never_appear(self):
        other = self.start("fest-two")
        self.event("Elsewhere", fid=other["id"])
        assert self.sched()["days"] == []

    def test_an_unknown_fest_is_not_found(self):
        assert client.get("/api/fests/nope/schedule", headers=auth(self.owner)).status_code == 404


class TestCheckingBeforeSaving(Committee):
    def setup_method(self):
        super().setup_method()
        self.fid = client.get("/api/fests/fest-one/manage", headers=auth(self.owner)).json()["id"]
        self.band = self.add_event(self.fid, title="Band battle", time="18:00", end_time="20:00", location="Main Stage", date="2026-12-05T00:00:00")["id"]

    def check(self, token=None, **q):
        params = {"day": "2026-12-05", "time": "19:00", "end_time": "21:00", "location": "Main Stage", **q}
        params = {k: v for k, v in params.items() if v is not None}
        return client.get("/api/fests/fest-one/schedule/check", params=params, headers=auth(token or self.owner))

    def test_it_names_the_event_that_would_clash(self):
        r = self.check()
        assert r.status_code == 200 and [c["title"] for c in r.json()["clashes"]] == ["Band battle"]

    def test_a_free_slot_has_no_clashes(self):
        assert self.check(time="20:00", end_time="22:00").json()["clashes"] == []
        assert self.check(location="Room 2").json()["clashes"] == []
        assert self.check(day="2026-12-06").json()["clashes"] == []

    def test_an_event_does_not_clash_with_itself(self):
        assert self.check(exclude_event_id=self.band).json()["clashes"] == []

    def test_no_venue_or_no_time_cannot_clash(self):
        assert self.check(location=None).json()["clashes"] == []
        assert self.check(time=None, end_time=None).json()["clashes"] == []

    def test_venue_spelling_does_not_matter(self):
        assert len(self.check(location="  main   stage").json()["clashes"]) == 1

    def test_a_missing_day_is_refused(self):
        r = client.get("/api/fests/fest-one/schedule/check", params={"time": "10:00"}, headers=auth(self.owner))
        assert r.status_code == 422

    def test_strangers_cannot_check(self):
        assert self.check(token=self.student).status_code == 403
