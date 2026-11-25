"""Paying online: holds, checkout, hearing back from the gateway, refunds, and visiting colleges' fees. A fake gateway stands in for Cashfree."""

from datetime import datetime, timedelta

import pytest

from test_fixes import user_id  # noqa: F401
from test_full import client, auth, reset_db, TestingSessionLocal, get_entry_pass  # noqa: F401
from test_ticketing import Box
from test_contingent_services import Services, SLUG
from test_committee_meetings import notices_for
from app import cashfree, models, payments
from app.cashfree import GatewayError


class FakeGateway:
    env = "sandbox"

    def __init__(self):
        self.orders, self.refunds, self.refund_error, self.create_error = {}, [], None, None

    def create_order(self, order_id, amount, customer_id, name, email, phone, return_url, notify_url, note, minutes=20):
        if self.create_error:
            raise GatewayError(self.create_error)
        self.orders[order_id] = {"status": "ACTIVE", "amount": amount, "phone": phone, "return_url": return_url}
        return {"payment_session_id": f"session_{order_id}", "order_status": "ACTIVE"}

    def get_order(self, order_id):
        return {"order_status": self.orders[order_id]["status"]}

    def get_payments(self, order_id):
        return [{"payment_status": "SUCCESS", "cf_payment_id": 777, "payment_group": "upi"}] if self.orders[order_id]["status"] == "PAID" else []

    def create_refund(self, order_id, refund_id, amount, note):
        if self.refund_error:
            raise GatewayError(self.refund_error)
        self.refunds.append((order_id, refund_id, amount, note))
        return {"refund_status": "SUCCESS", "cf_refund_id": "1"}

    def get_refund(self, order_id, refund_id):
        return {"refund_status": "SUCCESS"}

    def verify_webhook(self, raw, signature, timestamp):
        return signature == "good"

    def pay(self, order_id):
        self.orders[order_id]["status"] = "PAID"

    def last_order(self):
        return list(self.orders)[-1]


@pytest.fixture(autouse=True)
def gateway():
    fake = FakeGateway()
    cashfree._override = fake
    yield fake
    cashfree._override = False


def money_events(email):
    return [t for t, _ in notices_for(email, "payment")]


class Pay(Box):
    def student_two(self, email="two@test.com"):
        if not hasattr(self, "_two"):
            self._two = super().student_two(email)
        return self._two

    def reg(self, event=None, token=None, **body):
        body.setdefault("ticket_tier_id", None)
        body = {k: v for k, v in body.items() if v is not None}
        return super().reg(event=event, token=token, **body)

    def registered(self, token=None, event=None):
        r = self.reg(token=token, event=event)
        assert r.status_code == 201, r.text
        return r.json()

    def checkout(self, rid, token=None, phone="9876543210"):
        return client.post(f"/api/payments/registrations/{rid}/checkout", json={"phone": phone} if phone else {}, headers=auth(token or self.student))

    def verify(self, order_id, token=None):
        return client.post(f"/api/payments/orders/{order_id}/verify", headers=auth(token or self.student))

    def mine(self, token=None):
        return [r for r in client.get("/api/fest-events/my-registrations", headers=auth(token or self.student)).json()]

    def pay_up(self, gateway, token=None):
        r = self.registered(token)
        c = self.checkout(r["id"], token).json()
        gateway.pay(c["order_id"])
        assert self.verify(c["order_id"], token).json()["status"] == "paid"
        return r, c

    def staff_payments(self, query="", token=None):
        return client.get(f"/api/fests/fest-live/payments{query}", headers=auth(token or self.owner))


class TestRegistering(Pay):
    def test_a_paid_registration_waits_for_the_money_and_holds_the_seat(self):
        r = self.registered()
        assert r["payment_status"] == "unpaid" and r["amount_due"] == 500 and r["awaiting_payment"] is True and r["hold_expires_at"]

    def test_without_a_gateway_it_is_confirmed_at_once_as_before(self, gateway):
        cashfree._override = False
        r = self.registered()
        assert r["payment_status"] == "paid" and r["awaiting_payment"] is False and r["hold_expires_at"] is None

    def test_a_free_ticket_needs_no_payment(self):
        t = self.tier("Free pass", 0).json()
        r = self.reg(ticket_tier_id=t["id"]).json()
        assert r["awaiting_payment"] is False and r["amount_due"] == 0

    def test_a_fully_discounted_ticket_needs_no_payment(self):
        self.promo("FREE100", value=100)
        r = self.reg(promo_code="FREE100").json()
        assert r["awaiting_payment"] is False

    def test_checking_in_is_refused_until_it_is_paid(self, gateway):
        r = self.registered()
        pass_code = client.get("/api/users/me/fest-passes", headers=auth(self.student)).json()[0]["qr_code"]
        refusal = client.post(f"/api/fest-events/{self.event['id']}/check-in", json={"qr_code": pass_code}, headers=auth(self.owner))
        assert refusal.status_code == 400 and "Payment" in refusal.json()["detail"]
        c = self.checkout(r["id"]).json(); gateway.pay(c["order_id"]); self.verify(c["order_id"])
        assert client.post(f"/api/fest-events/{self.event['id']}/check-in", json={"qr_code": pass_code}, headers=auth(self.owner)).status_code == 200


class TestCheckout(Pay):
    def test_the_config_says_whether_payment_is_on(self, gateway):
        assert client.get("/api/payments/config").json() == {"enabled": True, "env": "sandbox"}
        cashfree._override = False
        assert client.get("/api/payments/config").json()["enabled"] is False

    def test_checkout_opens_an_order_for_the_amount_due(self, gateway):
        r = self.registered()
        c = self.checkout(r["id"])
        assert c.status_code == 200
        body = c.json()
        assert body["amount"] == 500 and body["payment_session_id"].startswith("session_") and body["env"] == "sandbox"
        assert gateway.orders[body["order_id"]]["amount"] == 500 and gateway.orders[body["order_id"]]["phone"] == "9876543210"
        assert gateway.orders[body["order_id"]]["return_url"].endswith(f"/payments/return?order_id={body['order_id']}")

    def test_a_tier_and_code_change_the_amount(self, gateway):
        self.tier("Regular", 500); t = self.tier("Early bird", 300).json(); self.promo("TEN", value=10)
        r = self.reg(ticket_tier_id=t["id"], promo_code="TEN").json()
        assert self.checkout(r["id"]).json()["amount"] == 270

    def test_the_same_open_order_is_reused(self, gateway):
        r = self.registered()
        a, b = self.checkout(r["id"]).json(), self.checkout(r["id"]).json()
        assert a["order_id"] == b["order_id"] and len(gateway.orders) == 1

    def test_a_phone_number_is_needed_and_must_be_real(self):
        r = self.registered()
        assert self.checkout(r["id"], phone=None).status_code == 400
        assert self.checkout(r["id"], phone="12345").status_code == 400
        assert self.checkout(r["id"], phone="+91 98765 43210").status_code == 200

    def test_only_the_person_registered_can_pay_for_it(self):
        r = self.registered()
        other = self.student_two()
        assert self.checkout(r["id"], other).status_code == 404

    def test_nothing_to_pay_when_it_is_already_paid(self, gateway):
        r, _ = self.pay_up(gateway)
        assert self.checkout(r["id"]).status_code == 400

    def test_a_gateway_failure_is_a_clear_error_not_a_crash(self, gateway):
        r = self.registered()
        gateway.create_error = "The payment service could not be reached."
        res = self.checkout(r["id"])
        assert res.status_code == 502 and "payment service" in res.json()["detail"]

    def test_without_a_gateway_there_is_no_checkout(self, gateway):
        r = self.registered()
        cashfree._override = False
        assert self.checkout(r["id"]).status_code == 400


class TestHearingBack(Pay):
    def test_paying_confirms_the_registration_and_tells_the_student(self, gateway):
        r = self.registered()
        c = self.checkout(r["id"]).json()
        waiting = self.verify(c["order_id"]).json()
        assert waiting["status"] == "created" and self.mine()[0]["awaiting_payment"] is True
        gateway.pay(c["order_id"])
        done = self.verify(c["order_id"]).json()
        assert done["status"] == "paid" and done["amount"] == 500 and done["event_id"] == self.event["id"] and done["fest_slug"] == "fest-live"
        m = self.mine()[0]
        assert m["payment_status"] == "paid" and m["awaiting_payment"] is False and m["hold_expires_at"] is None
        assert money_events("student@test.com").count(f"Payment received: {self.event['title']}") == 1

    def test_checking_twice_changes_nothing(self, gateway):
        _, c = self.pay_up(gateway)
        self.verify(c["order_id"]); self.verify(c["order_id"])
        assert len(money_events("student@test.com")) == 1 and gateway.refunds == []

    def test_only_the_payer_can_ask_about_an_order(self, gateway):
        r = self.registered(); c = self.checkout(r["id"]).json()
        assert self.verify(c["order_id"], self.student_two()).status_code == 404
        assert self.verify("hvnope").status_code == 404

    def test_the_webhook_needs_the_gateways_signature(self, gateway):
        r = self.registered(); c = self.checkout(r["id"]).json(); gateway.pay(c["order_id"])
        body = {"type": "PAYMENT_SUCCESS_WEBHOOK", "data": {"order": {"order_id": c["order_id"]}}}
        assert client.post("/api/payments/cashfree/webhook", json=body, headers={"x-webhook-signature": "bad", "x-webhook-timestamp": "1"}).status_code == 401
        assert self.mine()[0]["awaiting_payment"] is True
        assert client.post("/api/payments/cashfree/webhook", json=body, headers={"x-webhook-signature": "good", "x-webhook-timestamp": "1"}).status_code == 200
        assert self.mine()[0]["awaiting_payment"] is False

    def test_the_webhook_ignores_orders_it_does_not_know(self):
        assert client.post("/api/payments/cashfree/webhook", json={"data": {"order": {"order_id": "hvnope"}}}, headers={"x-webhook-signature": "good", "x-webhook-timestamp": "1"}).status_code == 200
        assert client.post("/api/payments/cashfree/webhook", json={}, headers={"x-webhook-signature": "good", "x-webhook-timestamp": "1"}).status_code == 200

    def test_an_expired_order_is_marked_so(self, gateway):
        r = self.registered(); c = self.checkout(r["id"]).json()
        gateway.orders[c["order_id"]]["status"] = "EXPIRED"
        assert self.verify(c["order_id"]).json()["status"] == "expired"
        again = self.checkout(r["id"]).json()          # the student can try again with a new order
        assert again["order_id"] != c["order_id"]

    def test_my_payments_lists_what_went_through(self, gateway):
        self.pay_up(gateway)
        rows = client.get("/api/payments/mine", headers=auth(self.student)).json()
        assert len(rows) == 1 and rows[0]["amount"] == 500 and rows[0]["status"] == "paid" and rows[0]["method"] == "upi"


class TestHolds(Pay):
    def expire(self, rid):
        db = TestingSessionLocal()
        db.query(models.EventRegistration).filter(models.EventRegistration.id == rid).update({"hold_expires_at": datetime.utcnow() - timedelta(minutes=1)})
        db.commit(); db.close()

    def test_an_unpaid_registration_frees_its_seat_when_the_hold_runs_out(self):
        ev = self.make_event(registration_limit=1)
        r = self.registered(event=ev)
        assert self.reg(event=ev, token=self.student_two()).status_code == 400   # full while it is held
        self.expire(r["id"])
        assert self.reg(event=ev, token=self.student_two()).status_code == 201
        assert self.mine() == []
        assert any("released" in t for t in money_events("student@test.com"))

    def test_a_hold_that_has_not_run_out_keeps_its_seat(self):
        ev = self.make_event(registration_limit=1)
        self.registered(event=ev)
        assert self.reg(event=ev, token=self.student_two()).status_code == 400

    def test_a_payment_made_just_in_time_still_counts(self, gateway):
        ev = self.make_event(registration_limit=1)
        r = self.registered(event=ev)
        c = self.checkout(r["id"]).json(); gateway.pay(c["order_id"])
        self.expire(r["id"])
        assert self.reg(event=ev, token=self.student_two()).status_code == 400   # sorted out before the seat was freed
        assert self.mine()[0]["payment_status"] == "paid"

    def test_the_next_person_in_the_queue_is_offered_the_seat_and_told_to_pay(self):
        ev = self.make_event(registration_limit=1, waitlist_enabled=True)
        r = self.registered(event=ev)
        two = self.student_two()
        assert client.post(f"/api/fest-events/{ev['id']}/waitlist", json={}, headers=auth(two)).status_code in (200, 201)
        self.expire(r["id"])
        self.mine()                                      # anything that looks at registrations frees expired holds
        got = [m for m in self.mine(two) if m["event_id"] == ev["id"]]
        assert got and got[0]["awaiting_payment"] is True
        assert any("Pay within 30 minutes" in b for _, b in notices_for("two@test.com", "waitlist"))

    def test_a_late_payment_after_the_seat_went_is_refunded(self, gateway):
        ev = self.make_event(registration_limit=1)
        r = self.registered(event=ev)
        c = self.checkout(r["id"]).json()
        self.expire(r["id"])
        self.reg(event=ev, token=self.student_two())         # frees the seat
        gateway.pay(c["order_id"])                            # ...and then the money arrives
        assert self.verify(c["order_id"]).json()["status"] == "paid"
        assert [x[2] for x in gateway.refunds] == [500]

    def test_paying_twice_for_one_registration_refunds_the_second(self, gateway):
        r = self.registered()
        c1 = self.checkout(r["id"]).json(); gateway.pay(c1["order_id"]); self.verify(c1["order_id"])
        db = TestingSessionLocal()
        p = models.Payment(order_id="hvdup", fest_id=db.query(models.Fest).first().id, user_id=db.query(models.Payment).first().user_id, purpose="registration", event_id=self.event["id"],
                           registration_id=r["id"], amount_paise=50000, status="created", session_id="s")
        db.add(p); db.commit(); db.close()
        gateway.orders["hvdup"] = {"status": "PAID", "amount": 500}
        assert self.verify("hvdup").json()["status"] == "paid"
        assert [x[1][:2] for x in gateway.refunds] == ["rf"] and gateway.refunds[0][0] == "hvdup"


class TestRefunds(Pay):
    def cancel(self, token=None, event=None):
        return client.delete(f"/api/fest-events/{(event or self.event)['id']}/register", headers=auth(token or self.student))

    def settings(self, **body):
        assert client.put("/api/fests/fest-live/finance/settings", json=body, headers=auth(self.owner)).status_code == 200

    def test_cancelling_in_time_refunds_in_full_on_its_own(self, gateway):
        self.pay_up(gateway)
        assert self.cancel().status_code == 204
        assert [x[2] for x in gateway.refunds] == [500]
        assert "Refund on its way" in money_events("student@test.com")[-1]
        assert self.staff_payments().json()["collected"] == 0

    def test_cancelling_before_paying_refunds_nothing_and_closes_the_order(self, gateway):
        r = self.registered(); self.checkout(r["id"])
        assert self.cancel().status_code == 204
        assert gateway.refunds == []

    def test_a_fest_can_switch_cancellation_refunds_off(self, gateway):
        self.settings(refund_on_cancel=False)
        self.pay_up(gateway)
        assert self.cancel().status_code == 204 and gateway.refunds == []

    def test_too_late_to_cancel_for_a_refund(self, gateway):
        self.settings(refund_cutoff_days=365)
        self.pay_up(gateway)
        assert self.cancel().status_code == 204 and gateway.refunds == []

    def test_the_rule_is_kept_and_only_staff_set_it(self):
        self.settings(refund_on_cancel=False, refund_cutoff_days=3)
        s = client.get("/api/fests/fest-live/finance/settings", headers=auth(self.owner)).json()
        assert s["refund_on_cancel"] is False and s["refund_cutoff_days"] == 3
        assert client.put("/api/fests/fest-live/finance/settings", json={"refund_on_cancel": True}, headers=auth(self.student)).status_code == 403

    def test_cancelling_the_event_refunds_everyone_who_paid(self, gateway):
        self.pay_up(gateway); self.pay_up(gateway, self.student_two())
        r = client.post(f"/api/events/{self.event['id']}/cancel", json={"reason": "Rain"}, headers=auth(self.owner))
        assert r.status_code == 200, r.text
        assert sorted(x[2] for x in gateway.refunds) == [500, 500]

    def test_turning_someone_down_refunds_them(self, gateway):
        r, _ = self.pay_up(gateway)
        db = TestingSessionLocal()
        db.query(models.EventRegistration).filter(models.EventRegistration.id == r["id"]).update({"approval_status": models.RegApprovalStatusEnum.pending}); db.commit(); db.close()
        assert client.post(f"/api/fest-events/registrations/{r['id']}/reject", headers=auth(self.owner)).status_code == 200
        assert [x[2] for x in gateway.refunds] == [500]

    def test_a_failed_refund_does_not_block_cancelling_and_can_be_retried(self, gateway):
        self.pay_up(gateway)
        gateway.refund_error = "The payment service refused that."
        assert self.cancel().status_code == 204
        p = self.staff_payments().json()["payments"][0]
        assert p["refunded"] == 0 and p["refunds"][0]["status"] == "failed" and p["refundable"] == 500
        gateway.refund_error = None
        again = client.post(f"/api/fests/fest-live/payments/{p['id']}/refund", json={"reason": "Retry"}, headers=auth(self.owner))
        assert again.status_code == 200 and again.json()["refunded"] == 500 and again.json()["refundable"] == 0

    def test_the_committee_can_refund_part_of_a_payment_and_not_more_than_was_paid(self, gateway):
        _, c = self.pay_up(gateway)
        pid = self.staff_payments().json()["payments"][0]["id"]
        url = f"/api/fests/fest-live/payments/{pid}/refund"
        first = client.post(url, json={"amount": 200, "reason": "Goodwill"}, headers=auth(self.owner)).json()
        assert first["refunded"] == 200 and first["refundable"] == 300
        assert client.post(url, json={"amount": 400, "reason": "Too much"}, headers=auth(self.owner)).status_code == 400
        assert client.post(url, json={"reason": "The rest"}, headers=auth(self.owner)).json()["refundable"] == 0
        assert client.post(url, json={"reason": "Again"}, headers=auth(self.owner)).status_code == 400
        assert [x[2] for x in gateway.refunds] == [200, 300]

    def test_a_refund_needs_a_reason_and_a_committee_member(self, gateway):
        self.pay_up(gateway)
        pid = self.staff_payments().json()["payments"][0]["id"]
        url = f"/api/fests/fest-live/payments/{pid}/refund"
        assert client.post(url, json={"reason": "x"}, headers=auth(self.owner)).status_code == 422
        assert client.post(url, json={"reason": "Because"}, headers=auth(self.student)).status_code == 403

    def test_a_gateway_refusal_on_a_manual_refund_is_shown(self, gateway):
        self.pay_up(gateway)
        pid = self.staff_payments().json()["payments"][0]["id"]
        gateway.refund_error = "The payment service refused that: balance too low"
        r = client.post(f"/api/fests/fest-live/payments/{pid}/refund", json={"reason": "Because"}, headers=auth(self.owner))
        assert r.status_code == 502 and "balance too low" in r.json()["detail"]


class TestCommitteeView(Pay):
    def test_the_committee_sees_what_was_collected(self, gateway):
        self.pay_up(gateway); self.pay_up(gateway, self.student_two())
        body = self.staff_payments().json()
        assert body["collected"] == 1000 and body["count"] == 2 and {p["user_email"] for p in body["payments"]} == {"student@test.com", "two@test.com"}
        assert all(p["event_title"] == self.event["title"] and p["status"] == "paid" for p in body["payments"])

    def test_unfinished_orders_are_listed_only_when_asked(self, gateway):
        r = self.registered(); self.checkout(r["id"])
        assert self.staff_payments().json()["count"] == 0
        assert self.staff_payments("?status=created").json()["count"] == 1

    def test_only_the_committee_sees_payments(self, gateway):
        assert self.staff_payments(token=self.student).status_code == 403

    def test_refreshing_a_payment_catches_up_with_the_gateway(self, gateway):
        r = self.registered(); c = self.checkout(r["id"]).json(); gateway.pay(c["order_id"])
        pid = self.staff_payments("?status=created").json()["payments"][0]["id"]
        out = client.post(f"/api/fests/fest-live/payments/{pid}/refresh", headers=auth(self.owner)).json()
        assert out["status"] == "paid" and self.mine()[0]["awaiting_payment"] is False

    def test_finance_counts_only_money_that_arrived(self, gateway):
        r = self.registered()
        inc = lambda: client.get("/api/fests/fest-live/finance/summary", headers=auth(self.owner)).json()
        before = inc()
        c = self.checkout(r["id"]).json(); gateway.pay(c["order_id"]); self.verify(c["order_id"])
        after = inc()
        assert after != before


class TestFeesOnline(Services):
    def charge(self, **fees):
        assert client.put(f"/api/fests/{SLUG}/fees/settings", json=fees, headers=auth(self.owner)).status_code == 200

    def pay(self, cid=None, token=None, **body):
        body.setdefault("phone", "9876543210")
        return client.post(f"/api/payments/contingents/{cid or self.a}/checkout", json=body, headers=auth(token or self.cl))

    def statement(self):
        return client.get(f"/api/fests/{SLUG}/fees/{self.a}", headers=auth(self.owner)).json()

    def test_a_leader_pays_what_is_owed_and_it_lands_on_the_statement(self, gateway):
        self.charge(registration_fee=1000)
        c = self.pay().json()
        assert c["amount"] == 1000
        gateway.pay(c["order_id"])
        assert client.post(f"/api/payments/orders/{c['order_id']}/verify", headers=auth(self.cl)).json()["status"] == "paid"
        s = self.statement()
        assert s["paid"] == 1000 and s["balance"] == 0 and s["payments"][0]["method"] == "Online"
        assert "We received your payment" in [t for t, _ in notices_for("cl@test.com", "contingent")]

    def test_part_payments_are_fine_but_not_more_than_is_owed(self, gateway):
        self.charge(registration_fee=1000)
        assert self.pay(amount=400).status_code == 200
        assert self.pay(amount=1500).status_code == 400

    def test_nothing_to_pay_when_nothing_is_owed(self):
        assert self.pay().status_code == 400

    def test_only_that_colleges_leaders_can_pay_for_it(self):
        self.charge(registration_fee=1000)
        assert self.pay(token=self.cl2).status_code == 404
        assert self.pay(token=self.stranger).status_code == 404

    def test_verifying_twice_records_the_payment_once(self, gateway):
        self.charge(registration_fee=1000)
        c = self.pay().json(); gateway.pay(c["order_id"])
        for _ in range(2):
            client.post(f"/api/payments/orders/{c['order_id']}/verify", headers=auth(self.cl))
        assert len(self.statement()["payments"]) == 1

    def test_online_fee_payments_show_in_the_committees_list(self, gateway):
        self.charge(registration_fee=1000)
        c = self.pay().json(); gateway.pay(c["order_id"]); client.post(f"/api/payments/orders/{c['order_id']}/verify", headers=auth(self.cl))
        body = client.get(f"/api/fests/{SLUG}/payments", headers=auth(self.owner)).json()
        assert body["collected"] == 1000 and body["payments"][0]["purpose"] == "contingent_fee"
