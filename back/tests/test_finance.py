"""Finance: categories, the budget, spend requests with approvals, receipts, income, and the summary."""

import io
from datetime import date, timedelta

from test_fixes import user_token  # noqa: F401
from test_full import client, auth, reset_db, TestingSessionLocal  # noqa: F401
from test_committee_structure import Committee
from test_committee_meetings import notices_for
from app import models

SLUG = "fest-one"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


def day(n):
    return (date.today() + timedelta(days=n)).isoformat()


class Money(Committee):
    """A fest with a director (owner), a core member, a volunteer, the usual categories, and a 10,000 rupee venue line."""

    def setup_method(self):
        super().setup_method()
        self.f("POST", "/categories/usual")
        self.cat = {c["name"]: c["id"] for c in self.f("GET", "/categories").json()}
        self.venue = self.line("Hall hire", "Venue and infrastructure", 10000)
        self.f("PUT", "/settings", json={"receipts_never_needed": True})   # most tests are about something else; the receipt rule has its own tests

    def want_receipts(self, over=1000):
        assert self.f("PUT", "/settings", json={"receipt_required_above": over}).status_code == 200

    def f(self, method, path, token=None, **kw):
        return client.request(method, f"/api/fests/{SLUG}/finance{path}", headers=auth(token or self.owner), **kw)

    def line(self, title, category, planned, **extra):
        r = self.f("POST", "/budget", json={"title": title, "category_id": self.cat[category], "planned": planned, **extra})
        assert r.status_code == 201, r.text
        return r.json()

    def ask(self, title="Stage hire", amount=2500, token=None, line=None, **extra):
        body = {"title": title, "amount": amount, "budget_line_id": (line or self.venue)["id"], **extra}
        return self.f("POST", "/expenses", token or self.vol, json=body)

    def lines(self):
        return {l["title"]: l for l in self.f("GET", "/budget").json()}

    def upload(self, content=PNG, name="bill.png", token=None):
        return self.f("POST", "/receipts", token or self.vol, files={"file": (name, io.BytesIO(content))})

    def income(self, title="Acme sponsorship", category="Sponsorship", expected=50000, **extra):
        r = self.f("POST", "/income", json={"title": title, "category_id": self.cat[category], "expected": expected, **extra})
        assert r.status_code == 201, r.text
        return r.json()

    def summary(self):
        r = self.f("GET", "/summary")
        assert r.status_code == 200, r.text
        return r.json()


# ─── settings and categories ─────────────────────────────────────────────────

class TestSettings(Money):
    def test_defaults_ask_the_committee_to_decide_everything_and_want_receipts_over_a_thousand(self):
        self.start("fest-two")
        s = client.get("/api/fests/fest-two/finance/settings", headers=auth(self.owner)).json()
        assert s["auto_approve_below"] == 0 and s["receipt_required_above"] == 1000

    def test_the_committee_sets_its_own_rules(self):
        s = self.f("PUT", "/settings", json={"auto_approve_below": 500, "receipt_required_above": 2000}).json()
        assert s["auto_approve_below"] == 500 and s["receipt_required_above"] == 2000

    def test_receipts_can_be_switched_off(self):
        self.want_receipts()
        assert self.ask(amount=99999).status_code == 400
        assert self.f("PUT", "/settings", json={"receipts_never_needed": True}).json()["receipt_required_above"] is None
        assert self.ask(amount=99999).status_code == 201

    def test_anyone_on_the_committee_can_read_them_but_only_the_core_team_changes_them(self):
        assert self.f("GET", "/settings", self.vol).status_code == 200
        assert self.f("PUT", "/settings", self.vol, json={"auto_approve_below": 1}).status_code == 403
        assert self.f("PUT", "/settings", self.core, json={"auto_approve_below": 1}).status_code == 200
        assert self.f("GET", "/settings", self.student).status_code == 403

    def test_negative_limits_are_refused(self):
        assert self.f("PUT", "/settings", json={"auto_approve_below": -1}).status_code == 422

    def test_each_fest_has_its_own(self):
        self.f("PUT", "/settings", json={"auto_approve_below": 700})
        self.start("fest-two")
        assert client.get("/api/fests/fest-two/finance/settings", headers=auth(self.owner)).json()["auto_approve_below"] == 0


class TestCategories(Money):
    def test_a_usual_set_of_income_and_expense_categories(self):
        cats = self.f("GET", "/categories").json()
        kinds = {c["kind"] for c in cats}
        assert kinds == {"income", "expense"} and "Sponsorship" in self.cat and "Venue and infrastructure" in self.cat

    def test_the_usual_set_is_added_once(self):
        n = len(self.f("GET", "/categories").json())
        self.f("POST", "/categories/usual")
        assert len(self.f("GET", "/categories").json()) == n

    def test_a_fest_can_add_rename_and_delete_its_own(self):
        c = self.f("POST", "/categories", json={"name": "Photography", "kind": "expense"}).json()
        assert self.f("PATCH", f"/categories/{c['id']}", json={"name": "Photo and video"}).json()["name"] == "Photo and video"
        assert self.f("DELETE", f"/categories/{c['id']}").status_code == 204

    def test_names_are_unique_ignoring_case(self):
        assert self.f("POST", "/categories", json={"name": "sponsorship", "kind": "income"}).status_code == 400

    def test_a_category_in_use_cannot_be_deleted(self):
        r = self.f("DELETE", f"/categories/{self.cat['Venue and infrastructure']}")
        assert r.status_code == 400 and "rename" in r.json()["detail"]

    def test_the_committee_can_read_but_only_the_core_team_changes_them(self):
        assert self.f("GET", "/categories", self.vol).status_code == 200
        assert self.f("POST", "/categories", self.vol, json={"name": "x", "kind": "expense"}).status_code == 403
        assert self.f("GET", "/categories", self.student).status_code == 403

    def test_a_bad_kind_is_refused(self):
        assert self.f("POST", "/categories", json={"name": "x", "kind": "gift"}).status_code == 422


# ─── the budget ──────────────────────────────────────────────────────────────

class TestBudget(Money):
    def test_a_line_has_a_category_a_plan_and_optionally_a_team(self):
        team = self.add_team("Logistics").json()
        l = self.line("Chairs", "Logistics", 2500.5, committee_team_id=team["id"], notes="200 chairs")
        assert l["planned"] == 2500.5 and l["team_name"] == "Logistics" and l["category_name"] == "Logistics" and l["remaining"] == 2500.5 and l["over_budget"] is False

    def test_only_expense_categories_can_hold_a_budget_line(self):
        r = self.f("POST", "/budget", json={"title": "x", "category_id": self.cat["Sponsorship"], "planned": 1})
        assert r.status_code == 400 and "income" in r.json()["detail"]

    def test_a_team_or_category_from_another_fest_is_refused(self):
        self.start("fest-two")
        other = client.post("/api/fests/fest-two/finance/categories", json={"name": "Elsewhere", "kind": "expense"}, headers=auth(self.owner)).json()
        assert self.f("POST", "/budget", json={"title": "x", "category_id": other["id"], "planned": 1}).status_code == 400
        assert self.f("POST", "/budget", json={"title": "x", "category_id": self.cat["Logistics"], "planned": 1, "committee_team_id": 999}).status_code == 400

    def test_spending_moves_the_figures_through_pending_committed_and_paid(self):
        e = self.ask(amount=4000).json()
        l = self.lines()["Hall hire"]
        assert (l["pending"], l["committed"], l["paid"], l["remaining"]) == (4000, 0, 0, 10000)
        self.f("POST", f"/expenses/{e['id']}/approve")
        l = self.lines()["Hall hire"]
        assert (l["pending"], l["committed"], l["paid"], l["remaining"]) == (0, 4000, 0, 6000)
        self.f("POST", f"/expenses/{e['id']}/pay")
        l = self.lines()["Hall hire"]
        assert (l["committed"], l["paid"], l["remaining"]) == (4000, 4000, 6000)

    def test_a_rejected_request_does_not_count(self):
        e = self.ask(amount=4000).json()
        self.f("POST", f"/expenses/{e['id']}/reject", json={"note": "Too much"})
        l = self.lines()["Hall hire"]
        assert l["pending"] == 0 and l["committed"] == 0

    def test_a_line_goes_over_budget_when_approved_spending_passes_the_plan(self):
        for amount in (6000, 5000):
            e = self.ask(amount=amount, receipts=[self.upload().json()["url"]]).json()
            self.f("POST", f"/expenses/{e['id']}/approve")
        l = self.lines()["Hall hire"]
        assert l["over_budget"] is True and l["remaining"] == -1000

    def test_a_line_can_be_changed_and_its_spending_follows_it_to_a_new_category(self):
        e = self.ask().json()
        r = self.f("PATCH", f"/budget/{self.venue['id']}", json={"planned": 12000, "category_id": self.cat["Logistics"], "title": "Hall and chairs"}).json()
        assert r["planned"] == 12000 and r["category_name"] == "Logistics"
        assert next(x for x in self.f("GET", "/expenses").json() if x["id"] == e["id"])["category_name"] == "Logistics"

    def test_a_line_with_spending_cannot_be_deleted(self):
        self.ask()
        assert self.f("DELETE", f"/budget/{self.venue['id']}").status_code == 400
        spare = self.line("Spare", "Travel", 100)
        assert self.f("DELETE", f"/budget/{spare['id']}").status_code == 204

    def test_only_the_core_team_sees_and_changes_the_budget(self):
        assert self.f("GET", "/budget", self.vol).status_code == 403
        assert self.f("POST", "/budget", self.vol, json={"title": "x", "category_id": self.cat["Travel"], "planned": 1}).status_code == 403
        assert self.f("GET", "/budget", self.core).status_code == 200

    def test_members_get_the_choices_without_any_amounts(self):
        o = self.f("GET", "/options", self.vol).json()
        assert o["lines"][0]["title"] == "Hall hire" and "planned" not in o["lines"][0] and all(c["kind"] == "expense" for c in o["categories"])
        assert self.f("GET", "/options", self.student).status_code == 403


# ─── spend requests ──────────────────────────────────────────────────────────

class TestRequests(Money):
    def test_a_member_asks_to_spend_against_a_budget_line(self):
        r = self.ask(vendor="Stagecraft", notes="Two days")
        e = r.json()
        assert r.status_code == 201 and e["status"] == "pending" and e["amount"] == 2500 and e["line_title"] == "Hall hire" and e["category_name"] == "Venue and infrastructure" and e["vendor"] == "Stagecraft"

    def test_or_against_just_a_category(self):
        r = self.f("POST", "/expenses", self.vol, json={"title": "Taxi", "amount": 300, "category_id": self.cat["Travel"]})
        assert r.status_code == 201 and r.json()["line_title"] is None and r.json()["category_name"] == "Travel"

    def test_it_needs_a_line_or_a_category_and_a_real_amount(self):
        assert self.f("POST", "/expenses", self.vol, json={"title": "x", "amount": 5}).status_code == 422
        assert self.ask(amount=0).status_code == 422 and self.ask(amount=-5).status_code == 422

    def test_the_category_must_be_an_expense_one_in_this_fest(self):
        assert self.f("POST", "/expenses", self.vol, json={"title": "x", "amount": 5, "category_id": self.cat["Sponsorship"]}).status_code == 400
        assert self.f("POST", "/expenses", self.vol, json={"title": "x", "amount": 5, "budget_line_id": 9999}).status_code == 404

    def test_a_receipt_is_needed_above_the_limit(self):
        self.want_receipts()
        r = self.ask(amount=1500)
        assert r.status_code == 400 and "receipt" in r.json()["detail"]
        url = self.upload().json()["url"]
        assert self.ask(amount=1500, receipts=[url]).status_code == 201
        assert self.ask(amount=1000).status_code == 201   # exactly the limit needs none

    def test_a_receipt_must_be_a_file_uploaded_here(self):
        assert self.ask(receipts=["https://evil.example/x.png"]).status_code == 422
        assert self.ask(receipts=["/api/media/../etc"]).status_code == 422
        assert self.ask(receipts=[f"/api/media/{'a' * 32}"] * 6).status_code == 422

    def test_a_small_request_can_be_approved_on_the_spot_if_the_fest_says_so(self):
        self.f("PUT", "/settings", json={"auto_approve_below": 500})
        small, big = self.ask(amount=200).json(), self.ask(amount=800).json()
        assert small["status"] == "approved" and small["auto_approved"] is True and big["status"] == "pending"

    def test_paying_out_of_ones_own_pocket_is_recorded(self):
        e = self.ask(paid_by_me=True).json()
        assert e["out_of_pocket_by"].startswith("Vol")

    def test_an_admin_who_is_not_on_the_committee_cannot_claim_out_of_pocket(self):
        r = self.ask(token=self.admin, paid_by_me=True)
        assert r.status_code == 400

    def test_the_core_team_is_told_of_a_new_request(self):
        self.ask(title="Banner printing")
        assert any("Banner printing" in t for t, _ in notices_for("core@test.com", "finance"))
        assert notices_for("vol@test.com", "finance") == []

    def test_a_member_sees_only_their_own_requests_and_the_core_team_sees_all(self):
        self.ask(title="Mine"); self.ask(title="Core's", token=self.core)
        assert [e["title"] for e in self.f("GET", "/expenses", self.vol).json()] == ["Mine"]
        assert {e["title"] for e in self.f("GET", "/expenses").json()} == {"Mine", "Core's"}

    def test_the_list_can_be_filtered(self):
        a = self.ask(title="A").json(); self.ask(title="B")
        self.f("POST", f"/expenses/{a['id']}/approve")
        assert [e["title"] for e in self.f("GET", "/expenses?status=approved").json()] == ["A"]
        assert [e["title"] for e in self.f("GET", f"/expenses?line_id={self.venue['id']}").json()] == ["B", "A"]
        assert self.f("GET", "/expenses?status=bogus").status_code == 422

    def test_strangers_cannot_ask_or_see(self):
        assert self.ask(token=self.student).status_code == 403
        assert self.f("GET", "/expenses", self.student).status_code == 403

    def test_the_requester_can_change_a_waiting_request(self):
        e = self.ask().json()
        r = self.f("PATCH", f"/expenses/{e['id']}", self.vol, json={"title": "Stage and sound", "amount": 3000, "notes": "Includes sound"})
        assert r.status_code == 200 and r.json()["amount"] == 3000 and r.json()["title"] == "Stage and sound"

    def test_changing_the_amount_rechecks_the_receipt_rule(self):
        self.want_receipts()
        e = self.ask(amount=500).json()
        assert self.f("PATCH", f"/expenses/{e['id']}", self.vol, json={"amount": 5000}).status_code == 400

    def test_someone_elses_request_cannot_be_changed_by_a_member(self):
        e = self.ask(token=self.core).json()
        assert self.f("PATCH", f"/expenses/{e['id']}", self.vol, json={"title": "Mine now"}).status_code == 403

    def test_once_decided_a_member_cannot_change_it_but_the_core_team_can_until_it_is_paid(self):
        e = self.ask().json()
        self.f("POST", f"/expenses/{e['id']}/approve")
        assert self.f("PATCH", f"/expenses/{e['id']}", self.vol, json={"amount": 1}).status_code == 403
        assert self.f("PATCH", f"/expenses/{e['id']}", json={"amount": 2000}).status_code == 200
        self.f("POST", f"/expenses/{e['id']}/pay")
        assert self.f("PATCH", f"/expenses/{e['id']}", json={"amount": 1}).status_code == 400

    def test_a_request_can_be_moved_to_another_line_or_category(self):
        e = self.ask().json()
        other = self.line("Posters", "Marketing and design", 3000)
        r = self.f("PATCH", f"/expenses/{e['id']}", self.vol, json={"budget_line_id": other["id"]}).json()
        assert r["line_title"] == "Posters" and r["category_name"] == "Marketing and design"
        r = self.f("PATCH", f"/expenses/{e['id']}", self.vol, json={"category_id": self.cat["Travel"]}).json()
        assert r["line_title"] is None and r["category_name"] == "Travel"


class TestDecisions(Money):
    def test_the_core_team_approves_and_the_requester_is_told(self):
        e = self.ask(title="Stage hire").json()
        r = self.f("POST", f"/expenses/{e['id']}/approve", self.core, json={"note": "Go ahead"}).json()
        assert r["status"] == "approved" and r["decided_by_name"].startswith("Core") and r["decision_note"] == "Go ahead" and r["auto_approved"] is False
        assert any("approved" in t for t, _ in notices_for("vol@test.com", "finance"))

    def test_turning_one_down_needs_a_reason_and_tells_the_requester(self):
        e = self.ask().json()
        assert self.f("POST", f"/expenses/{e['id']}/reject", json={"note": "no"}).status_code == 422
        r = self.f("POST", f"/expenses/{e['id']}/reject", json={"note": "Over our limit for this"}).json()
        assert r["status"] == "rejected" and r["decision_note"] == "Over our limit for this"
        assert any("not approved" in t for t, _ in notices_for("vol@test.com", "finance"))

    def test_only_a_waiting_request_can_be_decided(self):
        e = self.ask().json()
        self.f("POST", f"/expenses/{e['id']}/approve")
        assert self.f("POST", f"/expenses/{e['id']}/approve").status_code == 400
        assert self.f("POST", f"/expenses/{e['id']}/reject", json={"note": "Changed my mind"}).status_code == 400

    def test_marking_paid_needs_an_approval_first(self):
        e = self.ask().json()
        assert self.f("POST", f"/expenses/{e['id']}/pay").status_code == 400
        self.f("POST", f"/expenses/{e['id']}/approve")
        r = self.f("POST", f"/expenses/{e['id']}/pay", json={"paid_on": day(-1), "note": "UPI ref 123"}).json()
        assert r["status"] == "paid" and r["paid_on"] == day(-1) and r["paid_note"] == "UPI ref 123"

    def test_members_cannot_decide_or_pay(self):
        e = self.ask().json()
        assert self.f("POST", f"/expenses/{e['id']}/approve", self.vol).status_code == 403
        assert self.f("POST", f"/expenses/{e['id']}/reject", self.vol, json={"note": "Nope nope"}).status_code == 403
        self.f("POST", f"/expenses/{e['id']}/approve")
        assert self.f("POST", f"/expenses/{e['id']}/pay", self.vol).status_code == 403

    def test_a_member_can_withdraw_a_waiting_request_but_not_after_a_decision(self):
        a, b = self.ask().json(), self.ask().json()
        assert self.f("POST", f"/expenses/{a['id']}/cancel", self.vol).json()["status"] == "cancelled"
        self.f("POST", f"/expenses/{b['id']}/approve")
        assert self.f("POST", f"/expenses/{b['id']}/cancel", self.vol).status_code == 400

    def test_nobody_else_can_withdraw_someones_request(self):
        e = self.ask(token=self.core).json()
        assert self.f("POST", f"/expenses/{e['id']}/cancel", self.vol).status_code == 403

    def test_deleting_is_for_the_core_team_and_never_for_paid_ones(self):
        a, b = self.ask().json(), self.ask().json()
        assert self.f("DELETE", f"/expenses/{a['id']}", self.vol).status_code == 403
        assert self.f("DELETE", f"/expenses/{a['id']}").status_code == 204
        self.f("POST", f"/expenses/{b['id']}/approve"); self.f("POST", f"/expenses/{b['id']}/pay")
        assert self.f("DELETE", f"/expenses/{b['id']}").status_code == 400

    def test_a_request_of_another_fest_is_not_reachable(self):
        e = self.ask().json()
        self.start("fest-two")
        assert client.post(f"/api/fests/fest-two/finance/expenses/{e['id']}/approve", headers=auth(self.owner)).status_code == 404

    def test_a_member_paid_out_of_pocket_is_owed_until_it_is_marked_paid(self):
        e = self.ask(amount=900, paid_by_me=True).json()
        self.f("POST", f"/expenses/{e['id']}/approve")
        owed = self.summary()["owed_to_members"]
        assert len(owed) == 1 and owed[0]["amount"] == 900 and owed[0]["expenses"] == 1 and owed[0]["name"].startswith("Vol")
        self.f("POST", f"/expenses/{e['id']}/pay")
        assert self.summary()["owed_to_members"] == []
        assert any("paid back" in t for t, _ in notices_for("vol@test.com", "finance"))

    def test_a_member_sees_what_they_are_owed_in_their_own_list(self):
        e = self.ask(amount=900, paid_by_me=True, token=self.vol).json()
        assert [x["id"] for x in self.f("GET", "/expenses", self.vol).json()] == [e["id"]]


# ─── receipts ────────────────────────────────────────────────────────────────

class TestReceipts(Money):
    def test_a_photo_or_a_pdf_can_be_uploaded_by_any_committee_member(self):
        r = self.upload()
        assert r.status_code == 201 and r.json()["url"].startswith("/api/media/")
        assert self.upload(b"%PDF-1.4 fake", "bill.pdf").status_code == 201

    def test_other_files_are_refused(self):
        assert self.upload(b"MZ not an image", "x.exe").status_code == 400
        assert self.upload(b"<html></html>", "x.html").status_code == 400

    def test_a_big_file_is_refused(self):
        assert self.upload(PNG + b"0" * (3 * 1024 * 1024)).status_code == 400

    def test_strangers_cannot_upload(self):
        assert self.upload(token=self.student).status_code == 403

    def test_a_pdf_is_served_as_a_download_and_an_image_inline(self):
        pdf = self.upload(b"%PDF-1.4 fake", "bill.pdf").json()["url"]
        r = client.get(pdf)
        assert r.status_code == 200 and "attachment" in r.headers["content-disposition"] and r.headers["x-content-type-options"] == "nosniff"
        png = client.get(self.upload().json()["url"])
        assert png.headers["content-type"] == "image/png" and "content-disposition" not in png.headers

    def test_an_uploaded_receipt_attaches_to_a_request(self):
        url = self.upload().json()["url"]
        e = self.ask(amount=1500, receipts=[url]).json()
        assert e["receipts"] == [url]


# ─── income ──────────────────────────────────────────────────────────────────

class TestIncome(Money):
    def test_money_expected_from_a_sponsor_is_tracked_until_it_arrives(self):
        i = self.income(source="Acme Bank", expected=50000, due_on=day(10))
        assert i["status"] == "pledged" and i["received"] == 0 and i["outstanding"] == 50000
        i = self.f("POST", f"/income/{i['id']}/payments", json={"amount": 20000, "method": "Cheque"}).json()
        assert i["status"] == "partial" and i["received"] == 20000 and i["outstanding"] == 30000 and i["payments"][0]["method"] == "Cheque"
        i = self.f("POST", f"/income/{i['id']}/payments", json={"amount": 30000}).json()
        assert i["status"] == "received" and i["outstanding"] == 0

    def test_late_money_is_marked_overdue(self):
        i = self.income(expected=1000, due_on=day(-3))
        assert i["status"] == "overdue"

    def test_it_can_be_linked_to_a_listed_sponsor(self):
        sp = client.post(f"/api/fests/{SLUG}/sponsors", json={"name": "Acme Bank", "level": 1}, headers=auth(self.owner)).json()
        i = self.income(sponsor_id=sp["id"])
        assert i["sponsor_name"] == "Acme Bank"
        assert self.f("POST", "/income", json={"title": "x", "category_id": self.cat["Sponsorship"], "expected": 1, "sponsor_id": 9999}).status_code == 400

    def test_only_income_categories_are_allowed(self):
        r = self.f("POST", "/income", json={"title": "x", "category_id": self.cat["Travel"], "expected": 1})
        assert r.status_code == 400

    def test_it_can_be_changed_and_deleted_until_money_has_come_in(self):
        i = self.income()
        assert self.f("PATCH", f"/income/{i['id']}", json={"expected": 60000, "title": "Acme (renewed)"}).json()["expected"] == 60000
        paid = self.f("POST", f"/income/{i['id']}/payments", json={"amount": 100}).json()
        assert self.f("DELETE", f"/income/{i['id']}").status_code == 400
        assert self.f("DELETE", f"/income/payments/{paid['payments'][0]['id']}").json()["status"] == "pledged"
        assert self.f("DELETE", f"/income/{i['id']}").status_code == 204

    def test_a_payment_needs_a_positive_amount(self):
        i = self.income()
        assert self.f("POST", f"/income/{i['id']}/payments", json={"amount": 0}).status_code == 422

    def test_only_the_core_team_handles_income(self):
        assert self.f("GET", "/income", self.vol).status_code == 403
        assert self.f("POST", "/income", self.vol, json={"title": "x", "category_id": self.cat["Sponsorship"], "expected": 1}).status_code == 403
        assert self.f("GET", "/income", self.core).status_code == 200


# ─── the summary and the export ──────────────────────────────────────────────

class TestSummary(Money):
    def scenario(self):
        self.income(expected=50000)                                                          # sponsorship expected
        i = self.income("College grant", "College grant", expected=20000)
        self.f("POST", f"/income/{i['id']}/payments", json={"amount": 20000})                # 20,000 received
        team = self.add_team("Logistics").json()
        chairs = self.line("Chairs", "Logistics", 4000, committee_team_id=team["id"])
        url = self.upload().json()["url"]
        paid = self.ask("Stage", 6000, line=self.venue, receipts=[url]).json()               # approved and paid
        self.f("POST", f"/expenses/{paid['id']}/approve"); self.f("POST", f"/expenses/{paid['id']}/pay")
        appr = self.ask("Chairs deposit", 1000, line=chairs).json()                          # approved, unpaid
        self.f("POST", f"/expenses/{appr['id']}/approve")
        self.ask("Extra lights", 700, line=chairs)                                           # still waiting
        loose = self.f("POST", "/expenses", self.vol, json={"title": "Taxi", "amount": 300, "category_id": self.cat["Travel"]}).json()   # no budget line
        self.f("POST", f"/expenses/{loose['id']}/approve")

    def test_an_empty_fest_is_all_zeroes(self):
        s = self.summary()
        assert s["cash_position"] == 0 and s["committed"] == 0 and s["pending_requests"] == 0

    def test_the_position_is_worked_out_from_what_actually_happened(self):
        self.scenario()
        s = self.summary()
        assert s["income_expected"] == 70000 and s["income_received"] == 20000
        assert s["budget_planned"] == 14000
        assert (s["pending"], s["approved"], s["paid"], s["committed"]) == (700, 1300, 6000, 7300)
        assert s["cash_in"] == 20000 and s["cash_out"] == 6000 and s["cash_position"] == 14000
        assert s["expected_income"] == 70000 and s["projected_net"] == 70000 - 14000
        assert s["pending_requests"] == 1 and s["unbudgeted"] == 300 and s["over_budget_lines"] == 0

    def test_a_forecast_uses_the_larger_of_the_budget_and_what_is_committed(self):
        self.income(expected=10000)
        url = self.upload().json()["url"]
        e = self.ask("Huge", 20000, receipts=[url]).json()
        self.f("POST", f"/expenses/{e['id']}/approve")
        s = self.summary()
        assert s["projected_net"] == 10000 - 20000 and s["over_budget_lines"] == 1

    def test_it_is_broken_down_by_category_and_by_team(self):
        self.scenario()
        cats = {c["name"]: c for c in self.summary()["by_category"]}
        assert cats["Venue and infrastructure"]["planned"] == 10000 and cats["Venue and infrastructure"]["committed"] == 6000 and cats["Venue and infrastructure"]["paid"] == 6000
        assert cats["Sponsorship"]["kind"] == "income" and cats["Sponsorship"]["planned"] == 50000 and cats["Sponsorship"]["committed"] == 0
        assert cats["College grant"]["committed"] == 20000
        teams = {t["name"]: t for t in self.summary()["by_team"]}
        assert teams["Logistics"]["planned"] == 4000 and teams["Logistics"]["committed"] == 1000 and teams["No team"]["planned"] == 10000

    def test_money_from_visiting_colleges_counts_as_income(self):
        from test_contingents import Visiting  # noqa: F401
        # A college that registered and paid its fees
        db = TestingSessionLocal()
        fest = db.query(models.Fest).filter(models.Fest.slug == SLUG).first()
        owner_user = db.query(models.User).filter(models.User.email == "owner@test.com").first()
        db.add(models.ContingentSettings(fest_id=fest.id, enabled=True, registration_fee_paise=100000))
        c = models.Contingent(fest_id=fest.id, college_name="IIT Delhi", status="approved", leader_user_id=owner_user.id)
        db.add(c); db.flush()
        db.add(models.FeePayment(fest_id=fest.id, contingent_id=c.id, amount_paise=40000, received_on=date.today()))
        db.commit(); db.close()
        s = self.summary()
        assert s["college_fees_due"] == 1000 and s["college_fees_received"] == 400 and s["cash_in"] == 400 and s["expected_income"] == 1000

    def test_only_the_core_team_sees_it(self):
        assert self.f("GET", "/summary", self.vol).status_code == 403
        assert self.f("GET", "/summary", self.student).status_code == 403
        assert self.f("GET", "/summary", self.core).status_code == 200 and self.f("GET", "/summary", self.admin).status_code == 200

    def test_the_spreadsheet_lists_every_rupee_and_is_safe_to_open(self):
        self.scenario()
        e = self.ask("=cmd|' /C calc'!A0", 10).json()
        self.f("POST", f"/expenses/{e['id']}/approve")
        r = self.f("GET", "/export")
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv") and "attachment" in r.headers["content-disposition"]
        lines = r.text.strip().splitlines()
        assert lines[0].startswith("Date,Type,Description") and any(",Income received,College grant" in l for l in lines) and any(",Expense,Stage," in l for l in lines)
        assert "'=cmd" in r.text and ",=cmd" not in r.text

    def test_cancelled_requests_stay_out_of_the_spreadsheet(self):
        e = self.ask("Changed my mind").json()
        self.f("POST", f"/expenses/{e['id']}/cancel", self.vol)
        assert "Changed my mind" not in self.f("GET", "/export").text

    def test_only_the_core_team_can_export(self):
        assert self.f("GET", "/export", self.vol).status_code == 403


class TestDashboardHooks(Money):
    def home(self):
        return client.get("/api/dashboard", headers=auth(self.owner)).json()

    def test_waiting_requests_show_up_for_the_core_team(self):
        self.ask(); self.ask()
        a = next(x for x in self.home()["attention"] if x["kind"] == "spend_requests")
        assert a["title"] == "2 spend requests to decide" and a["tab"] == "finance"

    def test_they_go_away_once_decided(self):
        e = self.ask().json()
        self.f("POST", f"/expenses/{e['id']}/approve")
        assert all(x["kind"] != "spend_requests" for x in self.home()["attention"])

    def test_a_line_over_budget_is_flagged(self):
        url = self.upload().json()["url"]
        e = self.ask(amount=12000, receipts=[url]).json()
        self.f("POST", f"/expenses/{e['id']}/approve")
        a = next(x for x in self.home()["attention"] if x["kind"] == "over_budget")
        assert "1 budget line is over budget" in a["title"] and "Hall hire" in a["detail"]

    def test_a_volunteer_is_not_shown_the_money(self):
        self.ask()
        assert all(x["kind"] not in ("spend_requests", "over_budget") for x in client.get("/api/dashboard", headers=auth(self.vol)).json()["attention"])
