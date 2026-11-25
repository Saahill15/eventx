"""How long a fest runs, and the extra things an event asks for: the days it runs, who coordinates it, when registration closes."""

from datetime import date, datetime, timedelta

from test_full import client, auth, reset_db, TestingSessionLocal, get_entry_pass  # noqa: F401
from test_organiser import Setup, FEST_DETAILS, event_payload
from test_committee_structure import Committee
from app import schedule


def manage(setup, slug="fest-one"):
    return client.get(f"/api/fests/{slug}/manage", headers=auth(setup.owner)).json()


class TestFestLength(Setup):
    """Nobody types in how many days a fest runs: it is worked out from the dates."""

    def test_two_dates_give_the_number_of_days(self):
        assert self.start(start_date="2026-12-04", end_date="2026-12-06")["days_count"] == 3

    def test_a_start_alone_is_a_one_day_fest(self):
        f = self.start(start_date="2026-12-04")
        assert f["days_count"] == 1 and f["end_date"] == "2026-12-04"

    def test_with_no_dates_there_is_no_length_and_none_is_needed(self):
        f = self.start()
        assert f["days_count"] is None

    def test_a_number_of_days_cannot_be_typed_in_it_is_ignored(self):
        f = self.start(start_date="2026-12-04", end_date="2026-12-06", days_count=9)
        assert f["days_count"] == 3 and f["end_date"] == "2026-12-06"
        r = client.patch("/api/fests/fest-one", json={"days_count": 9}, headers=auth(self.owner)).json()
        assert r["days_count"] == 3

    def test_changing_the_dates_changes_the_length(self):
        self.start(start_date="2026-12-04", end_date="2026-12-06")
        r = client.patch("/api/fests/fest-one", json={"end_date": "2026-12-08"}, headers=auth(self.owner)).json()
        assert r["days_count"] == 5
        r = client.patch("/api/fests/fest-one", json={"start_date": "2026-12-06"}, headers=auth(self.owner)).json()
        assert r["days_count"] == 3

    def test_dates_coming_soon_clears_the_length_and_asks_for_nothing_more(self):
        self.start(start_date="2026-12-04", end_date="2026-12-06")
        r = client.patch("/api/fests/fest-one", json={"dates_tba": True}, headers=auth(self.owner)).json()
        assert r["days_count"] is None and r["start_date"] is None
        missing = self.submit().json()["detail"]["missing"]
        assert not any("day" in m for m in missing)

    def test_a_fest_can_run_for_at_most_fifteen_days(self):
        r = client.post("/api/fests/", json={"slug": "x-fest", "name": "X", "college_id": self.college_id, "start_date": "2026-12-01", "end_date": "2026-12-31"}, headers=auth(self.owner))
        assert r.status_code == 422
        self.start(start_date="2026-12-01", end_date="2026-12-15")
        assert client.patch("/api/fests/fest-one", json={"end_date": "2026-12-16"}, headers=auth(self.owner)).status_code == 400

    def test_an_end_before_the_start_is_still_refused(self):
        self.start(start_date="2026-12-04", end_date="2026-12-06")
        assert client.patch("/api/fests/fest-one", json={"end_date": "2026-12-01"}, headers=auth(self.owner)).status_code == 400

    def test_the_length_shows_on_the_public_fest(self):
        self.ready_and_approved()
        client.patch("/api/fests/fest-one/status", json={"status": "live"}, headers=auth(self.owner))
        assert client.get("/api/fests/fest-one").json()["days_count"] == 3


class TestEventDetails(Setup):
    def setup_method(self):
        super().setup_method()
        self.fest = self.start(start_date="2026-12-04", end_date="2026-12-06")

    def ev(self, **kw):
        return client.post("/api/events/", json=event_payload(self.fest["id"], date="2026-12-04T00:00:00", **kw), headers=auth(self.owner))

    def test_an_event_defaults_to_one_day_with_nobody_in_charge(self):
        body = self.ev().json()
        assert body["span_days"] == 1 and body["coordinator_name"] is None and body["registration_deadline"] is None

    def test_an_event_can_run_over_several_days(self):
        assert self.ev(span_days=3).json()["span_days"] == 3

    def test_the_length_of_an_event_is_between_one_and_fifteen_days(self):
        assert self.ev(span_days=0).status_code == 422 and self.ev(span_days=16).status_code == 422

    def test_a_coordinator_is_kept(self):
        body = self.ev(coordinator_name="Meera Shah", coordinator_phone="+91 98765 43210").json()
        assert body["coordinator_name"] == "Meera Shah" and body["coordinator_phone"] == "+91 98765 43210"

    def test_a_bad_phone_number_is_refused(self):
        assert self.ev(coordinator_phone="call me").status_code == 422

    def test_a_registration_deadline_is_kept(self):
        assert self.ev(requires_registration=True, registration_deadline="2026-12-03").json()["registration_deadline"] == "2026-12-03"

    def test_registration_cannot_close_after_the_events_last_day(self):
        assert self.ev(requires_registration=True, registration_deadline="2026-12-05").status_code == 422

    def test_a_multi_day_event_can_take_registrations_until_its_last_day(self):
        assert self.ev(requires_registration=True, span_days=3, registration_deadline="2026-12-06").status_code == 200

    def test_the_new_details_can_be_changed_later(self):
        eid = self.ev().json()["id"]
        r = client.patch(f"/api/events/{eid}", json={"span_days": 2, "coordinator_name": "Ravi", "registration_deadline": "2026-12-04"}, headers=auth(self.owner))
        assert r.status_code == 200 and r.json()["span_days"] == 2 and r.json()["coordinator_name"] == "Ravi"

    def test_a_deadline_after_the_last_day_is_refused_on_change(self):
        eid = self.ev().json()["id"]
        assert client.patch(f"/api/events/{eid}", json={"registration_deadline": "2026-12-20"}, headers=auth(self.owner)).status_code == 400
        assert client.get(f"/api/events/{eid}", headers=auth(self.owner)).json()["registration_deadline"] is None

    def test_shortening_an_event_below_its_deadline_is_refused(self):
        eid = self.ev(requires_registration=True, span_days=3, registration_deadline="2026-12-06").json()["id"]
        assert client.patch(f"/api/events/{eid}", json={"span_days": 1}, headers=auth(self.owner)).status_code == 400

    def test_a_multi_day_event_must_end_inside_the_fest_to_be_reviewed(self):
        self.fill(start_date="2026-12-04", end_date="2026-12-06")
        client.post("/api/events/", json=event_payload(self.fest["id"], date="2026-12-05T00:00:00", span_days=3), headers=auth(self.owner))
        missing = self.submit().json()["detail"]["missing"]
        assert any("outside the fest" in m for m in missing)

    def test_a_multi_day_event_inside_the_fest_is_fine(self):
        self.fill(start_date="2026-12-04", end_date="2026-12-06")
        client.post("/api/events/", json=event_payload(self.fest["id"], date="2026-12-04T00:00:00", span_days=3), headers=auth(self.owner))
        assert self.submit().status_code == 200


class TestRegistrationDeadline(Setup):
    def setup_method(self):
        super().setup_method()
        self.fest = self.ready_and_approved("fest-live")
        client.patch("/api/fests/fest-live/status", json={"status": "live"}, headers=auth(self.owner))
        get_entry_pass(self.student, "fest-live")

    def event(self, deadline):
        payload = event_payload(self.fest["id"], requires_registration=True, date="2026-12-05T00:00:00")
        payload["registration_deadline"] = deadline
        r = client.post("/api/events/", json=payload, headers=auth(self.owner))
        assert r.status_code == 200, r.text
        return r.json()

    def test_registration_is_open_up_to_and_including_the_deadline(self):
        e = self.event(date.today().isoformat())
        # the deadline is today, so it is still open; the event itself is later
        e2 = client.patch(f"/api/events/{e['id']}", json={"date": f"{(date.today() + timedelta(days=5)).isoformat()}T00:00:00"}, headers=auth(self.owner))
        assert e2.status_code == 200, e2.text
        assert client.post(f"/api/fest-events/{e['id']}/register", headers=auth(self.student)).status_code == 201

    def test_registration_is_refused_after_the_deadline(self):
        e = self.event((date.today() - timedelta(days=1)).isoformat())
        r = client.post(f"/api/fest-events/{e['id']}/register", headers=auth(self.student))
        assert r.status_code == 400 and "closed on" in r.json()["detail"]

    def test_with_no_deadline_registration_stays_open(self):
        payload = event_payload(self.fest["id"], requires_registration=True, date="2026-12-05T00:00:00")
        e = client.post("/api/events/", json=payload, headers=auth(self.owner)).json()
        assert client.post(f"/api/fest-events/{e['id']}/register", headers=auth(self.student)).status_code == 201


class TestMultiDaySchedule:
    class E:
        def __init__(self, id, day, time="10:00", end="12:00", venue="Hall", span=1, cancelled=False):
            self.id, self.title, self.time, self.end_time, self.location = id, f"E{id}", time, end, venue
            self.date, self.span_days, self.cancelled, self.category = datetime.fromisoformat(day), span, cancelled, None

    def test_a_multi_day_event_appears_on_each_of_its_days(self):
        s = schedule.build_schedule([self.E(1, "2026-12-04", span=3)])
        assert [(d["date"], d["items"][0]["day_of_event"]) for d in s["days"]] == [(date(2026, 12, 4), 1), (date(2026, 12, 5), 2), (date(2026, 12, 6), 3)]

    def test_it_clashes_with_an_event_on_any_of_its_days(self):
        s = schedule.build_schedule([self.E(1, "2026-12-04", span=3), self.E(2, "2026-12-06", time="11:00", end="13:00")])
        assert len(s["clashes"]) == 1 and s["clashes"][0]["date"] == date(2026, 12, 6)
        day3 = next(d for d in s["days"] if d["date"] == date(2026, 12, 6))
        assert all(i["clash_ids"] for i in day3["items"])
        day1 = next(d for d in s["days"] if d["date"] == date(2026, 12, 4))
        assert day1["items"][0]["clash_ids"] == []

    def test_two_long_events_in_the_same_venue_clash_on_every_shared_day(self):
        s = schedule.build_schedule([self.E(1, "2026-12-04", span=3), self.E(2, "2026-12-05", span=2)])
        assert sorted(c["date"] for c in s["clashes"]) == [date(2026, 12, 5), date(2026, 12, 6)]

    def test_every_fest_day_is_listed_numbered_even_when_empty(self):
        days = [date(2026, 12, 4) + timedelta(days=i) for i in range(3)]
        s = schedule.build_schedule([self.E(1, "2026-12-05")], days)
        assert [(d["day_number"], len(d["items"])) for d in s["days"]] == [(1, 0), (2, 1), (3, 0)]

    def test_without_fest_days_only_busy_days_are_listed_and_unnumbered(self):
        s = schedule.build_schedule([self.E(1, "2026-12-05")])
        assert [d["day_number"] for d in s["days"]] == [None]

    def test_the_clash_check_looks_across_a_new_events_days(self):
        existing = [self.E(1, "2026-12-06")]
        assert schedule.clashing_with(existing, date(2026, 12, 4), "10:00", "12:00", "Hall", span_days=3) == existing
        assert schedule.clashing_with(existing, date(2026, 12, 4), "10:00", "12:00", "Hall", span_days=2) == []

    def test_the_clash_check_sees_an_existing_multi_day_event(self):
        existing = [self.E(1, "2026-12-04", span=3)]
        assert schedule.clashing_with(existing, date(2026, 12, 6), "11:00", "13:00", "hall") == existing


class TestSchedulePageShowsFestDays(Committee):
    def test_the_whole_timeline_shows_even_before_any_event_is_added(self):
        client.patch("/api/fests/fest-one", json={"start_date": "2026-12-04", "end_date": "2026-12-06"}, headers=auth(self.owner))
        s = client.get("/api/fests/fest-one/schedule", headers=auth(self.owner)).json()
        assert [(d["day_number"], d["date"]) for d in s["days"]] == [(1, "2026-12-04"), (2, "2026-12-05"), (3, "2026-12-06")]

    def test_the_clash_check_accepts_a_number_of_days(self):
        client.patch("/api/fests/fest-one", json={"start_date": "2026-12-04", "end_date": "2026-12-06"}, headers=auth(self.owner))
        fid = manage(self)["id"]
        self.add_event(fid, title="Late show", date="2026-12-06T00:00:00", time="18:00", end_time="20:00", location="Main Stage")
        r = client.get("/api/fests/fest-one/schedule/check", params={"day": "2026-12-04", "time": "19:00", "end_time": "21:00", "location": "Main Stage", "span_days": 3}, headers=auth(self.owner))
        assert [c["title"] for c in r.json()["clashes"]] == ["Late show"]
        r = client.get("/api/fests/fest-one/schedule/check", params={"day": "2026-12-04", "time": "19:00", "end_time": "21:00", "location": "Main Stage"}, headers=auth(self.owner))
        assert r.json()["clashes"] == []


class TestWhenRegistrationOpens(Setup):
    """Registration can open at once, on a chosen day, or stay "not open yet" until the committee decides."""

    def setup_method(self):
        super().setup_method()
        self.fest = self.ready_and_approved("fest-live")
        client.patch("/api/fests/fest-live/status", json={"status": "live"}, headers=auth(self.owner))
        get_entry_pass(self.student, "fest-live")
        self.event_day = date.today() + timedelta(days=10)

    def make(self, **extra):
        payload = event_payload(self.fest["id"], requires_registration=True, date=f"{self.event_day.isoformat()}T00:00:00", **extra)
        r = client.post("/api/events/", json=payload, headers=auth(self.owner))
        assert r.status_code == 200, r.text
        return r.json()

    def register(self, e):
        return client.post(f"/api/fest-events/{e['id']}/register", headers=auth(self.student))

    def day(self, offset):
        return (date.today() + timedelta(days=offset)).isoformat()

    def test_saying_nothing_keeps_registration_open_as_before(self):
        e = self.make()
        assert e["registration_state"] == "open" and self.register(e).status_code == 201

    def test_open_now_takes_registrations_at_once(self):
        e = self.make(registration_mode="open_now")
        assert e["registration_state"] == "open" and self.register(e).status_code == 201

    def test_not_decided_yet_shows_not_open_and_refuses_registration(self):
        e = self.make(registration_mode="not_set")
        assert e["registration_state"] == "not_open" and e["registration_opens_on"] is None
        r = self.register(e)
        assert r.status_code == 400 and "not open yet" in r.json()["detail"]

    def test_a_future_opening_day_is_shown_and_registration_waits_for_it(self):
        e = self.make(registration_mode="scheduled", registration_opens_on=self.day(3))
        assert e["registration_state"] == "scheduled" and e["registration_opens_on"] == self.day(3)
        r = self.register(e)
        assert r.status_code == 400 and "opens on" in r.json()["detail"]

    def test_registration_opens_by_itself_on_the_day(self):
        e = self.make(registration_mode="scheduled", registration_opens_on=self.day(0))
        assert e["registration_state"] == "open" and self.register(e).status_code == 201

    def test_a_past_opening_day_means_open(self):
        e = self.make(registration_mode="scheduled", registration_opens_on=self.day(-2))
        assert e["registration_state"] == "open"

    def test_choosing_a_day_without_giving_one_is_refused(self):
        payload = event_payload(self.fest["id"], requires_registration=True, date=f"{self.event_day.isoformat()}T00:00:00", registration_mode="scheduled")
        assert client.post("/api/events/", json=payload, headers=auth(self.owner)).status_code == 422

    def test_it_cannot_open_after_it_closes_or_after_the_event(self):
        for opens, deadline in ((self.day(6), self.day(5)), (self.day(11), None)):
            payload = event_payload(self.fest["id"], requires_registration=True, date=f"{self.event_day.isoformat()}T00:00:00", registration_mode="scheduled", registration_opens_on=opens)
            if deadline:
                payload["registration_deadline"] = deadline
            assert client.post("/api/events/", json=payload, headers=auth(self.owner)).status_code == 422

    def test_an_opening_day_is_dropped_when_the_mode_is_not_scheduled(self):
        e = self.make(registration_mode="not_set", registration_opens_on=self.day(3))
        assert e["registration_opens_on"] is None

    def test_a_closing_day_that_has_passed_closes_it(self):
        e = self.make(registration_deadline=self.day(-1))
        assert e["registration_state"] == "closed"

    def test_an_event_that_needs_no_registration_has_no_state(self):
        e = client.post("/api/events/", json=event_payload(self.fest["id"], date=f"{self.event_day.isoformat()}T00:00:00"), headers=auth(self.owner)).json()
        assert e["registration_state"] is None

    def test_the_dates_can_be_changed_later(self):
        e = self.make(registration_mode="not_set")
        r = client.patch(f"/api/events/{e['id']}", json={"registration_mode": "scheduled", "registration_opens_on": self.day(2)}, headers=auth(self.owner))
        assert r.status_code == 200 and r.json()["registration_state"] == "scheduled"
        r = client.patch(f"/api/events/{e['id']}", json={"registration_mode": "open_now"}, headers=auth(self.owner)).json()
        assert r["registration_state"] == "open" and r["registration_opens_on"] is None

    def test_a_bad_change_is_refused_and_nothing_changes(self):
        e = self.make(registration_mode="not_set")
        assert client.patch(f"/api/events/{e['id']}", json={"registration_mode": "scheduled"}, headers=auth(self.owner)).status_code == 400
        assert client.get(f"/api/events/{e['id']}", headers=auth(self.owner)).json()["registration_mode"] == "not_set"

    def test_the_dates_can_change_after_people_registered(self):
        e = self.make()
        assert self.register(e).status_code == 201
        r = client.patch(f"/api/events/{e['id']}", json={"registration_deadline": self.day(5)}, headers=auth(self.owner))
        assert r.status_code == 200

    def test_the_committee_can_open_it_now_and_close_it(self):
        e = self.make(registration_mode="scheduled", registration_opens_on=self.day(5))
        opened = client.post(f"/api/events/{e['id']}/registration", json={"action": "open"}, headers=auth(self.owner)).json()
        assert opened["registration_state"] == "open" and opened["registration_opens_on"] is None
        assert self.register(e).status_code == 201
        closed = client.post(f"/api/events/{e['id']}/registration", json={"action": "close"}, headers=auth(self.owner)).json()
        assert closed["registration_state"] == "closed"

    def test_closed_by_hand_refuses_registration_and_can_be_reopened(self):
        e = self.make()
        client.post(f"/api/events/{e['id']}/registration", json={"action": "close"}, headers=auth(self.owner))
        r = self.register(e)
        assert r.status_code == 400 and "closed" in r.json()["detail"]
        client.post(f"/api/events/{e['id']}/registration", json={"action": "open"}, headers=auth(self.owner))
        assert self.register(e).status_code == 201

    def test_it_cannot_be_reopened_once_the_closing_day_has_passed(self):
        e = self.make(registration_deadline=self.day(-1))
        r = client.post(f"/api/events/{e['id']}/registration", json={"action": "open"}, headers=auth(self.owner))
        assert r.status_code == 400 and "closing date" in r.json()["detail"]

    def test_only_the_committee_can_open_or_close_it(self):
        e = self.make(registration_mode="not_set")
        assert client.post(f"/api/events/{e['id']}/registration", json={"action": "open"}, headers=auth(self.student)).status_code == 403
        assert client.post(f"/api/events/{e['id']}/registration", json={"action": "open"}).status_code == 401

    def test_an_event_without_registration_cannot_be_opened(self):
        e = client.post("/api/events/", json=event_payload(self.fest["id"], date=f"{self.event_day.isoformat()}T00:00:00"), headers=auth(self.owner)).json()
        assert client.post(f"/api/events/{e['id']}/registration", json={"action": "open"}, headers=auth(self.owner)).status_code == 400

    def test_team_registration_also_waits(self):
        e = self.make(registration_mode="not_set", is_team_event=True, team_min=2, team_max=4)
        r = client.post(f"/api/fest-events/{e['id']}/teams", json={"name": "Alpha"}, headers=auth(self.student))
        assert r.status_code == 400 and "not open yet" in r.json()["detail"]
