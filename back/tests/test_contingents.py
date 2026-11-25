"""Contingents: visiting colleges, their leaders, assistants and rosters."""

from datetime import date, timedelta

from test_fixes import user_token, user_id  # noqa: F401
from test_full import client, auth, reset_db, TestingSessionLocal  # noqa: F401
from test_committee_meetings import notices_for
from test_organiser import Setup
from app import models


def day(offset):
    return (date.today() + timedelta(days=offset)).isoformat()


class Visiting(Setup):
    """A live fest, its committee (the organiser), and a few outside people who could lead a college."""

    def setup_method(self):
        super().setup_method()
        self.ready_and_approved()
        assert client.patch("/api/fests/fest-one/status", json={"status": "live"}, headers=auth(self.owner)).status_code == 200
        self.cl = user_token("Leader One", "cl@test.com")
        self.acl = user_token("Assistant One", "acl@test.com")
        self.cl2 = user_token("Leader Two", "cl2@test.com")
        self.stranger = user_token("Nobody", "nobody@test.com")

    def settings(self, token=None, slug="fest-one", **over):
        body = {"enabled": True, **over}
        return client.put(f"/api/fests/{slug}/contingents/settings", json=body, headers=auth(token or self.owner))

    def register(self, token=None, college="IIT Delhi", slug="fest-one", **extra):
        return client.post(f"/api/fests/{slug}/contingents", json={"college_name": college, **extra}, headers=auth(token or self.cl))

    def go(self, method, path, token=None, slug="fest-one", **kw):
        return client.request(method, f"/api/fests/{slug}/contingents{path}", headers=auth(token or self.owner), **kw)

    def open_and_register(self, token=None, college="IIT Delhi", **over):
        assert self.settings(**over).status_code == 200
        r = self.register(token, college)
        assert r.status_code == 201, r.text
        return r.json()


class TestSettings(Visiting):
    def test_a_fest_starts_with_contingents_switched_off_and_sensible_terms(self):
        r = client.get("/api/fests/fest-one/contingents/settings", headers=auth(self.cl))
        body = r.json()
        assert r.status_code == 200 and body["enabled"] is False and body["term"] == "Contingent" and body["leader_term"] == "Contingent Leader"
        assert body["max_assistants"] == 2 and body["requires_approval"] is True and body["registration_open"] is False

    def test_the_committee_can_change_them_and_the_terms_are_the_fests_own(self):
        r = self.settings(term="Delegation", leader_term="Delegation Head", assistant_term="Deputy", max_assistants=1, min_members=3, max_members=20)
        body = r.json()
        assert r.status_code == 200 and body["term"] == "Delegation" and body["leader_term"] == "Delegation Head" and body["max_members"] == 20
        assert client.get("/api/fests/fest-one/contingents/settings", headers=auth(self.cl)).json()["term"] == "Delegation"

    def test_only_the_committee_can_change_them(self):
        assert self.settings(token=self.cl).status_code == 403
        assert self.settings(token=self.student).status_code == 403

    def test_admins_can(self):
        assert self.settings(token=self.admin).status_code == 200

    def test_terms_are_trimmed_and_cannot_be_blank(self):
        assert self.settings(term="  Squad  ").json()["term"] == "Squad"
        assert self.settings(term="   ").status_code == 422

    def test_the_largest_cannot_be_smaller_than_the_smallest(self):
        assert self.settings(min_members=5, max_members=2).status_code == 422

    def test_registration_cannot_close_before_it_opens(self):
        assert self.settings(opens_on=day(5), closes_on=day(1)).status_code == 422

    def test_registration_is_open_only_when_enabled_and_inside_the_window(self):
        assert self.settings().json()["registration_open"] is True
        assert self.settings(closes_on=day(-1)).json()["registration_open"] is False
        assert self.settings(opens_on=day(2)).json()["registration_open"] is False
        assert self.settings(opens_on=day(-2), closes_on=day(2)).json()["registration_open"] is True
        assert self.settings(enabled=False).json()["registration_open"] is False

    def test_a_draft_fest_is_hidden_from_outsiders_but_not_from_the_committee(self):
        client.patch("/api/fests/fest-one/status", json={"status": "draft"}, headers=auth(self.owner))
        assert client.get("/api/fests/fest-one/contingents/settings", headers=auth(self.stranger)).status_code == 404
        assert client.get("/api/fests/fest-one/contingents/settings", headers=auth(self.owner)).status_code == 200

    def test_settings_need_a_sign_in(self):
        assert client.get("/api/fests/fest-one/contingents/settings").status_code == 401


class TestPublicInfo(Visiting):
    def test_anyone_can_ask_without_signing_in(self):
        self.settings(term="Delegation", leader_term="Delegation Head", closes_on=day(9))
        r = client.get("/api/fests/fest-one/contingents/info")
        assert r.status_code == 200
        body = r.json()
        assert body["enabled"] is True and body["registration_open"] is True and body["term"] == "Delegation" and body["leader_term"] == "Delegation Head" and body["closes_on"] == day(9)

    def test_a_fest_that_never_set_it_up_says_not_enabled(self):
        assert client.get("/api/fests/fest-one/contingents/info").json()["enabled"] is False

    def test_it_reflects_a_closed_window(self):
        self.settings(closes_on=day(-1))
        assert client.get("/api/fests/fest-one/contingents/info").json()["registration_open"] is False

    def test_it_gives_away_nothing_private(self):
        self.settings(max_assistants=5, requires_approval=False)
        assert set(client.get("/api/fests/fest-one/contingents/info").json()) == {"enabled", "registration_open", "term", "leader_term", "opens_on", "closes_on"}

    def test_a_draft_fest_is_not_found_for_outsiders_but_visible_to_the_committee(self):
        client.patch("/api/fests/fest-one/status", json={"status": "draft"}, headers=auth(self.owner))
        assert client.get("/api/fests/fest-one/contingents/info").status_code == 404
        assert client.get("/api/fests/fest-one/contingents/info", headers=auth(self.owner)).status_code == 200

    def test_an_unknown_fest_is_not_found(self):
        assert client.get("/api/fests/nope/contingents/info").status_code == 404


class TestRegistering(Visiting):
    def test_a_college_can_register_and_waits_for_approval(self):
        self.settings()
        r = self.register()
        body = r.json()
        assert r.status_code == 201 and body["status"] == "pending" and body["my_role"] == "leader" and body["leader_name"] == "Leader One"
        assert body["college_name"] == "IIT Delhi" and body["code"] is None and body["name"] is None

    def test_it_is_approved_at_once_when_the_fest_does_not_require_approval(self):
        self.settings(requires_approval=False)
        assert self.register().json()["status"] == "approved"

    def test_the_committee_is_told_but_not_the_leader(self):
        self.settings()
        self.register()
        assert len(notices_for("owner@test.com", "contingent")) == 1 and notices_for("cl@test.com", "contingent") == []
        assert "IIT Delhi" in notices_for("owner@test.com", "contingent")[0][0]

    def test_it_is_refused_when_the_fest_does_not_take_visiting_colleges(self):
        assert self.register().status_code == 400

    def test_it_is_refused_for_a_fest_that_is_not_live(self):
        self.settings()
        client.patch("/api/fests/fest-one/status", json={"status": "draft"}, headers=auth(self.owner))
        assert self.register().status_code == 400

    def test_it_is_refused_outside_the_registration_window(self):
        self.settings(closes_on=day(-1))
        r = self.register()
        assert r.status_code == 400 and "closed" in r.json()["detail"]
        self.settings(opens_on=day(3))
        assert "not opened" in self.register().json()["detail"]

    def test_the_messages_use_the_fests_own_word(self):
        self.settings(term="Delegation")
        self.settings(term="Delegation", closes_on=day(-1))
        assert "delegation" in self.register().json()["detail"]

    def test_a_sign_in_is_needed(self):
        self.settings()
        assert client.post("/api/fests/fest-one/contingents", json={"college_name": "IIT Delhi"}).status_code == 401

    def test_one_person_cannot_lead_two(self):
        self.settings()
        self.register()
        assert self.register(college="Another College").status_code == 400

    def test_the_same_college_cannot_register_twice_whatever_the_spelling(self):
        self.settings()
        self.register(college="IIT  Delhi")
        r = self.register(token=self.cl2, college="iit delhi")
        assert r.status_code == 400 and "already has" in r.json()["detail"]

    def test_the_same_listed_college_cannot_register_twice(self):
        self.settings()
        self.register(college="IIT D", college_id=self.college_id)
        assert self.register(token=self.cl2, college="Different spelling", college_id=self.college_id).status_code == 400

    def test_a_fest_can_allow_several_contingents_per_college(self):
        self.settings(allow_multiple_per_college=True)
        self.register()
        assert self.register(token=self.cl2).status_code == 201

    def test_an_unknown_college_id_is_refused(self):
        self.settings()
        assert self.register(college_id=99999).status_code == 400

    def test_a_too_short_college_name_is_refused(self):
        self.settings()
        assert self.register(college="X").status_code == 422

    def test_an_assistant_elsewhere_cannot_register_their_own(self):
        c = self.open_and_register()
        self.go("POST", f"/{c['id']}/assistants", token=self.cl, json={"email": "acl@test.com"})
        assert self.register(token=self.acl, college="Other College").status_code == 400

    def test_someone_whose_contingent_was_withdrawn_can_register_again(self):
        c = self.open_and_register()
        self.go("POST", f"/{c['id']}/withdraw", token=self.cl)
        assert self.register().status_code == 201

    def test_someone_whose_contingent_was_rejected_can_register_again(self):
        c = self.open_and_register()
        self.go("POST", f"/{c['id']}/reject", json={"note": "Not a college we know"})
        assert self.register(college="IIT Delhi (corrected)").status_code == 201

    def test_a_withdrawn_college_frees_its_name_for_someone_else(self):
        c = self.open_and_register()
        self.go("POST", f"/{c['id']}/withdraw", token=self.cl)
        assert self.register(token=self.cl2).status_code == 201


class TestMine(Visiting):
    def test_nothing_until_you_register(self):
        self.settings()
        assert self.go("GET", "/mine", token=self.cl).json() is None

    def test_the_leader_and_an_assistant_each_see_theirs(self):
        c = self.open_and_register()
        self.go("POST", f"/{c['id']}/assistants", token=self.cl, json={"email": "acl@test.com"})
        assert self.go("GET", "/mine", token=self.cl).json()["my_role"] == "leader"
        assert self.go("GET", "/mine", token=self.acl).json()["my_role"] == "assistant"

    def test_other_people_see_nothing(self):
        self.open_and_register()
        assert self.go("GET", "/mine", token=self.stranger).json() is None

    def test_a_withdrawn_contingent_is_not_shown(self):
        c = self.open_and_register()
        self.go("POST", f"/{c['id']}/withdraw", token=self.cl)
        assert self.go("GET", "/mine", token=self.cl).json() is None

    def test_a_rejected_one_is_shown_so_the_leader_can_read_why(self):
        c = self.open_and_register()
        self.go("POST", f"/{c['id']}/reject", json={"note": "Please use your full college name"})
        body = self.go("GET", "/mine", token=self.cl).json()
        assert body["status"] == "rejected" and "full college name" in body["note"]

    def test_an_active_one_wins_over_an_old_rejected_one(self):
        c = self.open_and_register()
        self.go("POST", f"/{c['id']}/reject", json={"note": "Please use your full college name"})
        self.register(college="Indian Institute of Technology Delhi")
        assert self.go("GET", "/mine", token=self.cl).json()["college_name"] == "Indian Institute of Technology Delhi"


class TestSeeingContingents(Visiting):
    def test_the_committee_sees_all_in_college_order(self):
        self.settings()
        self.register(college="zeta college")
        self.register(token=self.cl2, college="Alpha College")
        assert [c["college_name"] for c in self.go("GET", "").json()] == ["Alpha College", "zeta college"]

    def test_filter_by_status(self):
        self.settings()
        a = self.register(college="A College").json()["id"]
        self.register(token=self.cl2, college="B College")
        self.go("POST", f"/{a}/approve")
        assert [c["college_name"] for c in self.go("GET", "?status=approved").json()] == ["A College"]
        assert [c["college_name"] for c in self.go("GET", "?status=pending").json()] == ["B College"]

    def test_a_bad_filter_is_refused(self):
        assert self.go("GET", "?status=maybe").status_code == 422

    def test_only_the_committee_can_list_everything(self):
        self.settings()
        self.register()
        assert self.go("GET", "", token=self.cl).status_code == 403

    def test_leader_assistant_and_committee_can_open_one_but_not_outsiders(self):
        c = self.open_and_register()
        self.go("POST", f"/{c['id']}/assistants", token=self.cl, json={"email": "acl@test.com"})
        assert self.go("GET", f"/{c['id']}", token=self.cl).json()["my_role"] == "leader"
        assert self.go("GET", f"/{c['id']}", token=self.acl).json()["my_role"] == "assistant"
        assert self.go("GET", f"/{c['id']}", token=self.owner).json()["my_role"] == "staff"
        assert self.go("GET", f"/{c['id']}", token=self.cl2).status_code == 403

    def test_another_fests_contingent_is_not_found(self):
        c = self.open_and_register()
        self.start("fest-two")
        assert self.go("GET", f"/{c['id']}", slug="fest-two").status_code == 404

    def test_the_roster_check_reflects_the_fests_limits(self):
        c = self.open_and_register(min_members=2, max_members=3)
        assert c["roster_ok"] is False
        for n in ("A", "B"):
            c = self.go("POST", f"/{c['id']}/members", token=self.cl, json={"name": n}).json()
        assert c["roster_ok"] is True


class TestTheCommitteeDecides(Visiting):
    def test_approving_tells_the_leader(self):
        c = self.open_and_register()
        r = self.go("POST", f"/{c['id']}/approve", json={"note": "Welcome!"})
        assert r.json()["status"] == "approved" and r.json()["note"] == "Welcome!"
        title, body = notices_for("cl@test.com", "contingent")[0]
        assert "approved" in title and "Welcome!" in body

    def test_approving_needs_no_note(self):
        c = self.open_and_register()
        assert self.go("POST", f"/{c['id']}/approve").status_code == 200

    def test_rejecting_needs_a_reason(self):
        c = self.open_and_register()
        assert self.go("POST", f"/{c['id']}/reject", json={}).status_code == 400
        assert self.go("POST", f"/{c['id']}/reject", json={"note": "no"}).status_code == 400
        r = self.go("POST", f"/{c['id']}/reject", json={"note": "We do not recognise this college"})
        assert r.json()["status"] == "rejected" and "not approved" in notices_for("cl@test.com", "contingent")[0][0]

    def test_rejecting_releases_a_code_and_name(self):
        c = self.open_and_register()
        self.go("PATCH", f"/{c['id']}/assign", json={"code": "AL01", "name": "Phoenix"})
        r = self.go("POST", f"/{c['id']}/reject", json={"note": "Not a college we know"})
        assert r.json()["code"] is None and r.json()["name"] is None

    def test_a_rejected_one_can_be_approved_later(self):
        c = self.open_and_register()
        self.go("POST", f"/{c['id']}/reject", json={"note": "Not sure about this one"})
        assert self.go("POST", f"/{c['id']}/approve").json()["status"] == "approved"

    def test_only_the_committee_decides_not_even_the_leader(self):
        c = self.open_and_register()
        assert self.go("POST", f"/{c['id']}/approve", token=self.cl).status_code == 403
        assert self.go("POST", f"/{c['id']}/reject", token=self.cl, json={"note": "Reject myself"}).status_code == 403

    def test_a_withdrawn_one_cannot_be_decided(self):
        c = self.open_and_register()
        self.go("POST", f"/{c['id']}/withdraw", token=self.cl)
        assert self.go("POST", f"/{c['id']}/approve").status_code == 400


class TestCodesAndNames(Visiting):
    def test_the_committee_gives_a_code_and_a_name(self):
        c = self.open_and_register()
        r = self.go("PATCH", f"/{c['id']}/assign", json={"code": "AL01", "name": "Phoenix"})
        assert r.status_code == 200 and r.json()["code"] == "AL01" and r.json()["name"] == "Phoenix"
        assert "Phoenix" in notices_for("cl@test.com", "contingent")[0][1]

    def test_only_what_is_sent_changes_and_empty_clears(self):
        c = self.open_and_register()
        self.go("PATCH", f"/{c['id']}/assign", json={"code": "AL01", "name": "Phoenix"})
        r = self.go("PATCH", f"/{c['id']}/assign", json={"name": "Falcon"}).json()
        assert r["code"] == "AL01" and r["name"] == "Falcon"
        r = self.go("PATCH", f"/{c['id']}/assign", json={"code": ""}).json()
        assert r["code"] is None and r["name"] == "Falcon"

    def test_two_contingents_cannot_share_a_name_or_code_ignoring_case(self):
        a = self.open_and_register()
        self.go("PATCH", f"/{a['id']}/assign", json={"code": "AL01", "name": "Phoenix"})
        b = self.register(token=self.cl2, college="IIT Bombay").json()
        assert self.go("PATCH", f"/{b['id']}/assign", json={"name": "phoenix"}).status_code == 400
        assert self.go("PATCH", f"/{b['id']}/assign", json={"code": "al01"}).status_code == 400

    def test_keeping_your_own_value_is_fine_and_sends_no_new_notice(self):
        c = self.open_and_register()
        self.go("PATCH", f"/{c['id']}/assign", json={"name": "Phoenix"})
        before = len(notices_for("cl@test.com", "contingent"))
        assert self.go("PATCH", f"/{c['id']}/assign", json={"name": "Phoenix"}).status_code == 200
        assert len(notices_for("cl@test.com", "contingent")) == before

    def test_only_the_committee_can_assign(self):
        c = self.open_and_register()
        assert self.go("PATCH", f"/{c['id']}/assign", token=self.cl, json={"name": "Phoenix"}).status_code == 403

    def test_a_rejected_or_withdrawn_contingent_cannot_hold_them(self):
        c = self.open_and_register()
        self.go("POST", f"/{c['id']}/reject", json={"note": "Not a college we know"})
        assert self.go("PATCH", f"/{c['id']}/assign", json={"name": "Phoenix"}).status_code == 400

    def test_a_withdrawn_contingent_frees_its_name_and_code_for_the_next(self):
        a = self.open_and_register()
        self.go("PATCH", f"/{a['id']}/assign", json={"code": "AL01", "name": "Phoenix"})
        self.go("POST", f"/{a['id']}/withdraw", token=self.cl)
        b = self.register(token=self.cl2, college="IIT Bombay").json()
        assert self.go("PATCH", f"/{b['id']}/assign", json={"code": "AL01", "name": "Phoenix"}).status_code == 200


class TestWithdrawingAndDeleting(Visiting):
    def test_the_leader_can_withdraw_and_the_committee_is_told(self):
        c = self.open_and_register()
        r = self.go("POST", f"/{c['id']}/withdraw", token=self.cl)
        assert r.json()["status"] == "withdrawn"
        assert any("withdrew" in t for t, _ in notices_for("owner@test.com", "contingent"))

    def test_an_assistant_cannot_withdraw_it(self):
        c = self.open_and_register()
        self.go("POST", f"/{c['id']}/assistants", token=self.cl, json={"email": "acl@test.com"})
        assert self.go("POST", f"/{c['id']}/withdraw", token=self.acl).status_code == 403

    def test_the_committee_can_withdraw_one_without_a_notice_to_itself(self):
        c = self.open_and_register()
        before = len(notices_for("owner@test.com", "contingent"))
        assert self.go("POST", f"/{c['id']}/withdraw").status_code == 200
        assert len(notices_for("owner@test.com", "contingent")) == before

    def test_withdrawing_twice_is_refused(self):
        c = self.open_and_register()
        self.go("POST", f"/{c['id']}/withdraw", token=self.cl)
        assert self.go("POST", f"/{c['id']}/withdraw", token=self.cl).status_code == 400

    def test_only_the_committee_can_delete_and_it_takes_the_roster_with_it(self):
        c = self.open_and_register()
        self.go("POST", f"/{c['id']}/members", token=self.cl, json={"name": "Asha"})
        assert self.go("DELETE", f"/{c['id']}", token=self.cl).status_code == 403
        assert self.go("DELETE", f"/{c['id']}").status_code == 204
        db = TestingSessionLocal()
        assert db.query(models.ContingentMember).count() == 0 and db.query(models.Contingent).count() == 0
        db.close()

    def test_another_fests_contingent_cannot_be_deleted(self):
        c = self.open_and_register()
        self.start("fest-two")
        assert self.go("DELETE", f"/{c['id']}", slug="fest-two").status_code == 404


class TestChangingTheCollege(Visiting):
    def test_the_leader_can_correct_the_name(self):
        c = self.open_and_register()
        r = self.go("PATCH", f"/{c['id']}", token=self.cl, json={"college_name": "Indian Institute of Technology Delhi"})
        assert r.json()["college_name"] == "Indian Institute of Technology Delhi"

    def test_an_assistant_cannot(self):
        c = self.open_and_register()
        self.go("POST", f"/{c['id']}/assistants", token=self.cl, json={"email": "acl@test.com"})
        assert self.go("PATCH", f"/{c['id']}", token=self.acl, json={"college_name": "Elsewhere"}).status_code == 403

    def test_it_cannot_be_changed_to_a_college_that_already_has_one(self):
        self.open_and_register()
        b = self.register(token=self.cl2, college="IIT Bombay").json()
        assert self.go("PATCH", f"/{b['id']}", token=self.cl2, json={"college_name": "iit delhi"}).status_code == 400

    def test_keeping_your_own_name_is_fine(self):
        c = self.open_and_register()
        assert self.go("PATCH", f"/{c['id']}", token=self.cl, json={"college_name": "IIT Delhi"}).status_code == 200

    def test_a_rejected_contingent_cannot_be_edited(self):
        c = self.open_and_register()
        self.go("POST", f"/{c['id']}/reject", json={"note": "Not a college we know"})
        assert self.go("PATCH", f"/{c['id']}", token=self.cl, json={"college_name": "Fixed Name"}).status_code == 400


class TestAssistants(Visiting):
    def test_the_leader_can_add_an_assistant_who_is_told(self):
        c = self.open_and_register()
        r = self.go("POST", f"/{c['id']}/assistants", token=self.cl, json={"email": "acl@test.com"})
        assert r.status_code == 201 and r.json()["assistant_count"] == 1 and r.json()["assistants"][0]["user_name"] == "Assistant One"
        assert len(notices_for("acl@test.com", "contingent")) == 1

    def test_the_fests_limit_applies(self):
        c = self.open_and_register(max_assistants=1)
        self.go("POST", f"/{c['id']}/assistants", token=self.cl, json={"email": "acl@test.com"})
        assert self.go("POST", f"/{c['id']}/assistants", token=self.cl, json={"email": "cl2@test.com"}).status_code == 400

    def test_a_fest_can_allow_no_assistants(self):
        c = self.open_and_register(max_assistants=0)
        assert self.go("POST", f"/{c['id']}/assistants", token=self.cl, json={"email": "acl@test.com"}).status_code == 400

    def test_an_unknown_email_is_refused(self):
        c = self.open_and_register()
        r = self.go("POST", f"/{c['id']}/assistants", token=self.cl, json={"email": "ghost@test.com"})
        assert r.status_code == 404 and "sign up" in r.json()["detail"]

    def test_the_leader_cannot_assist_themselves(self):
        c = self.open_and_register()
        assert self.go("POST", f"/{c['id']}/assistants", token=self.cl, json={"email": "cl@test.com"}).status_code == 400

    def test_someone_already_in_another_contingent_cannot_be_added(self):
        c = self.open_and_register()
        self.register(token=self.cl2, college="IIT Bombay")
        assert self.go("POST", f"/{c['id']}/assistants", token=self.cl, json={"email": "cl2@test.com"}).status_code == 400

    def test_the_same_person_cannot_be_added_twice(self):
        c = self.open_and_register()
        self.go("POST", f"/{c['id']}/assistants", token=self.cl, json={"email": "acl@test.com"})
        assert self.go("POST", f"/{c['id']}/assistants", token=self.cl, json={"email": "acl@test.com"}).status_code == 400

    def test_only_the_leader_or_the_committee_can_add(self):
        c = self.open_and_register()
        self.go("POST", f"/{c['id']}/assistants", token=self.cl, json={"email": "acl@test.com"})
        assert self.go("POST", f"/{c['id']}/assistants", token=self.acl, json={"email": "nobody@test.com"}).status_code == 403
        assert self.go("POST", f"/{c['id']}/assistants", token=self.stranger, json={"email": "nobody@test.com"}).status_code == 403
        assert self.go("POST", f"/{c['id']}/assistants", token=self.owner, json={"email": "nobody@test.com"}).status_code == 201

    def test_the_leader_can_remove_an_assistant_and_an_assistant_can_leave(self):
        c = self.open_and_register()
        self.go("POST", f"/{c['id']}/assistants", token=self.cl, json={"email": "acl@test.com"})
        assert self.go("DELETE", f"/{c['id']}/assistants/{user_id('acl@test.com')}", token=self.cl).json()["assistant_count"] == 0
        self.go("POST", f"/{c['id']}/assistants", token=self.cl, json={"email": "acl@test.com"})
        assert self.go("DELETE", f"/{c['id']}/assistants/{user_id('acl@test.com')}", token=self.acl).status_code == 200
        assert self.go("GET", "/mine", token=self.acl).json() is None

    def test_an_assistant_cannot_remove_someone_else(self):
        c = self.open_and_register()
        self.go("POST", f"/{c['id']}/assistants", token=self.cl, json={"email": "acl@test.com"})
        self.go("POST", f"/{c['id']}/assistants", token=self.cl, json={"email": "nobody@test.com"})
        assert self.go("DELETE", f"/{c['id']}/assistants/{user_id('nobody@test.com')}", token=self.acl).status_code == 403

    def test_removing_someone_who_is_not_an_assistant_is_not_found(self):
        c = self.open_and_register()
        assert self.go("DELETE", f"/{c['id']}/assistants/{user_id('nobody@test.com')}", token=self.cl).status_code == 404

    def test_a_rejected_contingent_takes_no_new_assistants(self):
        c = self.open_and_register()
        self.go("POST", f"/{c['id']}/reject", json={"note": "Not a college we know"})
        assert self.go("POST", f"/{c['id']}/assistants", token=self.cl, json={"email": "acl@test.com"}).status_code == 400


class TestTheRoster(Visiting):
    def member(self, c, token=None, **kw):
        return self.go("POST", f"/{c['id']}/members", token=token or self.cl, json={"name": "Asha Rao", **kw})

    def test_the_leader_an_assistant_and_the_committee_can_add_people(self):
        c = self.open_and_register()
        self.go("POST", f"/{c['id']}/assistants", token=self.cl, json={"email": "acl@test.com"})
        for token in (self.cl, self.acl, self.owner):
            assert self.member(c, token).status_code == 201
        assert self.go("GET", f"/{c['id']}", token=self.cl).json()["member_count"] == 3

    def test_everything_about_a_delegate_is_kept(self):
        c = self.open_and_register()
        body = self.member(c, email="asha@college.edu", phone="+91 98765 43210", year=3, notes="Vegetarian").json()["members"][0]
        assert body["email"] == "asha@college.edu" and body["phone"] == "+91 98765 43210" and body["year"] == 3 and body["notes"] == "Vegetarian"

    def test_outsiders_cannot_touch_the_roster(self):
        c = self.open_and_register()
        assert self.member(c, self.stranger).status_code == 403
        assert self.member(c, self.cl2).status_code == 403

    def test_the_fests_size_limit_applies_to_the_college_but_not_the_committee(self):
        c = self.open_and_register(max_members=2)
        assert self.go("POST", f"/{c['id']}/members", token=self.cl, json={"name": "A"}).status_code == 201
        assert self.go("POST", f"/{c['id']}/members", token=self.cl, json={"name": "B"}).status_code == 201
        assert self.go("POST", f"/{c['id']}/members", token=self.cl, json={"name": "C"}).status_code == 400
        assert self.go("POST", f"/{c['id']}/members", token=self.owner, json={"name": "C"}).status_code == 201

    def test_the_same_email_cannot_be_on_the_roster_twice(self):
        c = self.open_and_register()
        self.member(c, email="asha@college.edu")
        assert self.go("POST", f"/{c['id']}/members", token=self.cl, json={"name": "Other", "email": "ASHA@college.edu"}).status_code == 400

    def test_two_people_with_no_email_are_fine(self):
        c = self.open_and_register()
        assert self.member(c).status_code == 201 and self.member(c).status_code == 201

    def test_a_blank_name_or_bad_details_are_refused(self):
        c = self.open_and_register()
        assert self.go("POST", f"/{c['id']}/members", token=self.cl, json={"name": "   "}).status_code == 422
        assert self.member(c, email="not-an-email").status_code == 422
        assert self.member(c, year=0).status_code == 422

    def test_a_delegate_can_be_changed_and_null_clears_a_field(self):
        c = self.open_and_register()
        mid = self.member(c, year=2, notes="x").json()["members"][0]["id"]
        r = self.go("PATCH", f"/{c['id']}/members/{mid}", token=self.cl, json={"name": "Asha R.", "year": None, "notes": None}).json()["members"][0]
        assert r["name"] == "Asha R." and r["year"] is None and r["notes"] is None

    def test_changing_a_name_to_blank_is_refused(self):
        c = self.open_and_register()
        mid = self.member(c).json()["members"][0]["id"]
        assert self.go("PATCH", f"/{c['id']}/members/{mid}", token=self.cl, json={"name": "  "}).status_code in (400, 422)

    def test_changing_an_email_to_one_already_there_is_refused(self):
        c = self.open_and_register()
        self.member(c, email="a@college.edu")
        mid = self.go("POST", f"/{c['id']}/members", token=self.cl, json={"name": "B", "email": "b@college.edu"}).json()["members"][1]["id"]
        assert self.go("PATCH", f"/{c['id']}/members/{mid}", token=self.cl, json={"email": "a@college.edu"}).status_code == 400

    def test_a_delegate_can_be_removed(self):
        c = self.open_and_register()
        mid = self.member(c).json()["members"][0]["id"]
        assert self.go("DELETE", f"/{c['id']}/members/{mid}", token=self.cl).json()["member_count"] == 0

    def test_a_delegate_of_another_contingent_is_not_found(self):
        a = self.open_and_register()
        b = self.register(token=self.cl2, college="IIT Bombay").json()
        mid = self.member(b, token=self.cl2).json()["members"][0]["id"]
        assert self.go("DELETE", f"/{a['id']}/members/{mid}", token=self.cl).status_code == 404

    def test_the_roster_locks_once_registration_has_closed_but_not_for_the_committee(self):
        c = self.open_and_register(closes_on=day(5))
        mid = self.member(c).json()["members"][0]["id"]
        self.settings(closes_on=day(-1))
        assert self.go("POST", f"/{c['id']}/members", token=self.cl, json={"name": "Late"}).status_code == 400
        assert self.go("DELETE", f"/{c['id']}/members/{mid}", token=self.cl).status_code == 400
        assert self.go("GET", f"/{c['id']}", token=self.cl).json()["roster_open"] is False
        assert self.go("POST", f"/{c['id']}/members", token=self.owner, json={"name": "Committee added"}).status_code == 201
        assert self.go("GET", f"/{c['id']}", token=self.owner).json()["roster_open"] is True

    def test_a_fest_can_keep_the_roster_open_after_closing(self):
        c = self.open_and_register(closes_on=day(5))
        self.settings(closes_on=day(-1), lock_roster_after_close=False)
        assert self.member(c).status_code == 201

    def test_a_rejected_contingent_cannot_change_its_roster(self):
        c = self.open_and_register()
        self.go("POST", f"/{c['id']}/reject", json={"note": "Not a college we know"})
        assert self.member(c).status_code == 400
