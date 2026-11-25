"""Ticketing: several kinds of ticket for an event, and promo codes."""

from datetime import date, timedelta

from test_fixes import user_token  # noqa: F401
from test_full import client, auth, reset_db, get_entry_pass, verify_student, TestingSessionLocal  # noqa: F401
from test_organiser import Setup, event_payload
from app import models


def day(n):
    return (date.today() + timedelta(days=n)).isoformat()


class Box(Setup):
    """A live fest with a paid 500 rupee event, and a student who holds an entry pass."""

    def setup_method(self):
        super().setup_method()
        self.fest = self.ready_and_approved("fest-live")
        assert client.patch("/api/fests/fest-live/status", json={"status": "live"}, headers=auth(self.owner)).status_code == 200
        get_entry_pass(self.student, "fest-live")
        self.event = self.make_event()

    def make_event(self, **extra):
        payload = event_payload(self.fest["id"], requires_registration=True, date="2026-12-05T00:00:00")
        payload.update({"is_paid": True, "is_free": False, "price": 500, **extra})
        r = client.post("/api/events/", json=payload, headers=auth(self.owner))
        assert r.status_code == 200, r.text
        return r.json()

    def tier(self, name="Regular", price=500, event=None, token=None, **extra):
        e = event or self.event
        return client.post(f"/api/events/{e['id']}/tiers", json={"name": name, "price": price, **extra}, headers=auth(token or self.owner))

    def reg(self, event=None, token=None, **body):
        return client.post(f"/api/fest-events/{(event or self.event)['id']}/register", json=body or None, headers=auth(token or self.student))

    def quote(self, event=None, token=None, **body):
        return client.post(f"/api/fest-events/{(event or self.event)['id']}/quote", json=body, headers=auth(token or self.student))

    def promo(self, code="SAVE20", **extra):
        body = {"code": code, "kind": "percent", "value": 20, **extra}
        return client.post("/api/fests/fest-live/promo-codes", json=body, headers=auth(self.owner))

    def event_now(self, e=None):
        return client.get(f"/api/events/{(e or self.event)['id']}", headers=auth(self.owner)).json()

    def student_two(self, email="two@test.com"):
        tok = user_token("Two", email)
        get_entry_pass(tok, "fest-live")
        return tok


# ─── tiers ───────────────────────────────────────────────────────────────────

class TestTiers(Box):
    def test_an_event_can_sell_several_kinds_of_ticket(self):
        self.tier("Early bird", 300, quantity=50); self.tier("Regular", 500); self.tier("VIP", 1200, description="Front row")
        tiers = client.get(f"/api/events/{self.event['id']}/tiers").json()
        assert [t["name"] for t in tiers] == ["Early bird", "Regular", "VIP"] and tiers[0]["remaining"] == 50 and tiers[1]["remaining"] is None and tiers[2]["description"] == "Front row"

    def test_the_event_shows_its_lowest_price_and_counts_as_paid(self):
        self.tier("Regular", 500); self.tier("Early bird", 300)
        e = self.event_now()
        assert e["price"] == 300 and e["is_free"] is False and e["is_paid"] is True

    def test_lists_say_from_only_when_the_tickets_differ_in_price(self):
        self.tier("Regular", 500)
        assert self.event_now()["price_is_from"] is False
        t = self.tier("Early bird", 300).json()
        assert self.event_now()["price_is_from"] is True
        client.delete(f"/api/ticket-tiers/{t['id']}", headers=auth(self.owner))
        assert self.event_now()["price_is_from"] is False

    def test_an_event_whose_tickets_are_all_free_is_free(self):
        self.tier("Free pass", 0)
        e = self.event_now()
        assert e["is_free"] is True and e["is_paid"] is False and e["price"] == 0

    def test_tickets_are_for_events_people_register_for(self):
        e = client.post("/api/events/", json=event_payload(self.fest["id"]), headers=auth(self.owner)).json()
        r = self.tier(event=e)
        assert r.status_code == 400 and "registration" in r.json()["detail"]

    def test_tickets_that_are_switched_off_are_hidden_from_the_public_but_not_the_committee(self):
        t = self.tier("Hidden", 100).json()
        client.patch(f"/api/ticket-tiers/{t['id']}", json={"active": False}, headers=auth(self.owner))
        assert client.get(f"/api/events/{self.event['id']}/tiers").json() == []
        assert len(client.get(f"/api/events/{self.event['id']}/tiers", headers=auth(self.owner)).json()) == 1

    def test_only_the_committee_sees_how_many_are_sold(self):
        self.tier("Regular", 500, quantity=10).json()
        tid = client.get(f"/api/events/{self.event['id']}/tiers").json()[0]["id"]
        self.reg(ticket_tier_id=tid)
        assert client.get(f"/api/events/{self.event['id']}/tiers").json()[0]["sold"] is None
        staff_view = client.get(f"/api/events/{self.event['id']}/tiers", headers=auth(self.owner)).json()[0]
        assert staff_view["sold"] == 1 and staff_view["remaining"] == 9

    def test_the_student_price_must_be_lower_and_sales_must_end_after_they_start(self):
        assert self.tier("A", 500, student_price=500).status_code == 422
        assert self.tier("B", 500, sales_open_on=day(5), sales_close_on=day(2)).status_code == 422
        assert self.tier("C", 500, quantity=0).status_code == 422

    def test_names_are_unique_within_an_event(self):
        self.tier("Regular")
        assert self.tier("regular").status_code == 400

    def test_an_event_can_have_at_most_twelve_kinds(self):
        for i in range(12):
            assert self.tier(f"T{i}", 100).status_code == 201
        assert self.tier("One more", 100).status_code == 400

    def test_a_ticket_can_be_changed_but_not_below_what_is_sold(self):
        t = self.tier("Regular", 500, quantity=10).json()
        self.reg(ticket_tier_id=t["id"])
        assert client.patch(f"/api/ticket-tiers/{t['id']}", json={"quantity": 1}, headers=auth(self.owner)).status_code == 200
        t2 = self.tier("Other", 100, quantity=5).json()
        for i in range(2):
            self.reg(token=self.student_two(f"x{i}@test.com"), ticket_tier_id=t2["id"])
        assert client.patch(f"/api/ticket-tiers/{t2['id']}", json={"quantity": 1}, headers=auth(self.owner)).status_code == 400

    def test_changing_a_price_does_not_change_what_people_already_paid(self):
        t = self.tier("Regular", 500).json()
        self.reg(ticket_tier_id=t["id"])
        client.patch(f"/api/ticket-tiers/{t['id']}", json={"price": 900}, headers=auth(self.owner))
        mine = client.get("/api/fest-events/my-registrations", headers=auth(self.student)).json()
        assert mine[0]["amount_due"] == 500
        assert self.event_now()["price"] == 900

    def test_a_student_price_cannot_be_set_above_the_price_by_a_later_change(self):
        t = self.tier("Regular", 500, student_price=300).json()
        assert client.patch(f"/api/ticket-tiers/{t['id']}", json={"price": 250}, headers=auth(self.owner)).status_code == 400

    def test_a_ticket_with_sales_cannot_be_deleted_but_can_be_switched_off(self):
        t = self.tier("Regular", 500).json()
        self.reg(ticket_tier_id=t["id"])
        r = client.delete(f"/api/ticket-tiers/{t['id']}", headers=auth(self.owner))
        assert r.status_code == 400 and "Switch it off" in r.json()["detail"]
        assert client.patch(f"/api/ticket-tiers/{t['id']}", json={"active": False}, headers=auth(self.owner)).json()["status"] == "off"

    def test_an_unsold_ticket_can_be_deleted_and_the_event_price_follows(self):
        a = self.tier("Cheap", 100).json(); self.tier("Dear", 700)
        assert client.delete(f"/api/ticket-tiers/{a['id']}", headers=auth(self.owner)).status_code == 204
        assert self.event_now()["price"] == 700

    def test_only_the_committee_manages_tickets(self):
        t = self.tier("Regular").json()
        assert self.tier("X", token=self.student).status_code == 403
        assert client.patch(f"/api/ticket-tiers/{t['id']}", json={"price": 1}, headers=auth(self.student)).status_code == 403
        assert client.delete(f"/api/ticket-tiers/{t['id']}", headers=auth(self.student)).status_code == 403
        assert client.post(f"/api/events/{self.event['id']}/tiers", json={"name": "x", "price": 1}).status_code == 401


# ─── buying a ticket ─────────────────────────────────────────────────────────

class TestBuying(Box):
    def test_with_several_tickets_you_must_choose_one(self):
        self.tier("Regular", 500)
        r = self.reg()
        assert r.status_code == 400 and "Choose which ticket" in r.json()["detail"]

    def test_the_ticket_chosen_sets_the_price_and_is_recorded(self):
        a = self.tier("Early bird", 300).json(); b = self.tier("VIP", 1200).json()
        r = self.reg(ticket_tier_id=b["id"])
        assert r.status_code == 201 and r.json()["amount_due"] == 1200 and r.json()["ticket_tier_id"] == b["id"] and r.json()["payment_status"] == "paid"
        assert a

    def test_a_verified_student_pays_the_student_price(self):
        t = self.tier("Regular", 500, student_price=350).json()
        verify_student("student@test.com")
        assert self.reg(ticket_tier_id=t["id"]).json()["amount_due"] == 350
        other = self.student_two()
        assert self.reg(token=other, ticket_tier_id=t["id"]).json()["amount_due"] == 500

    def test_a_ticket_from_another_event_or_a_made_up_one_is_refused(self):
        self.tier("Regular", 500)
        other = self.make_event(title="Other event")
        theirs = self.tier("Theirs", 100, event=other).json()
        assert self.reg(ticket_tier_id=theirs["id"]).status_code == 400
        assert self.reg(ticket_tier_id=99999).status_code == 400

    def test_an_event_without_several_tickets_refuses_a_ticket_choice(self):
        assert self.reg(ticket_tier_id=1).status_code == 400

    def test_a_ticket_not_yet_on_sale_or_already_ended_cannot_be_bought(self):
        soon = self.tier("Later", 500, sales_open_on=day(3)).json()
        gone = self.tier("Gone", 500, sales_close_on=day(-1)).json()
        r1, r2 = self.reg(ticket_tier_id=soon["id"]), self.reg(ticket_tier_id=gone["id"])
        assert r1.status_code == 400 and "not on sale yet" in r1.json()["detail"]
        assert r2.status_code == 400 and "no longer on sale" in r2.json()["detail"]
        statuses = {t["name"]: t["status"] for t in client.get(f"/api/events/{self.event['id']}/tiers").json()}
        assert statuses == {"Later": "not_yet", "Gone": "ended"}

    def test_a_sold_out_ticket_cannot_be_bought_and_says_so(self):
        t = self.tier("Few", 500, quantity=1).json()
        assert self.reg(ticket_tier_id=t["id"]).status_code == 201
        r = self.reg(token=self.student_two(), ticket_tier_id=t["id"])
        assert r.status_code == 400 and "sold out" in r.json()["detail"]
        assert client.get(f"/api/events/{self.event['id']}/tiers").json()[0]["status"] == "sold_out"

    def test_a_cancelled_registration_gives_the_ticket_back(self):
        t = self.tier("Few", 500, quantity=1).json()
        self.reg(ticket_tier_id=t["id"])
        client.delete(f"/api/fest-events/{self.event['id']}/register", headers=auth(self.student))
        assert self.reg(token=self.student_two(), ticket_tier_id=t["id"]).status_code == 201

    def test_a_free_ticket_costs_nothing(self):
        t = self.tier("Free", 0).json()
        r = self.reg(ticket_tier_id=t["id"])
        assert r.status_code == 201 and r.json()["amount_due"] == 0 and r.json()["payment_status"] == "unpaid"

    def test_each_person_in_a_team_event_picks_their_own_ticket(self):
        e = self.make_event(title="Team event", is_team_event=True, team_min=2, team_max=3)
        a = self.tier("Standard", 400, event=e).json(); b = self.tier("Premium", 800, event=e).json()
        r = client.post(f"/api/fest-events/{e['id']}/teams", json={"name": "Alpha", "ticket_tier_id": a["id"]}, headers=auth(self.student))
        assert r.status_code == 201
        code = r.json()["code"]
        mate = self.student_two()
        assert client.post("/api/fest-events/teams/join", json={"code": code}, headers=auth(mate)).status_code == 400   # must choose
        assert client.post("/api/fest-events/teams/join", json={"code": code, "ticket_tier_id": b["id"]}, headers=auth(mate)).status_code == 200
        regs = {r["user_name"]: r["amount_due"] for r in client.get(f"/api/fest-events/{e['id']}/registrations", headers=auth(self.owner)).json()}
        assert sorted(regs.values()) == [400, 800]

    def test_the_committee_sees_which_ticket_each_person_bought(self):
        t = self.tier("VIP", 1200).json()
        self.reg(ticket_tier_id=t["id"])
        rows = client.get(f"/api/fest-events/{self.event['id']}/registrations", headers=auth(self.owner)).json()
        assert rows[0]["tier_name"] == "VIP" and rows[0]["amount_due"] == 1200


# ─── promo codes ─────────────────────────────────────────────────────────────

class TestPromoCodes(Box):
    def test_a_code_takes_a_percentage_off(self):
        self.promo("SAVE20", value=20)
        r = self.reg(promo_code="save20")   # typed in any case
        assert r.status_code == 201 and r.json()["amount_due"] == 400 and r.json()["discount"] == 100

    def test_or_a_fixed_amount(self):
        self.promo("FLAT150", kind="flat", value=150)
        assert self.reg(promo_code="FLAT150").json()["amount_due"] == 350

    def test_a_fixed_amount_bigger_than_the_price_makes_it_free(self):
        self.promo("FREE", kind="flat", value=900)
        r = self.reg(promo_code="FREE")
        assert r.json()["amount_due"] == 0 and r.json()["payment_status"] == "unpaid" and r.json()["discount"] == 500

    def test_percentages_round_down_to_whole_paise(self):
        self.promo("THIRD", value=33)
        assert self.quote(promo_code="THIRD").json()["discount"] == 165

    def test_a_code_applies_to_the_student_price_and_to_a_chosen_ticket(self):
        t = self.tier("Regular", 500, student_price=300).json()
        verify_student("student@test.com")
        self.promo("TEN", value=10)
        q = self.quote(ticket_tier_id=t["id"], promo_code="TEN").json()
        assert q["price"] == 300 and q["discount"] == 30 and q["total"] == 270 and q["tier_name"] == "Regular"

    def test_the_quote_changes_nothing(self):
        self.promo("SAVE20")
        self.quote(promo_code="SAVE20")
        assert client.get("/api/fest-events/my-registrations", headers=auth(self.student)).json() == []
        assert self.reg(promo_code="SAVE20").status_code == 201

    def test_the_quote_needs_a_sign_in_and_a_registration_event(self):
        assert client.post(f"/api/fest-events/{self.event['id']}/quote", json={}).status_code == 401
        e = client.post("/api/events/", json=event_payload(self.fest["id"]), headers=auth(self.owner)).json()
        assert self.quote(event=e).status_code == 404

    def test_a_made_up_code_is_refused(self):
        assert self.reg(promo_code="NOPE").status_code == 400
        assert "not valid" in self.quote(promo_code="NOPE").json()["detail"]

    def test_a_free_ticket_does_not_need_a_code(self):
        self.promo("SAVE20")
        free = self.make_event(title="Free one", is_paid=False, is_free=True, price=0)
        r = self.quote(event=free, promo_code="SAVE20")
        assert r.status_code == 400 and "free" in r.json()["detail"]

    def test_a_code_not_yet_started_or_expired_is_refused(self):
        self.promo("LATER", valid_from=day(4)); self.promo("OVER", valid_until=day(-1))
        assert "can be used from" in self.quote(promo_code="LATER").json()["detail"]
        assert "expired" in self.quote(promo_code="OVER").json()["detail"]

    def test_a_code_for_other_events_does_not_work_here(self):
        other = self.make_event(title="Other")
        self.promo("ONLYTHERE", event_ids=[other["id"]])
        assert "does not work for this event" in self.quote(promo_code="ONLYTHERE").json()["detail"]
        assert self.quote(event=other, promo_code="ONLYTHERE").status_code == 200

    def test_a_code_for_students_is_refused_to_everyone_else(self):
        self.promo("STUDENT", students_only=True)
        assert "verified students" in self.quote(promo_code="STUDENT").json()["detail"]
        verify_student("student@test.com")
        assert self.quote(promo_code="STUDENT").status_code == 200

    def test_a_code_can_be_used_only_so_many_times_in_all(self):
        self.promo("TWO", max_uses=2, per_user_limit=5)
        for i in range(2):
            assert self.reg(token=self.student_two(f"p{i}@test.com"), promo_code="TWO").status_code == 201
        late = self.student_two("late@test.com")
        r = self.reg(token=late, promo_code="TWO")
        assert r.status_code == 400 and "used up" in r.json()["detail"]
        assert next(p for p in client.get("/api/fests/fest-live/promo-codes", headers=auth(self.owner)).json() if p["code"] == "TWO")["status"] == "used_up"

    def test_each_person_may_use_a_code_only_so_many_times(self):
        self.promo("ONCE")
        a = self.event; b = self.make_event(title="Second event")
        assert self.reg(event=a, promo_code="ONCE").status_code == 201
        r = self.reg(event=b, promo_code="ONCE")
        assert r.status_code == 400 and "already used" in r.json()["detail"]

    def test_a_limit_of_two_per_person_lets_them_use_it_twice(self):
        self.promo("TWICE", per_user_limit=2)
        assert self.reg(event=self.event, promo_code="TWICE").status_code == 201
        assert self.reg(event=self.make_event(title="Second"), promo_code="TWICE").status_code == 201
        assert self.reg(event=self.make_event(title="Third"), promo_code="TWICE").status_code == 400

    def test_cancelling_gives_the_use_back(self):
        self.promo("BACK", max_uses=1)
        self.reg(promo_code="BACK")
        client.delete(f"/api/fest-events/{self.event['id']}/register", headers=auth(self.student))
        assert self.reg(token=self.student_two(), promo_code="BACK").status_code == 201

    def test_a_switched_off_code_is_refused(self):
        p = self.promo("OFF").json()
        client.patch(f"/api/fests/fest-live/promo-codes/{p['id']}", json={"active": False}, headers=auth(self.owner))
        assert "not valid" in self.quote(promo_code="OFF").json()["detail"]

    def test_the_committee_sees_how_a_code_is_doing(self):
        self.promo("SAVE20", value=20, max_uses=10)
        self.reg(promo_code="SAVE20")
        p = client.get("/api/fests/fest-live/promo-codes", headers=auth(self.owner)).json()[0]
        assert p["used"] == 1 and p["discount_given"] == 100 and p["status"] == "live" and p["max_uses"] == 10

    def test_the_committee_sees_which_code_each_person_used(self):
        self.promo("SAVE20")
        self.reg(promo_code="SAVE20")
        assert client.get(f"/api/fest-events/{self.event['id']}/registrations", headers=auth(self.owner)).json()[0]["promo_code_text"] == "SAVE20"

    def test_a_code_is_stored_in_capitals_and_cannot_be_made_twice(self):
        assert self.promo("early-bird").json()["code"] == "EARLY-BIRD"
        assert self.promo("EARLY-bird").status_code == 400

    def test_bad_codes_are_refused(self):
        assert self.promo("ab").status_code == 422 and self.promo("has space").status_code == 422
        assert self.promo("BIG", value=150).status_code == 422
        assert self.promo("HALF", value=12.5).status_code == 400
        assert self.promo("BACKWARDS", valid_from=day(5), valid_until=day(2)).status_code == 422

    def test_a_code_can_only_name_events_of_this_fest(self):
        assert self.promo("XYZ1", event_ids=[999999]).status_code == 400

    def test_a_code_can_be_changed_but_a_used_one_cannot_be_deleted(self):
        p = self.promo("EDIT", value=10).json()
        assert client.patch(f"/api/fests/fest-live/promo-codes/{p['id']}", json={"value": 25, "max_uses": 5}, headers=auth(self.owner)).json()["value"] == 25
        assert client.patch(f"/api/fests/fest-live/promo-codes/{p['id']}", json={"value": 250}, headers=auth(self.owner)).status_code == 400
        self.reg(promo_code="EDIT")
        r = client.delete(f"/api/fests/fest-live/promo-codes/{p['id']}", headers=auth(self.owner))
        assert r.status_code == 400 and "Switch it off" in r.json()["detail"]
        fresh = self.promo("FRESH").json()
        assert client.delete(f"/api/fests/fest-live/promo-codes/{fresh['id']}", headers=auth(self.owner)).status_code == 204

    def test_only_the_committee_manages_codes(self):
        assert client.get("/api/fests/fest-live/promo-codes", headers=auth(self.student)).status_code == 403
        assert client.post("/api/fests/fest-live/promo-codes", json={"code": "HACK", "kind": "percent", "value": 100}, headers=auth(self.student)).status_code == 403

    def test_a_codes_of_another_fest_do_not_work_here(self):
        self.start("fest-two")
        client.post("/api/fests/fest-two/promo-codes", json={"code": "ELSEWHERE", "kind": "percent", "value": 50}, headers=auth(self.owner))
        assert "not valid" in self.quote(promo_code="ELSEWHERE").json()["detail"]

    def test_each_member_of_a_team_may_use_their_own_code(self):
        e = self.make_event(title="Team event", is_team_event=True, team_min=2, team_max=3)
        self.promo("TEAM10", value=10, per_user_limit=1)
        r = client.post(f"/api/fest-events/{e['id']}/teams", json={"name": "Beta", "promo_code": "TEAM10"}, headers=auth(self.student))
        assert r.status_code == 201
        mate = self.student_two()
        assert client.post("/api/fest-events/teams/join", json={"code": r.json()["code"], "promo_code": "TEAM10"}, headers=auth(mate)).status_code == 200
        amounts = sorted(x["amount_due"] for x in client.get(f"/api/fest-events/{e['id']}/registrations", headers=auth(self.owner)).json())
        assert amounts == [450, 450]

    def test_deleting_an_event_with_tickets_and_no_sales_works(self):
        e = self.make_event(title="To delete")
        self.tier("Regular", 100, event=e)
        assert client.delete(f"/api/events/{e['id']}", headers=auth(self.owner)).status_code == 204
