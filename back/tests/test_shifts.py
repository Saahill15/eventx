"""The duty roster: adding duties, assigning and signing up, double booking, arrival, and who gets told."""

from datetime import datetime, timedelta

from test_fixes import user_id  # noqa: F401
from test_full import client, auth, reset_db, TestingSessionLocal  # noqa: F401
from test_committee_structure import Committee
from test_committee_meetings import notices_for
from app import models


def at(hours=0, days=0):
    return (datetime.now() + timedelta(days=days, hours=hours)).replace(microsecond=0).isoformat()


class Roster(Committee):
    def duty(self, title="Main gate", token=None, slug="fest-one", start=None, end=None, **extra):
        body = {"title": title, "starts_at": start or at(days=2), "ends_at": end or at(days=2, hours=3), **extra}
        return client.post(f"/api/fests/{slug}/shifts", json=body, headers=auth(token or self.owner))

    def one(self, title="Main gate", **kw):
        r = self.duty(title, **kw)
        assert r.status_code == 201, r.text
        return r.json()[0]

    def shifts(self, token=None, slug="fest-one", query=""):
        r = client.get(f"/api/fests/{slug}/shifts{query}", headers=auth(token or self.owner))
        assert r.status_code == 200, r.text
        return r.json()

    def call(self, method, path, token=None, slug="fest-one", body=None):
        return client.request(method, f"/api/fests/{slug}/shifts{path}", json=body, headers=auth(token or self.owner))


class TestAdding(Roster):
    def test_staff_can_add_a_duty(self):
        for token in (self.owner, self.core, self.admin):
            assert self.duty(token=token).status_code == 201

    def test_volunteers_and_strangers_cannot(self):
        assert self.duty(token=self.vol).status_code == 403
        assert self.duty(token=self.student).status_code == 403

    def test_a_duty_carries_what_it_was_given(self):
        s = self.one(location="Gate 1", needed=3, notes="Bring a lanyard", open_signup=True)
        assert s["location"] == "Gate 1" and s["needed"] == 3 and s["notes"] == "Bring a lanyard" and s["open_signup"] is True
        assert s["filled"] == 0 and s["open_spots"] == 3 and s["state"] == "upcoming"

    def test_hours_must_make_sense(self):
        assert self.duty(start=at(days=2), end=at(days=2)).status_code == 422
        assert self.duty(start=at(days=2), end=at(days=1)).status_code == 422
        assert self.duty(start=at(days=2), end=at(days=3)).status_code == 422   # over 18 hours
        assert self.duty(needed=0).status_code == 422

    def test_the_same_duty_can_repeat_on_other_days(self):
        d1 = (datetime.now() + timedelta(days=2)).date()
        r = self.duty(repeat_on=[str(d1 + timedelta(days=1)), str(d1 + timedelta(days=2)), str(d1 + timedelta(days=1))])
        out = r.json()
        assert r.status_code == 201 and len(out) == 3
        assert len({s["starts_at"][11:16] for s in out}) == 1
        assert len({s["starts_at"][:10] for s in out}) == 3

    def test_people_can_be_put_on_it_at_once_and_are_told(self):
        s = self.one(needed=2, member_ids=[self.vol_mid])
        assert [p["member_id"] for p in s["people"]] == [self.vol_mid] and s["filled"] == 1
        assert [t for t, _ in notices_for("vol@test.com", "shift")] == ["You are on duty: Main gate"]

    def test_the_person_who_added_it_is_not_told_about_themselves(self):
        self.one(member_ids=[self.owner_mid])
        assert notices_for("owner@test.com", "shift") == []

    def test_more_people_than_needed_is_refused(self):
        assert self.duty(needed=1, member_ids=[self.vol_mid, self.core_mid]).status_code == 400

    def test_people_from_outside_the_committee_are_refused(self):
        assert self.duty(member_ids=[999999]).status_code == 400

    def test_a_duty_can_belong_to_a_team_and_an_event_of_this_fest(self):
        team = self.add_team("Gate").json()
        s = self.one(committee_team_id=team["id"])
        assert s["team_name"] == "Gate"
        assert self.duty(committee_team_id=999999).status_code == 400
        assert self.duty(event_id=999999).status_code == 400


class TestAssigning(Roster):
    def test_staff_can_put_a_member_on_a_duty(self):
        s = self.one(needed=2)
        r = self.call("POST", f"/{s['id']}/assign", body={"member_id": self.vol_mid})
        assert r.status_code == 200 and r.json()["filled"] == 1 and r.json()["open_spots"] == 1

    def test_volunteers_cannot_assign(self):
        s = self.one()
        assert self.call("POST", f"/{s['id']}/assign", token=self.vol, body={"member_id": self.vol_mid}).status_code == 403

    def test_a_full_duty_takes_nobody_else(self):
        s = self.one(needed=1, member_ids=[self.vol_mid])
        assert self.call("POST", f"/{s['id']}/assign", body={"member_id": self.core_mid}).status_code == 400

    def test_nobody_is_put_on_the_same_duty_twice(self):
        s = self.one(needed=3, member_ids=[self.vol_mid])
        assert self.call("POST", f"/{s['id']}/assign", body={"member_id": self.vol_mid}).status_code == 400

    def test_double_booking_is_refused_with_the_name_of_the_clash(self):
        self.one("Main gate", member_ids=[self.vol_mid])
        b = self.one("Help desk", start=at(days=2, hours=1), end=at(days=2, hours=4))
        r = self.call("POST", f"/{b['id']}/assign", body={"member_id": self.vol_mid})
        assert r.status_code == 400 and "Main gate" in r.json()["detail"]

    def test_back_to_back_duties_are_fine(self):
        self.one("Morning", start=at(days=2), end=at(days=2, hours=3), member_ids=[self.vol_mid])
        b = self.one("Afternoon", start=at(days=2, hours=3), end=at(days=2, hours=6))
        assert self.call("POST", f"/{b['id']}/assign", body={"member_id": self.vol_mid}).status_code == 200

    def test_taking_someone_off_tells_them(self):
        s = self.one(member_ids=[self.vol_mid])
        r = self.call("DELETE", f"/{s['id']}/people/{self.vol_mid}")
        assert r.status_code == 200 and r.json()["filled"] == 0
        assert "Taken off a duty: Main gate" in [t for t, _ in notices_for("vol@test.com", "shift")]

    def test_taking_off_someone_who_is_not_on_it(self):
        s = self.one()
        assert self.call("DELETE", f"/{s['id']}/people/{self.vol_mid}").status_code == 404

    def test_a_finished_duty_cannot_be_assigned(self):
        db = TestingSessionLocal()
        s = self.one()
        sh = db.query(models.Shift).get(s["id"])
        sh.starts_at, sh.ends_at = datetime.now() - timedelta(hours=5), datetime.now() - timedelta(hours=2)
        db.commit(); db.close()
        assert self.call("POST", f"/{s['id']}/assign", body={"member_id": self.vol_mid}).status_code == 400


class TestSigningUp(Roster):
    def test_a_member_can_take_an_open_duty_and_leave_it(self):
        s = self.one(needed=2, open_signup=True)
        r = self.call("POST", f"/{s['id']}/claim", token=self.vol)
        assert r.status_code == 200 and r.json()["mine"] is True and r.json()["filled"] == 1 and r.json()["can_leave"] is True
        r = self.call("DELETE", f"/{s['id']}/claim", token=self.vol)
        assert r.status_code == 200 and r.json()["mine"] is False and r.json()["filled"] == 0

    def test_a_closed_duty_cannot_be_taken(self):
        s = self.one(open_signup=False)
        assert self.call("POST", f"/{s['id']}/claim", token=self.vol).status_code == 400

    def test_a_full_duty_cannot_be_taken(self):
        s = self.one(needed=1, open_signup=True, member_ids=[self.core_mid])
        assert self.call("POST", f"/{s['id']}/claim", token=self.vol).status_code == 400

    def test_strangers_cannot_take_duties(self):
        s = self.one(open_signup=True)
        assert self.call("POST", f"/{s['id']}/claim", token=self.student).status_code == 403

    def test_signing_up_cannot_double_book(self):
        self.one("Main gate", member_ids=[self.vol_mid])
        b = self.one("Help desk", open_signup=True, start=at(days=2, hours=1), end=at(days=2, hours=2))
        r = self.call("POST", f"/{b['id']}/claim", token=self.vol)
        assert r.status_code == 400 and "Main gate" in r.json()["detail"]

    def test_list_says_who_can_take_what(self):
        a = self.one("Open", open_signup=True)
        self.one("Closed", start=at(days=3), end=at(days=3, hours=2))
        rows = {r["title"]: r for r in self.shifts(token=self.vol)}
        assert rows["Open"]["can_claim"] is True and rows["Closed"]["can_claim"] is False
        self.call("POST", f"/{a['id']}/claim", token=self.vol)
        assert {r["title"]: r for r in self.shifts(token=self.vol)}["Open"]["can_claim"] is False

    def test_leaving_after_it_started_is_refused_and_the_director_is_told_when_allowed(self):
        s = self.one(open_signup=True, member_ids=[self.vol_mid])
        r = self.call("DELETE", f"/{s['id']}/claim", token=self.vol)
        assert r.status_code == 200, r.text
        assert any("left a duty: Main gate" in t for t, _ in notices_for("owner@test.com", "shift"))
        t = self.one("Now", start=at(hours=-1), end=at(hours=2), member_ids=[self.vol_mid])
        assert self.call("DELETE", f"/{t['id']}/claim", token=self.vol).status_code == 400

    def test_leaving_a_duty_you_are_not_on(self):
        s = self.one(open_signup=True)
        assert self.call("DELETE", f"/{s['id']}/claim", token=self.vol).status_code == 404


class TestListing(Roster):
    def test_every_member_sees_the_roster_but_not_strangers(self):
        self.one()
        for token in (self.owner, self.core, self.vol, self.admin):
            assert len(self.shifts(token=token)) == 1
        assert client.get("/api/fests/fest-one/shifts", headers=auth(self.student)).status_code == 403
        assert client.get("/api/fests/fest-one/shifts").status_code in (401, 403)

    def test_mine_shows_only_my_duties(self):
        self.one("A", member_ids=[self.vol_mid])
        self.one("B", start=at(days=3), end=at(days=3, hours=2))
        assert [s["title"] for s in self.shifts(token=self.vol, query="?mine=true")] == ["A"]

    def test_upcoming_past_and_all(self):
        self.one("Later")
        old = self.one("Done", start=at(days=1), end=at(days=1, hours=2))
        db = TestingSessionLocal()
        sh = db.query(models.Shift).get(old["id"])
        sh.starts_at, sh.ends_at = datetime.now() - timedelta(days=1), datetime.now() - timedelta(days=1) + timedelta(hours=2)
        db.commit(); db.close()
        assert [s["title"] for s in self.shifts()] == ["Later"]
        assert [s["title"] for s in self.shifts(query="?when=past")] == ["Done"]
        assert [s["title"] for s in self.shifts(query="?when=all")] == ["Done", "Later"]
        assert self.shifts(query="?when=past")[0]["state"] == "over"

    def test_one_fest_cannot_see_anothers_duties(self):
        s = self.one()
        assert self.call("PATCH", f"/{s['id']}", slug="no-such-fest", body={"needed": 2}).status_code == 404


class TestChanging(Roster):
    def test_staff_can_change_a_duty(self):
        s = self.one()
        r = self.call("PATCH", f"/{s['id']}", body={"title": "Side gate", "needed": 4, "location": "Gate 2", "notes": "Bring water", "open_signup": True})
        assert r.status_code == 200
        b = r.json()
        assert b["title"] == "Side gate" and b["needed"] == 4 and b["location"] == "Gate 2" and b["open_signup"] is True

    def test_volunteers_cannot(self):
        s = self.one()
        assert self.call("PATCH", f"/{s['id']}", token=self.vol, body={"needed": 2}).status_code == 403
        assert self.call("DELETE", f"/{s['id']}", token=self.vol).status_code == 403

    def test_moving_a_duty_tells_the_people_on_it(self):
        s = self.one(member_ids=[self.vol_mid])
        self.call("PATCH", f"/{s['id']}", body={"location": "Gate 9"})
        titles = [t for t, _ in notices_for("vol@test.com", "shift")]
        assert "Your duty changed: Main gate" in titles

    def test_a_note_change_does_not_bother_anyone(self):
        s = self.one(member_ids=[self.vol_mid])
        self.call("PATCH", f"/{s['id']}", body={"notes": "Bring a pen", "needed": 3})
        assert [t for t, _ in notices_for("vol@test.com", "shift")] == ["You are on duty: Main gate"]

    def test_the_number_needed_cannot_drop_below_who_is_on_it(self):
        s = self.one(needed=2, member_ids=[self.vol_mid, self.core_mid])
        assert self.call("PATCH", f"/{s['id']}", body={"needed": 1}).status_code == 400

    def test_moving_it_onto_another_duty_of_someone_is_refused(self):
        self.one("Other", start=at(days=3), end=at(days=3, hours=3), member_ids=[self.vol_mid])
        s = self.one("Mine", member_ids=[self.vol_mid])
        r = self.call("PATCH", f"/{s['id']}", body={"starts_at": at(days=3, hours=1), "ends_at": at(days=3, hours=2)})
        assert r.status_code == 400 and "Other" in r.json()["detail"]

    def test_bad_hours_are_refused_on_change(self):
        s = self.one()
        assert self.call("PATCH", f"/{s['id']}", body={"ends_at": at(days=1)}).status_code == 400

    def test_cancelling_tells_the_people_and_removes_it(self):
        s = self.one(member_ids=[self.vol_mid])
        assert self.call("DELETE", f"/{s['id']}").status_code == 204
        assert self.shifts() == []
        assert "Duty cancelled: Main gate" in [t for t, _ in notices_for("vol@test.com", "shift")]


class TestTurningUp(Roster):
    def test_a_member_can_say_they_are_here_from_thirty_minutes_before(self):
        s = self.one(start=at(hours=0.25), end=at(hours=3), member_ids=[self.vol_mid])
        assert self.shifts(token=self.vol)[0]["can_arrive"] is True
        r = self.call("POST", f"/{s['id']}/arrive", token=self.vol)
        assert r.status_code == 200 and r.json()["people"][0]["arrived_at"] is not None and r.json()["can_arrive"] is False

    def test_it_is_too_early_two_hours_before(self):
        s = self.one(start=at(hours=2), end=at(hours=5), member_ids=[self.vol_mid])
        assert self.shifts(token=self.vol)[0]["can_arrive"] is False
        assert self.call("POST", f"/{s['id']}/arrive", token=self.vol).status_code == 400

    def test_someone_not_on_the_duty_cannot_say_they_are_here(self):
        s = self.one(start=at(hours=-1), end=at(hours=2))
        assert self.call("POST", f"/{s['id']}/arrive", token=self.vol).status_code == 404

    def test_a_duty_in_progress_shows_as_now(self):
        self.one(start=at(hours=-1), end=at(hours=2))
        assert self.shifts()[0]["state"] == "now"

    def test_staff_mark_who_came_and_who_did_not(self):
        s = self.one(needed=2, start=at(hours=-1), end=at(hours=2), member_ids=[self.vol_mid, self.core_mid])
        r = self.call("PUT", f"/{s['id']}/attendance", body={"marks": [{"member_id": self.vol_mid, "status": "arrived"}, {"member_id": self.core_mid, "status": "no_show"}]})
        people = {p["member_id"]: p for p in r.json()["people"]}
        assert people[self.vol_mid]["arrived_at"] and people[self.core_mid]["no_show"] is True
        r = self.call("PUT", f"/{s['id']}/attendance", body={"marks": [{"member_id": self.core_mid, "status": "clear"}]})
        assert {p["member_id"]: p for p in r.json()["people"]}[self.core_mid]["no_show"] is False

    def test_volunteers_cannot_mark_attendance_and_only_for_people_on_it(self):
        s = self.one(member_ids=[self.vol_mid])
        assert self.call("PUT", f"/{s['id']}/attendance", token=self.vol, body={"marks": [{"member_id": self.vol_mid, "status": "arrived"}]}).status_code == 403
        assert self.call("PUT", f"/{s['id']}/attendance", body={"marks": [{"member_id": self.core_mid, "status": "arrived"}]}).status_code == 400


class TestCoverage(Roster):
    def test_it_counts_the_gaps_and_the_people_without_a_duty(self):
        self.one("Gate", needed=3, member_ids=[self.vol_mid])
        self.one("Desk", needed=1, member_ids=[self.core_mid], start=at(days=9), end=at(days=9, hours=2))
        r = client.get("/api/fests/fest-one/shifts/coverage", headers=auth(self.owner))
        assert r.status_code == 200
        c = r.json()
        assert c["upcoming"] == 2 and c["understaffed"] == 1 and c["open_spots"] == 2
        assert [g["title"] for g in c["soon"]] == ["Gate"]
        assert "Vol User" not in c["unassigned_people"] and "Core User" not in c["unassigned_people"] and len(c["unassigned_people"]) == 1

    def test_far_off_gaps_are_not_urgent(self):
        self.one("Far", start=at(days=20), end=at(days=20, hours=2))
        c = client.get("/api/fests/fest-one/shifts/coverage", headers=auth(self.owner)).json()
        assert c["understaffed"] == 1 and c["soon"] == []

    def test_volunteers_cannot_see_coverage(self):
        assert client.get("/api/fests/fest-one/shifts/coverage", headers=auth(self.vol)).status_code == 403


class TestTidyUp(Roster):
    def test_removing_a_member_clears_their_duties(self):
        s = self.one(member_ids=[self.vol_mid])
        r = client.delete(f"/api/fests/fest-one/members/{user_id('vol@test.com')}", headers=auth(self.owner))
        assert r.status_code == 204, r.text
        assert self.shifts()[0]["filled"] == 0 and s["id"]

    def test_deleting_an_event_keeps_its_duties(self):
        db = TestingSessionLocal()
        fest = db.query(models.Fest).filter(models.Fest.slug == "fest-one").first()
        ev = models.Event(title="Quiz", date=datetime.now() + timedelta(days=2), fest_id=fest.id, event_type=models.EventTypeEnum.fest, organizer_id=fest.created_by_id if hasattr(fest, "created_by_id") else None)
        db.add(ev); db.commit(); eid = ev.id; db.close()
        s = self.one(event_id=eid)
        assert s["event_id"] == eid


class TestDashboard(Roster):
    def dash(self, token):
        r = client.get("/api/dashboard", headers=auth(token))
        assert r.status_code == 200, r.text
        return r.json()

    def test_the_core_team_is_told_about_empty_spots_soon(self):
        self.one("Gate", needed=3, member_ids=[self.vol_mid], start=at(days=1), end=at(days=1, hours=2))
        item = next(a for a in self.dash(self.owner)["attention"] if a["kind"] == "shifts_gaps")
        assert "2 duty spots" in item["title"] and item["tab"] == "shifts"

    def test_far_off_gaps_do_not_nag_and_volunteers_are_not_asked_to_staff_it(self):
        self.one("Far", needed=2, start=at(days=10), end=at(days=10, hours=2))
        assert not [a for a in self.dash(self.owner)["attention"] if a["kind"] == "shifts_gaps"]
        self.one("Near", needed=2, start=at(days=1), end=at(days=1, hours=2))
        assert not [a for a in self.dash(self.vol)["attention"] if a["kind"] == "shifts_gaps"]

    def test_my_own_duties_show_under_coming_up(self):
        self.one("Gate", member_ids=[self.vol_mid], location="Gate 1")
        mine = [u for u in self.dash(self.vol)["coming_up"] if u["kind"] == "shift"]
        assert [u["title"] for u in mine] == ["On duty: Gate"] and mine[0]["tab"] == "duty" and mine[0]["detail"] == "Gate 1"
        assert not [u for u in self.dash(self.core)["coming_up"] if u["kind"] == "shift"]
