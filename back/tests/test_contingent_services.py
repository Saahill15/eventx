"""Visiting colleges in the fest: entering events, accommodation, and what they pay."""

from datetime import date, datetime, timedelta

from test_fixes import user_token  # noqa: F401
from test_full import client, auth, reset_db, TestingSessionLocal  # noqa: F401
from test_contingents import Visiting
from test_organiser import event_payload
from test_committee_meetings import notices_for
from app import models

SLUG = "fest-one"


def day(n):
    return (date.today() + timedelta(days=n)).isoformat()


class Services(Visiting):
    """A live fest taking visiting colleges, with two approved contingents, each with a few people on its list."""

    def setup_method(self):
        super().setup_method()
        self.settings(allow_multiple_per_college=True)
        self.a = self.approved(self.cl, "IIT Delhi")
        self.b = self.approved(self.cl2, "NIT Surat")
        self.people = {"a": [self.person(self.cl, self.a, n) for n in ("Asha", "Ravi", "Meena", "Kabir")],
                       "b": [self.person(self.cl2, self.b, n) for n in ("Dev", "Isha")]}

    def approved(self, token, college):
        cid = self.register(token, college).json()["id"]
        assert self.go("POST", f"/{cid}/approve").status_code == 200
        return cid

    def person(self, token, cid, name):
        r = self.go("POST", f"/{cid}/members", token=token, json={"name": name, "phone": "+91 98765 43210"})
        assert r.status_code == 201, r.text
        return r.json()["members"][-1]["id"]

    def event(self, **extra):
        fest = client.get(f"/api/fests/{SLUG}/manage", headers=auth(self.owner)).json()
        payload = event_payload(fest["id"], contingent_entries=True, **extra)
        r = client.post("/api/events/", json=payload, headers=auth(self.owner))
        assert r.status_code == 200, r.text
        return r.json()

    def enter(self, event, members, token=None, contingent=None):
        body = {"event_id": event["id"], "member_ids": members}
        if contingent:
            body["contingent_id"] = contingent
        return client.post(f"/api/fests/{SLUG}/entries", json=body, headers=auth(token or self.cl))

    def mine(self, token=None):
        r = client.get(f"/api/fests/{SLUG}/entries/mine", headers=auth(token or self.cl))
        assert r.status_code == 200, r.text
        return r.json()


# ─── entering events ─────────────────────────────────────────────────────────

class TestEventSettings(Services):
    def test_an_event_can_be_opened_to_visiting_colleges_with_its_own_rules(self):
        e = self.event(entries_per_contingent=2, entry_fee=250.5, entry_fee_per="participant", entry_deadline="2026-12-04")
        assert e["contingent_entries"] is True and e["entries_per_contingent"] == 2 and e["entry_fee"] == 250.5 and e["entry_fee_per"] == "participant" and e["entry_deadline"] == "2026-12-04"

    def test_by_default_an_event_is_not_open_to_them(self):
        fest = client.get(f"/api/fests/{SLUG}/manage", headers=auth(self.owner)).json()
        e = client.post("/api/events/", json=event_payload(fest["id"]), headers=auth(self.owner)).json()
        assert e["contingent_entries"] is False and e["entry_fee"] == 0 and e["entries_per_contingent"] == 1

    def test_the_rules_can_be_changed_later(self):
        e = self.event()
        r = client.patch(f"/api/events/{e['id']}", json={"entries_per_contingent": 3, "entry_fee": 100, "entry_deadline": "2026-12-03"}, headers=auth(self.owner)).json()
        assert r["entries_per_contingent"] == 3 and r["entry_fee"] == 100 and r["entry_deadline"] == "2026-12-03"

    def test_the_deadline_cannot_be_after_the_events_last_day(self):
        fest = client.get(f"/api/fests/{SLUG}/manage", headers=auth(self.owner)).json()
        r = client.post("/api/events/", json=event_payload(fest["id"], contingent_entries=True, entry_deadline="2026-12-20"), headers=auth(self.owner))
        assert r.status_code == 422
        e = self.event()
        assert client.patch(f"/api/events/{e['id']}", json={"entry_deadline": "2026-12-20"}, headers=auth(self.owner)).status_code == 400

    def test_bad_numbers_are_refused(self):
        fest = client.get(f"/api/fests/{SLUG}/manage", headers=auth(self.owner)).json()
        for bad in ({"entries_per_contingent": 0}, {"entry_fee": -1}, {"entry_fee_per": "head"}):
            assert client.post("/api/events/", json=event_payload(fest["id"], **bad), headers=auth(self.owner)).status_code == 422


class TestEntering(Services):
    def test_a_leader_sees_the_events_they_can_enter(self):
        self.event(title="Quiz")
        fest = client.get(f"/api/fests/{SLUG}/manage", headers=auth(self.owner)).json()
        client.post("/api/events/", json=event_payload(fest["id"], title="Closed to colleges"), headers=auth(self.owner))
        m = self.mine()
        assert [e["title"] for e in m["events"]] == ["Quiz"] and m["events"][0]["open"] is True

    def test_a_solo_event_takes_one_person_per_entry(self):
        e = self.event()
        r = self.enter(e, [self.people["a"][0]])
        assert r.status_code == 201 and [m["name"] for m in r.json()["members"]] == ["Asha"] and r.json()["status"] == "confirmed"
        assert self.enter(e, self.people["a"][1:3]).status_code == 400  # two people in one solo entry
        assert client.post(f"/api/fests/{SLUG}/entries", json={"event_id": e["id"], "member_ids": []}, headers=auth(self.cl)).status_code == 422

    def test_a_team_event_takes_a_team_within_its_size(self):
        e = self.event(is_team_event=True, team_min=2, team_max=3, requires_registration=True)
        assert self.enter(e, self.people["a"][:1]).status_code == 400
        assert self.enter(e, self.people["a"][:4]).status_code == 400
        assert self.enter(e, self.people["a"][:3]).status_code == 201

    def test_only_people_on_the_contingents_own_list_can_take_part(self):
        e = self.event()
        assert self.enter(e, [self.people["b"][0]]).status_code == 400
        assert self.enter(e, [999999]).status_code == 400

    def test_a_person_cannot_be_in_two_entries_of_the_same_event_and_the_limit_is_kept(self):
        e = self.event(entries_per_contingent=2)
        assert self.enter(e, [self.people["a"][0]]).status_code == 201
        assert self.enter(e, [self.people["a"][0]]).status_code == 400
        assert self.enter(e, [self.people["a"][1]]).status_code == 201
        r = self.enter(e, [self.people["a"][2]])
        assert r.status_code == 400 and "2 entries" in r.json()["detail"]

    def test_withdrawing_frees_the_slot(self):
        e = self.event()
        entry = self.enter(e, [self.people["a"][0]]).json()
        assert client.delete(f"/api/fests/{SLUG}/entries/{entry['id']}", headers=auth(self.cl)).json()["status"] == "withdrawn"
        assert self.enter(e, [self.people["a"][1]]).status_code == 201

    def test_who_takes_part_can_be_changed(self):
        e = self.event()
        entry = self.enter(e, [self.people["a"][0]]).json()
        r = client.put(f"/api/fests/{SLUG}/entries/{entry['id']}", json={"member_ids": [self.people["a"][1]]}, headers=auth(self.cl))
        assert r.status_code == 200 and [m["name"] for m in r.json()["members"]] == ["Ravi"]
        assert client.put(f"/api/fests/{SLUG}/entries/{entry['id']}", json={"member_ids": self.people["a"][:2]}, headers=auth(self.cl)).status_code == 400

    def test_a_person_in_two_events_at_the_same_time_gets_a_warning(self):
        e1 = self.event(title="One", time="10:00", end_time="12:00")
        e2 = self.event(title="Two", time="11:00", end_time="13:00")
        self.enter(e1, [self.people["a"][0]])
        r = self.enter(e2, [self.people["a"][0]])
        assert r.status_code == 201 and any("Asha" in w and "One" in w for w in r.json()["warnings"])

    def test_events_at_different_times_raise_no_warning(self):
        e1 = self.event(title="One", time="09:00", end_time="10:00")
        e2 = self.event(title="Two", time="11:00", end_time="12:00")
        self.enter(e1, [self.people["a"][0]])
        assert self.enter(e2, [self.people["a"][0]]).json()["warnings"] == []

    def test_after_the_deadline_a_leader_cannot_enter_but_the_committee_can(self):
        e = self.event()
        db = TestingSessionLocal()
        db.query(models.Event).filter(models.Event.id == e["id"]).update({"entry_deadline": date.today() - timedelta(days=1)})
        db.commit(); db.close()
        r = self.enter(e, [self.people["a"][0]])
        assert r.status_code == 400 and "closed on" in r.json()["detail"]
        assert self.mine()["events"][0]["open"] is False
        assert self.enter(e, [self.people["a"][0]], token=self.owner, contingent=self.a).status_code == 201

    def test_a_leader_cannot_withdraw_after_the_deadline(self):
        e = self.event()
        entry = self.enter(e, [self.people["a"][0]]).json()
        db = TestingSessionLocal()
        db.query(models.Event).filter(models.Event.id == e["id"]).update({"entry_deadline": date.today() - timedelta(days=1)})
        db.commit(); db.close()
        assert client.delete(f"/api/fests/{SLUG}/entries/{entry['id']}", headers=auth(self.cl)).status_code == 400

    def test_an_event_not_open_to_colleges_or_cancelled_cannot_be_entered(self):
        fest = client.get(f"/api/fests/{SLUG}/manage", headers=auth(self.owner)).json()
        closed = client.post("/api/events/", json=event_payload(fest["id"]), headers=auth(self.owner)).json()
        assert self.enter(closed, [self.people["a"][0]]).status_code == 400
        e = self.event()
        client.post(f"/api/events/{e['id']}/cancel", json={"reason": "Rain"}, headers=auth(self.owner))
        assert self.enter(e, [self.people["a"][0]]).status_code == 400

    def test_a_contingent_not_yet_approved_cannot_enter(self):
        pending = self.register(self.stranger, "IIT Madras").json()["id"]
        e = self.event()
        r = client.post(f"/api/fests/{SLUG}/entries", json={"event_id": e["id"], "member_ids": [1]}, headers=auth(self.stranger))
        assert r.status_code == 403 and pending

    def test_a_disqualified_contingent_cannot_enter(self):
        self.go  # the competition's penalty route
        client.post(f"/api/fests/{SLUG}/competition/penalties", json={"contingent_id": self.a, "disqualified": True, "reason": "Cheating"}, headers=auth(self.owner))
        e = self.event()
        assert self.enter(e, [self.people["a"][0]]).status_code == 400

    def test_a_leader_cannot_enter_for_another_contingent(self):
        e = self.event()
        assert self.enter(e, [self.people["b"][0]], token=self.cl, contingent=self.b).status_code == 403

    def test_an_assistant_can_enter_for_the_contingent(self):
        assert self.go("POST", f"/{self.a}/assistants", json={"email": "acl@test.com"}).status_code == 201
        e = self.event()
        assert self.enter(e, [self.people["a"][0]], token=self.acl).status_code == 201

    def test_strangers_cannot_enter_or_see_entries(self):
        e = self.event()
        assert self.enter(e, [1], token=self.student).status_code == 403
        assert client.get(f"/api/fests/{SLUG}/entries/mine", headers=auth(self.student)).json() is None
        assert client.get(f"/api/fests/{SLUG}/entries", headers=auth(self.cl)).status_code == 403

    def test_the_committee_must_say_which_contingent_when_entering(self):
        e = self.event()
        r = client.post(f"/api/fests/{SLUG}/entries", json={"event_id": e["id"], "member_ids": [self.people["a"][0]]}, headers=auth(self.owner))
        assert r.status_code == 400

    def test_the_committee_sees_every_entry_and_can_filter_by_event(self):
        e1 = self.event(title="One"); e2 = self.event(title="Two")
        self.enter(e1, [self.people["a"][0]]); self.enter(e2, [self.people["a"][1]]); self.enter(e1, [self.people["b"][0]], token=self.cl2)
        rows = client.get(f"/api/fests/{SLUG}/entries", headers=auth(self.owner)).json()
        assert len(rows) == 3
        only = client.get(f"/api/fests/{SLUG}/entries?event_id={e1['id']}", headers=auth(self.owner)).json()
        assert {r["contingent_label"] for r in only} == {"IIT Delhi", "NIT Surat"} and all(r["members"][0]["phone"] for r in only)

    def test_a_leader_sees_only_their_own_entries(self):
        e = self.event()
        self.enter(e, [self.people["a"][0]]); self.enter(e, [self.people["b"][0]], token=self.cl2)
        assert [x["contingent_id"] for x in self.mine()["entries"]] == [self.a]

    def test_removing_an_entry_tells_the_leader_why(self):
        e = self.event()
        entry = self.enter(e, [self.people["a"][0]]).json()
        r = client.delete(f"/api/fests/{SLUG}/entries/{entry['id']}?reason=Not%20eligible", headers=auth(self.owner)).json()
        assert r["status"] == "removed" and r["note"] == "Not eligible"
        assert any("Not eligible" in body for _, body in notices_for("cl@test.com", "contingent"))

    def test_another_contingents_entry_is_not_reachable(self):
        e = self.event()
        entry = self.enter(e, [self.people["a"][0]]).json()
        assert client.delete(f"/api/fests/{SLUG}/entries/{entry['id']}", headers=auth(self.cl2)).status_code == 403
        assert client.put(f"/api/fests/{SLUG}/entries/{entry['id']}", json={"member_ids": [self.people["b"][0]]}, headers=auth(self.cl2)).status_code == 403


# ─── accommodation ───────────────────────────────────────────────────────────

class TestAccommodation(Services):
    def acc(self, method, path, token=None, **kw):
        return client.request(method, f"/api/fests/{SLUG}/accommodation{path}", headers=auth(token or self.owner), **kw)

    def open_it(self, **extra):
        assert self.acc("PUT", "/settings", json={"enabled": True, **extra}).status_code == 200

    def place(self, name="Hostel A", capacity=10, policy="any", fee=100.0):
        r = self.acc("POST", "/options", json={"name": name, "capacity": capacity, "gender_policy": policy, "fee_per_night": fee})
        assert r.status_code == 201, r.text
        return r.json()

    def ask(self, token=None, **extra):
        body = {"boys": 2, "girls": 1, "others": 0, "arrival_date": day(5), "departure_date": day(8), **extra}
        return self.acc("PUT", "/mine", token or self.cl, json=body)

    def test_switched_off_until_the_committee_turns_it_on(self):
        assert self.acc("GET", "/settings", self.cl).json()["open"] is False
        r = self.ask()
        assert r.status_code == 400 and "not open" in r.json()["detail"]

    def test_the_closing_date_shuts_it(self):
        self.open_it(closes_on=day(-1))
        assert self.acc("GET", "/settings", self.cl).json()["open"] is False
        assert self.ask().status_code == 400
        self.acc("PUT", "/settings", json={"closes_on": day(3)})
        assert self.ask().status_code == 200

    def test_only_the_committee_changes_the_settings(self):
        assert self.acc("PUT", "/settings", self.cl, json={"enabled": True}).status_code == 403

    def test_a_request_says_how_many_and_which_nights(self):
        self.open_it()
        r = self.ask()
        body = r.json()
        assert r.status_code == 200 and body["people"] == 3 and body["nights"] == 3 and body["status"] == "requested" and body["unplaced"] == {"boys": 2, "girls": 1, "others": 0}

    def test_a_request_must_make_sense(self):
        self.open_it()
        assert self.ask(boys=0, girls=0, others=0).status_code == 422
        assert self.ask(arrival_date=day(8), departure_date=day(5)).status_code == 422
        assert self.ask(arrival_date=day(1), departure_date=day(40)).status_code == 422

    def test_a_request_can_be_changed_until_it_is_placed(self):
        self.open_it()
        self.ask()
        r = self.ask(boys=4)
        assert r.json()["boys"] == 4

    def test_the_committee_lists_places_with_capacity_gender_and_price(self):
        self.place("Boys hostel", 20, "boys", 150.5)
        o = self.acc("GET", "/options").json()[0]
        assert o["capacity"] == 20 and o["gender_policy"] == "boys" and o["fee_per_night"] == 150.5 and o["free"] == 20

    def test_leaders_cannot_manage_places_or_see_every_request(self):
        assert self.acc("POST", "/options", self.cl, json={"name": "x", "capacity": 1}).status_code == 403
        assert self.acc("GET", "/options", self.cl).status_code == 403
        assert self.acc("GET", "/requests", self.cl).status_code == 403

    def test_placing_people_marks_the_request_placed_and_tells_the_leader(self):
        self.open_it()
        hostel = self.place(capacity=10)
        rid = self.ask().json()["id"]
        r = self.acc("PUT", f"/requests/{rid}/allocations", json={"allocations": [{"option_id": hostel["id"], "group": "boys", "people": 2}, {"option_id": hostel["id"], "group": "girls", "people": 1}]})
        body = r.json()
        assert r.status_code == 200 and body["status"] == "allocated" and body["unplaced"] == {"boys": 0, "girls": 0, "others": 0}
        assert body["fee"] == 900.0  # 3 people x 3 nights x 100
        assert any("arranged" in t for t, _ in notices_for("cl@test.com", "contingent"))
        assert self.acc("GET", "/options").json()[0]["free"] == 7

    def test_partial_placing_shows_who_is_still_unplaced(self):
        self.open_it()
        hostel = self.place()
        rid = self.ask().json()["id"]
        body = self.acc("PUT", f"/requests/{rid}/allocations", json={"allocations": [{"option_id": hostel["id"], "group": "boys", "people": 1}]}).json()
        assert body["unplaced"] == {"boys": 1, "girls": 1, "others": 0}

    def test_you_cannot_place_more_than_asked_or_past_capacity_or_against_the_policy(self):
        self.open_it()
        small = self.place("Small", 2)
        girls_only = self.place("Girls block", 10, "girls")
        rid = self.ask().json()["id"]
        put = lambda allocs: self.acc("PUT", f"/requests/{rid}/allocations", json={"allocations": allocs})
        assert put([{"option_id": small["id"], "group": "boys", "people": 3}]).status_code == 400   # more boys than asked
        assert put([{"option_id": small["id"], "group": "boys", "people": 2}, {"option_id": small["id"], "group": "girls", "people": 1}]).status_code == 400  # past capacity of 2
        assert put([{"option_id": girls_only["id"], "group": "boys", "people": 1}]).status_code == 400
        assert put([{"option_id": small["id"], "group": "boys", "people": 1}, {"option_id": small["id"], "group": "boys", "people": 1}]).status_code == 400

    def test_capacity_counts_everyone_placed_from_every_contingent(self):
        self.open_it()
        hostel = self.place(capacity=4)
        r1 = self.ask(self.cl, boys=3, girls=0).json()["id"]
        r2 = self.ask(self.cl2, boys=2, girls=0).json()["id"]
        assert self.acc("PUT", f"/requests/{r1}/allocations", json={"allocations": [{"option_id": hostel["id"], "group": "boys", "people": 3}]}).status_code == 200
        r = self.acc("PUT", f"/requests/{r2}/allocations", json={"allocations": [{"option_id": hostel["id"], "group": "boys", "people": 2}]})
        assert r.status_code == 400 and "room for 1" in r.json()["detail"]

    def test_placing_again_replaces_the_earlier_placing_and_frees_the_room(self):
        self.open_it()
        a = self.place("A", 5); b = self.place("B", 5)
        rid = self.ask(boys=2, girls=0).json()["id"]
        self.acc("PUT", f"/requests/{rid}/allocations", json={"allocations": [{"option_id": a["id"], "group": "boys", "people": 2}]})
        self.acc("PUT", f"/requests/{rid}/allocations", json={"allocations": [{"option_id": b["id"], "group": "boys", "people": 2}]})
        free = {o["name"]: o["free"] for o in self.acc("GET", "/options").json()}
        assert free == {"A": 5, "B": 3}

    def test_declining_needs_a_reason_clears_the_places_and_tells_the_leader(self):
        self.open_it()
        hostel = self.place()
        rid = self.ask().json()["id"]
        self.acc("PUT", f"/requests/{rid}/allocations", json={"allocations": [{"option_id": hostel["id"], "group": "boys", "people": 2}]})
        assert self.acc("POST", f"/requests/{rid}/decline", json={"note": "x"}).status_code == 422
        r = self.acc("POST", f"/requests/{rid}/decline", json={"note": "We are full that week"}).json()
        assert r["status"] == "declined" and r["allocations"] == [] and r["decision_note"] == "We are full that week"
        assert self.acc("GET", "/options").json()[0]["free"] == 10
        assert any("full that week" in b for _, b in notices_for("cl@test.com", "contingent"))

    def test_a_declined_leader_can_ask_again(self):
        self.open_it()
        rid = self.ask().json()["id"]
        self.acc("POST", f"/requests/{rid}/decline", json={"note": "No room right now"})
        assert self.ask(boys=1).json()["status"] == "requested"

    def test_once_placed_a_leader_cannot_change_it_themselves(self):
        self.open_it()
        hostel = self.place()
        rid = self.ask().json()["id"]
        self.acc("PUT", f"/requests/{rid}/allocations", json={"allocations": [{"option_id": hostel["id"], "group": "boys", "people": 2}]})
        r = self.ask(boys=9)
        assert r.status_code == 400 and "already been given" in r.json()["detail"]

    def test_cancelling_frees_the_places(self):
        self.open_it()
        hostel = self.place()
        rid = self.ask().json()["id"]
        self.acc("PUT", f"/requests/{rid}/allocations", json={"allocations": [{"option_id": hostel["id"], "group": "boys", "people": 2}]})
        assert self.acc("DELETE", "/mine", self.cl).json()["status"] == "cancelled"
        assert self.acc("GET", "/options").json()[0]["free"] == 10 and self.acc("GET", "/mine", self.cl).json()["request"] is None

    def test_a_place_with_people_in_it_cannot_be_deleted_or_shrunk(self):
        self.open_it()
        hostel = self.place(capacity=5)
        rid = self.ask(boys=3, girls=0).json()["id"]
        self.acc("PUT", f"/requests/{rid}/allocations", json={"allocations": [{"option_id": hostel["id"], "group": "boys", "people": 3}]})
        assert self.acc("DELETE", f"/options/{hostel['id']}").status_code == 400
        assert self.acc("PATCH", f"/options/{hostel['id']}", json={"capacity": 2}).status_code == 400
        assert self.acc("PATCH", f"/options/{hostel['id']}", json={"capacity": 8, "fee_per_night": 50}).json()["capacity"] == 8

    def test_strangers_cannot_ask(self):
        self.open_it()
        assert self.acc("PUT", "/mine", self.student, json={"boys": 1, "arrival_date": day(5), "departure_date": day(6)}).status_code == 403

    def test_the_committee_sees_every_request(self):
        self.open_it()
        self.ask(self.cl); self.ask(self.cl2, boys=1, girls=0)
        assert len(self.acc("GET", "/requests").json()) == 2


# ─── fees ────────────────────────────────────────────────────────────────────

class TestFees(Services):
    def fees(self, method, path="", token=None, **kw):
        return client.request(method, f"/api/fests/{SLUG}/fees{path}", headers=auth(token or self.owner), **kw)

    def statement(self, cid=None, token=None):
        r = self.fees("GET", f"/{cid or self.a}", token)
        assert r.status_code == 200, r.text
        return r.json()

    def charge(self, **fees):
        assert self.fees("PUT", "/settings", json=fees).status_code == 200

    def test_a_fest_charges_nothing_unless_it_says_so(self):
        s = self.statement()
        assert s["status"] == "no_fees" and s["total"] == 0 and s["lines"] == []

    def test_the_fests_own_charges_and_instructions_are_kept(self):
        self.charge(registration_fee=1500, fee_per_member=250.5, fee_instructions="Pay to UPI hiveout@bank", fees_due_on=day(10))
        s = self.fees("GET", "/settings").json()
        assert s["registration_fee"] == 1500 and s["fee_per_member"] == 250.5 and s["fee_instructions"] == "Pay to UPI hiveout@bank" and s["fees_due_on"] == day(10)

    def test_only_the_committee_sets_them(self):
        assert self.fees("PUT", "/settings", self.cl, json={"registration_fee": 1}).status_code == 403
        assert self.fees("GET", "/settings", self.cl).status_code == 403

    def test_negative_charges_are_refused(self):
        assert self.fees("PUT", "/settings", json={"registration_fee": -5}).status_code == 422

    def test_the_statement_adds_up_registration_people_entries_and_stay(self):
        self.charge(registration_fee=1000, fee_per_member=100)
        e1 = self.event(entry_fee=200)                                   # a flat price per entry
        e2 = self.event(is_team_event=True, team_min=2, team_max=3, requires_registration=True, entry_fee=50, entry_fee_per="participant")
        self.enter(e1, [self.people["a"][0]])
        self.enter(e2, self.people["a"][:3])
        c = TestAccommodation.__dict__  # noqa: F841  (the stay is arranged through its own routes below)
        client.put(f"/api/fests/{SLUG}/accommodation/settings", json={"enabled": True}, headers=auth(self.owner))
        hostel = client.post(f"/api/fests/{SLUG}/accommodation/options", json={"name": "Hostel", "capacity": 10, "fee_per_night": 80}, headers=auth(self.owner)).json()
        rid = client.put(f"/api/fests/{SLUG}/accommodation/mine", json={"boys": 2, "girls": 0, "others": 0, "arrival_date": day(5), "departure_date": day(7)}, headers=auth(self.cl)).json()["id"]
        client.put(f"/api/fests/{SLUG}/accommodation/requests/{rid}/allocations", json={"allocations": [{"option_id": hostel["id"], "group": "boys", "people": 2}]}, headers=auth(self.owner))
        s = self.statement()
        by_kind = {l["kind"]: l for l in s["lines"]}
        assert by_kind["registration"]["amount"] == 1000
        assert by_kind["members"]["quantity"] == 4 and by_kind["members"]["amount"] == 400
        entry_lines = [l for l in s["lines"] if l["kind"] == "entry"]
        assert sorted(l["amount"] for l in entry_lines) == [150, 200]
        assert by_kind["stay"]["quantity"] == 4 and by_kind["stay"]["amount"] == 320   # 2 people x 2 nights x 80
        assert s["total"] == 1000 + 400 + 350 + 320

    def test_withdrawing_an_entry_or_changing_the_list_changes_the_bill(self):
        self.charge(fee_per_member=100)
        e = self.event(entry_fee=200)
        entry = self.enter(e, [self.people["a"][0]]).json()
        assert self.statement()["total"] == 400 + 200
        client.delete(f"/api/fests/{SLUG}/entries/{entry['id']}", headers=auth(self.cl))
        assert self.statement()["total"] == 400
        self.go("DELETE", f"/{self.a}/members/{self.people['a'][3]}", token=self.cl)
        assert self.statement()["total"] == 300

    def test_payments_move_the_status_from_unpaid_to_part_to_paid(self):
        self.charge(registration_fee=1000)
        assert self.statement()["status"] == "unpaid"
        r = self.fees("POST", f"/{self.a}/payments", json={"amount": 400, "method": "UPI", "reference": "TXN123"}).json()
        assert r["status"] == "part" and r["paid"] == 400 and r["balance"] == 600 and r["payments"][0]["reference"] == "TXN123"
        r = self.fees("POST", f"/{self.a}/payments", json={"amount": 600}).json()
        assert r["status"] == "paid" and r["balance"] == 0
        r = self.fees("POST", f"/{self.a}/payments", json={"amount": 50}).json()
        assert r["status"] == "overpaid" and r["balance"] == -50

    def test_a_payment_can_be_deleted_and_the_leader_is_told_when_one_is_recorded(self):
        self.charge(registration_fee=1000)
        pid = self.fees("POST", f"/{self.a}/payments", json={"amount": 1000}).json()["payments"][0]["id"]
        assert any("1,000.00" in b for _, b in notices_for("cl@test.com", "contingent"))
        assert self.fees("DELETE", f"/payments/{pid}").json()["status"] == "unpaid"

    def test_payments_need_a_positive_amount(self):
        assert self.fees("POST", f"/{self.a}/payments", json={"amount": 0}).status_code == 422
        assert self.fees("POST", f"/{self.a}/payments", json={"amount": -5}).status_code == 422

    def test_the_committee_can_add_a_late_fee_or_a_waiver(self):
        self.charge(registration_fee=1000)
        s = self.fees("POST", f"/{self.a}/adjustments", json={"label": "Late registration", "amount": 200}).json()
        assert s["total"] == 1200
        s = self.fees("POST", f"/{self.a}/adjustments", json={"label": "Scholarship waiver", "amount": -500}).json()
        assert s["total"] == 700
        waiver = next(l for l in s["lines"] if l["label"] == "Scholarship waiver")
        assert self.fees("DELETE", f"/adjustments/{waiver['adjustment_id']}").json()["total"] == 1200

    def test_an_adjustment_needs_an_amount_and_a_label(self):
        assert self.fees("POST", f"/{self.a}/adjustments", json={"label": "x", "amount": 5}).status_code == 422
        assert self.fees("POST", f"/{self.a}/adjustments", json={"label": "Nothing", "amount": 0}).status_code == 422

    def test_only_the_committee_records_payments_and_adjusts(self):
        assert self.fees("POST", f"/{self.a}/payments", self.cl, json={"amount": 5}).status_code == 403
        assert self.fees("POST", f"/{self.a}/adjustments", self.cl, json={"label": "Free ride", "amount": -999}).status_code == 403
        assert self.fees("GET", "", self.cl).status_code == 403

    def test_a_leader_sees_their_own_statement_and_nobody_elses(self):
        self.charge(registration_fee=1000, fee_instructions="Pay by UPI")
        mine = self.fees("GET", "/mine", self.cl).json()
        assert mine["contingent_id"] == self.a and mine["total"] == 1000 and mine["instructions"] == "Pay by UPI"
        assert self.fees("GET", f"/{self.a}", self.cl).status_code == 200
        assert self.fees("GET", f"/{self.b}", self.cl).status_code == 403
        assert self.fees("GET", "/mine", self.student).json() is None

    def test_the_committee_sees_everyones_totals(self):
        self.charge(registration_fee=1000)
        self.fees("POST", f"/{self.a}/payments", json={"amount": 1000})
        s = self.fees("GET", "").json()
        assert s["total"] == 2000 and s["paid"] == 1000 and s["balance"] == 1000
        assert {r["college_name"]: r["status"] for r in s["rows"]} == {"IIT Delhi": "paid", "NIT Surat": "unpaid"}

    def test_the_spreadsheet_has_a_row_for_each_contingent_and_is_safe_to_open(self):
        self.charge(registration_fee=1000)
        self.go("PATCH", f"/{self.a}", token=self.cl, json={"college_name": "=HYPERLINK(\"http://evil\")"})
        r = self.fees("GET", "/export")
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
        lines = r.text.strip().splitlines()
        assert lines[0].startswith("Contingent,College") and len(lines) == 3
        assert "'=HYPERLINK" in r.text and ",=HYPERLINK" not in r.text
        assert self.fees("GET", "/export", self.cl).status_code == 403

    def test_a_fests_charges_do_not_leak_to_another_fest(self):
        self.charge(registration_fee=1000)
        self.start("fest-two")
        other = client.get("/api/fests/fest-two/fees/settings", headers=auth(self.owner)).json()
        assert other["registration_fee"] == 0


class TestDashboardHooks(Services):
    def home(self):
        return client.get("/api/dashboard", headers=auth(self.owner)).json()

    def test_accommodation_waiting_to_be_placed_shows_up(self):
        client.put(f"/api/fests/{SLUG}/accommodation/settings", json={"enabled": True}, headers=auth(self.owner))
        client.put(f"/api/fests/{SLUG}/accommodation/mine", json={"boys": 2, "arrival_date": day(5), "departure_date": day(6)}, headers=auth(self.cl))
        a = next(x for x in self.home()["attention"] if x["kind"] == "accommodation")
        assert a["title"] == "1 accommodation request to place" and a["tab"] == "colleges"

    def test_fees_past_their_due_date_show_up_until_paid(self):
        client.put(f"/api/fests/{SLUG}/fees/settings", json={"registration_fee": 1000, "fees_due_on": day(-1)}, headers=auth(self.owner))
        a = next(x for x in self.home()["attention"] if x["kind"] == "fees_overdue")
        assert "2 colleges have not paid" in a["title"]
        client.post(f"/api/fests/{SLUG}/fees/{self.a}/payments", json={"amount": 1000}, headers=auth(self.owner))
        client.post(f"/api/fests/{SLUG}/fees/{self.b}/payments", json={"amount": 1000}, headers=auth(self.owner))
        assert all(x["kind"] != "fees_overdue" for x in self.home()["attention"])

    def test_nothing_is_shown_before_the_due_date(self):
        client.put(f"/api/fests/{SLUG}/fees/settings", json={"registration_fee": 1000, "fees_due_on": day(5)}, headers=auth(self.owner))
        assert all(x["kind"] != "fees_overdue" for x in self.home()["attention"])
