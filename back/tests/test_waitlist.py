"""Waiting lists: queuing for a full event, and the seat that goes to whoever has waited longest."""

from datetime import date, timedelta

from test_fixes import user_token  # noqa: F401
from test_full import client, auth, reset_db, get_entry_pass, verify_student, TestingSessionLocal  # noqa: F401
from test_organiser import event_payload
from test_ticketing import Box, day
from test_committee_meetings import notices_for
from app import models


class Queue(Box):
    """A free event with two seats and a waiting list, and a few students with entry passes."""

    def setup_method(self):
        super().setup_method()
        self.ev = self.free(registration_limit=1, waitlist_enabled=True)
        self.s2 = self.student_two("two@test.com")
        self.s3 = self.student_two("three@test.com")
        self.s4 = self.student_two("four@test.com")

    def free(self, **extra):
        return self.make_event(title=extra.pop("title", "Workshop"), is_paid=False, is_free=True, price=0, **extra)

    def wl(self, method="POST", token=None, event=None, **body):
        e = event or self.ev
        kw = {"json": body} if method == "POST" else {}
        return client.request(method, f"/api/fest-events/{e['id']}/waitlist", headers=auth(token or self.s2), **kw)

    def take_seat(self, event=None):
        assert self.reg(event=event or self.ev).status_code == 201   # the first student takes the only seat

    def staff(self, method, path, **kw):
        return client.request(method, f"/api/fests/fest-live/waitlist{path}", headers=auth(self.owner), **kw)

    def registered(self, token, event=None):
        rows = client.get("/api/fest-events/my-registrations", headers=auth(token)).json()
        return [r for r in rows if r["event_id"] == (event or self.ev)["id"]]


class TestJoining(Queue):
    def test_status_tells_whether_a_queue_can_be_joined(self):
        s = self.wl("GET").json()
        assert s["enabled"] is True and s["full"] is False and s["open"] is False and s["waiting"] == 0
        self.take_seat()
        s = self.wl("GET").json()
        assert s["full"] is True and s["open"] is True and s["mine"] is None

    def test_while_there_are_seats_you_register_directly(self):
        r = self.wl()
        assert r.status_code == 400 and "register directly" in r.json()["detail"]

    def test_when_full_you_can_join_and_see_your_place(self):
        self.take_seat()
        r = self.wl()
        assert r.status_code == 201 and r.json()["mine"] == {"position": 1, "status": "waiting", "note": None} and r.json()["waiting"] == 1
        assert self.wl(token=self.s3).json()["mine"]["position"] == 2

    def test_you_cannot_join_twice_or_while_registered(self):
        self.take_seat()
        self.wl()
        assert self.wl().status_code == 400
        assert self.wl(token=self.student).status_code == 400   # the one who holds the seat

    def test_an_event_without_a_waiting_list_does_not_take_one(self):
        e = self.free(registration_limit=1, title="No list")
        self.reg(event=e)
        r = self.wl(event=e)
        assert r.status_code == 400 and "no waiting list" in r.json()["detail"]

    def test_you_need_an_entry_pass(self):
        self.take_seat()
        nopass = user_token("No Pass", "nopass@test.com")
        assert self.wl(token=nopass).status_code == 400

    def test_the_list_can_be_given_a_longest_length(self):
        e = self.free(registration_limit=1, waitlist_enabled=True, waitlist_limit=1, title="Short list")
        self.reg(event=e)
        assert self.wl(event=e).status_code == 201
        r = self.wl(event=e, token=self.s3)
        assert r.status_code == 400 and "full" in r.json()["detail"]
        assert self.wl("GET", event=e, token=self.s4).json()["open"] is False

    def test_leaving_moves_everyone_up(self):
        self.take_seat()
        self.wl(); self.wl(token=self.s3)
        assert self.wl("DELETE").json()["mine"] is None
        assert self.wl("GET", token=self.s3).json()["mine"]["position"] == 1
        assert self.wl("DELETE").status_code == 404

    def test_the_questions_of_the_event_still_have_to_be_answered(self):
        e = self.free(registration_limit=1, waitlist_enabled=True, title="With a question")
        q = client.put(f"/api/events/{e['id']}/questions", json={"questions": [{"label": "Your branch", "kind": "short_text", "required": True}]}, headers=auth(self.owner))
        assert q.status_code == 200, q.text
        qid = client.get(f"/api/events/{e['id']}/questions").json()[0]["id"]
        assert self.reg(event=e, answers=[{"question_id": qid, "value": "ECE"}]).status_code == 201
        assert self.wl(event=e).status_code == 400
        assert self.wl(event=e, answers=[{"question_id": qid, "value": "CSE"}]).status_code == 201

    def test_a_team_event_needs_a_team_name_that_is_free(self):
        e = self.free(registration_limit=1, waitlist_enabled=True, is_team_event=True, team_min=2, team_max=3, title="Teams")
        client.post(f"/api/fest-events/{e['id']}/teams", json={"name": "Alpha"}, headers=auth(self.student))
        assert self.wl(event=e).status_code == 400
        assert self.wl(event=e, team_name="alpha").status_code == 400
        assert self.wl(event=e, team_name="Beta").status_code == 201

    def test_a_ticket_or_code_that_does_not_work_is_refused_at_once(self):
        e = self.make_event(title="Paid", registration_limit=1, waitlist_enabled=True)
        self.reg(event=e)
        assert self.wl(event=e, promo_code="NOPE").status_code == 400

    def test_a_student_only_event_refuses_those_who_are_not_verified(self):
        e = self.free(registration_limit=1, waitlist_enabled=True, students_only=True, title="Students")
        verify_student("student@test.com")
        self.reg(event=e)
        assert self.wl(event=e).status_code == 403


class TestSeatsOpening(Queue):
    def test_a_cancellation_gives_the_seat_to_the_first_in_line(self):
        self.take_seat()
        self.wl(); self.wl(token=self.s3)
        client.delete(f"/api/fest-events/{self.ev['id']}/register", headers=auth(self.student))
        mine = self.registered(self.s2)
        assert len(mine) == 1 and mine[0]["approval_status"] == "approved"
        assert self.registered(self.s3) == []
        assert self.wl("GET", token=self.s2).json()["mine"]["status"] == "promoted"
        assert self.wl("GET", token=self.s3).json()["mine"]["position"] == 1
        assert any("You are in" in t for t, _ in notices_for("two@test.com", "waitlist"))

    def test_the_next_cancellation_goes_to_the_next_person(self):
        self.take_seat()
        self.wl(); self.wl(token=self.s3)
        client.delete(f"/api/fest-events/{self.ev['id']}/register", headers=auth(self.student))
        client.delete(f"/api/fest-events/{self.ev['id']}/register", headers=auth(self.s2))
        assert len(self.registered(self.s3)) == 1

    def test_nobody_is_promoted_while_the_event_is_still_full(self):
        e = self.free(registration_limit=2, waitlist_enabled=True, title="Two seats")
        self.reg(event=e); self.reg(event=e, token=self.s2)
        self.wl(event=e, token=self.s3)
        client.delete(f"/api/fest-events/{e['id']}/register", headers=auth(self.student))
        assert len(self.registered(self.s3, e)) == 1   # one seat opened, one person got it
        self.wl(event=e, token=self.s4)
        assert self.registered(self.s4, e) == []

    def test_when_the_committee_approves_each_one_a_promoted_person_waits_for_approval(self):
        e = self.free(registration_limit=1, waitlist_enabled=True, approval_mode="manual", title="Approval")
        self.reg(event=e)
        self.wl(event=e)
        client.delete(f"/api/fest-events/{e['id']}/register", headers=auth(self.student))
        assert self.registered(self.s2, e)[0]["approval_status"] == "pending"
        assert any("confirm" in b for _, b in notices_for("two@test.com", "waitlist"))

    def test_turning_someone_down_frees_their_seat_for_the_queue(self):
        e = self.free(registration_limit=1, waitlist_enabled=True, approval_mode="manual", title="Approval")
        reg = self.reg(event=e).json()
        self.wl(event=e)
        assert client.post(f"/api/fest-events/registrations/{reg['id']}/reject", headers=auth(self.owner)).status_code == 200
        assert len(self.registered(self.s2, e)) == 1

    def test_raising_the_limit_lets_the_queue_in(self):
        self.take_seat()
        self.wl(); self.wl(token=self.s3); self.wl(token=self.s4)
        assert client.patch(f"/api/events/{self.ev['id']}", json={"registration_limit": 3}, headers=auth(self.owner)).status_code == 200
        assert all(len(self.registered(t)) == 1 for t in (self.s2, self.s3))
        assert self.registered(self.s4) == []

    def test_the_promoted_person_gets_the_ticket_and_code_they_chose(self):
        e = self.make_event(title="Paid", registration_limit=1, waitlist_enabled=True)
        t = self.tier("Regular", 500, event=e).json()
        self.promo("QUEUE", value=20)
        self.reg(event=e, ticket_tier_id=t["id"])
        self.wl(event=e, ticket_tier_id=t["id"], promo_code="queue")
        client.delete(f"/api/fest-events/{e['id']}/register", headers=auth(self.student))
        r = self.registered(self.s2, e)[0]
        assert r["amount_due"] == 400 and r["ticket_tier_id"] == t["id"] and r["discount"] == 100

    def test_someone_whose_ticket_has_since_sold_out_is_taken_off_and_the_next_gets_the_seat(self):
        e = self.make_event(title="Paid", registration_limit=1, waitlist_enabled=True)
        t = self.tier("Regular", 500, event=e, quantity=3).json()
        self.reg(event=e, ticket_tier_id=t["id"])
        self.wl(event=e, ticket_tier_id=t["id"], token=self.s2)
        self.wl(event=e, ticket_tier_id=t["id"], token=self.s3)
        client.patch(f"/api/ticket-tiers/{t['id']}", json={"active": False}, headers=auth(self.owner))
        self.tier("Other", 600, event=e)
        client.delete(f"/api/fest-events/{e['id']}/register", headers=auth(self.student))
        status = self.wl("GET", event=e, token=self.s2).json()["mine"]
        assert status["status"] == "removed" and status["note"]
        assert self.registered(self.s2, e) == [] and self.registered(self.s3, e) == []
        assert any("could not be given" in b for _, b in notices_for("two@test.com", "waitlist"))

    def test_a_team_leader_in_the_queue_gets_a_team_and_a_code(self):
        e = self.free(registration_limit=1, waitlist_enabled=True, is_team_event=True, team_min=2, team_max=3, title="Teams")
        client.post(f"/api/fest-events/{e['id']}/teams", json={"name": "Alpha"}, headers=auth(self.student))
        self.wl(event=e, team_name="Beta")
        client.delete(f"/api/fest-events/{e['id']}/register", headers=auth(self.student))
        team = client.get(f"/api/fest-events/{e['id']}/my-team", headers=auth(self.s2)).json()
        assert team["name"] == "Beta" and team["i_am_leader"] is True and len(team["code"]) == 6
        assert any(team["code"] in b for _, b in notices_for("two@test.com", "waitlist"))

    def test_no_promotion_while_registration_is_closed(self):
        e = self.free(registration_limit=1, waitlist_enabled=True, title="Closing")
        self.reg(event=e); self.wl(event=e)
        client.post(f"/api/events/{e['id']}/registration", json={"action": "close"}, headers=auth(self.owner))
        client.delete(f"/api/fest-events/{e['id']}/register", headers=auth(self.student))
        assert self.registered(self.s2, e) == []
        assert self.wl("GET", event=e).json()["mine"]["status"] == "waiting"


class TestCommitteeSide(Queue):
    def test_the_committee_sees_every_queue_in_order(self):
        self.take_seat()
        self.wl(); self.wl(token=self.s3)
        rows = self.staff("GET", "").json()
        assert [(r["user_email"], r["position"], r["status"]) for r in rows] == [("two@test.com", 1, "waiting"), ("three@test.com", 2, "waiting")]
        assert rows[0]["event_title"] == "Workshop"
        assert len(self.staff("GET", f"?event_id={self.ev['id']}").json()) == 2 and self.staff("GET", "?event_id=9999").json() == []

    def test_the_committee_can_let_someone_in_past_the_limit(self):
        self.take_seat()
        self.wl(); self.wl(token=self.s3)
        second = self.staff("GET", "").json()[1]
        r = self.staff("POST", f"/{second['id']}/admit")
        assert r.status_code == 200 and r.json()["status"] == "promoted"
        assert len(self.registered(self.s3)) == 1 and self.wl("GET", token=self.s2).json()["mine"]["position"] == 1

    def test_the_committee_can_take_someone_off_with_a_reason(self):
        self.take_seat()
        self.wl()
        row = self.staff("GET", "").json()[0]
        r = self.staff("DELETE", f"/{row['id']}?reason=Duplicate%20sign-up").json()
        assert r["status"] == "removed" and r["note"] == "Duplicate sign-up"
        assert any("Duplicate sign-up" in b for _, b in notices_for("two@test.com", "waitlist"))
        assert self.staff("DELETE", f"/{row['id']}").status_code == 400

    def test_only_the_committee_sees_or_changes_the_lists(self):
        self.take_seat()
        self.wl()
        row = self.staff("GET", "").json()[0]
        assert client.get("/api/fests/fest-live/waitlist", headers=auth(self.s2)).status_code == 403
        assert client.post(f"/api/fests/fest-live/waitlist/{row['id']}/admit", headers=auth(self.s2)).status_code == 403
        assert client.delete(f"/api/fests/fest-live/waitlist/{row['id']}", headers=auth(self.s2)).status_code == 403

    def test_an_entry_of_another_fest_is_not_reachable(self):
        self.take_seat()
        self.wl()
        row = self.staff("GET", "").json()[0]
        self.start("fest-two")
        assert client.delete(f"/api/fests/fest-two/waitlist/{row['id']}", headers=auth(self.owner)).status_code == 404

    def test_the_list_settings_can_be_changed_on_the_event(self):
        r = client.patch(f"/api/events/{self.ev['id']}", json={"waitlist_limit": 5}, headers=auth(self.owner))
        assert r.status_code == 200 and r.json()["waitlist_limit"] == 5 and r.json()["waitlist_enabled"] is True
        assert client.patch(f"/api/events/{self.ev['id']}", json={"waitlist_enabled": False}, headers=auth(self.owner)).json()["waitlist_enabled"] is False

    def test_deleting_an_event_clears_its_queue(self):
        e = self.free(registration_limit=1, waitlist_enabled=True, title="Gone")
        self.reg(event=e); self.wl(event=e)
        client.delete(f"/api/fest-events/{e['id']}/register", headers=auth(self.student))   # promoted, so nobody is registered... remove them too
        client.delete(f"/api/fest-events/{e['id']}/register", headers=auth(self.s2))
        assert client.delete(f"/api/events/{e['id']}", headers=auth(self.owner)).status_code == 204
