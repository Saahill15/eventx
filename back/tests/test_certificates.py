"""Certificates: the committee's wording, issuing them in bulk or one by one, and checking one by its code."""

from test_fixes import user_token  # noqa: F401
from test_full import client, auth, reset_db, get_entry_pass, TestingSessionLocal  # noqa: F401
from test_organiser import event_payload
from test_ticketing import Box
from test_committee_meetings import notices_for
from app import models

FEST = "fest-live"


class Certs(Box):
    """A live fest with a free open event, and a student who went to it."""

    def setup_method(self):
        super().setup_method()
        r = client.post("/api/events/", json=event_payload(self.fest["id"], title="Battle of Bands", date="2026-12-05T00:00:00"), headers=auth(self.owner))
        self.show = r.json()
        self.pass_code = get_entry_pass(self.student, FEST).json()["qr_code"]
        self.templates = {t["kind"]: t for t in self.c("POST", "/certificate-templates/usual").json()}

    def c(self, method, path, token=None, **kw):
        return client.request(method, f"/api/fests/{FEST}{path}", headers=auth(token or self.owner), **kw)

    def attend(self, token=None, pass_code=None, event=None):
        r = client.post(f"/api/fest-events/{(event or self.show)['id']}/check-in", json={"qr_code": pass_code or self.pass_code}, headers=auth(token or self.owner))
        assert r.status_code == 200, r.text

    def issue_attended(self, kind="participation", event=None):
        return self.c("POST", "/certificates/issue-attended", json={"event_id": (event or self.show)["id"], "template_id": self.templates[kind]["id"]})

    def listing(self, **q):
        qs = "&".join(f"{k}={v}" for k, v in q.items())
        return self.c("GET", f"/certificates{'?' + qs if qs else ''}").json()

    def mine(self, token=None):
        return client.get("/api/users/me/certificates", headers=auth(token or self.student)).json()

    def check(self, code):
        return client.get(f"/api/certificates/{code}")


class TestWording(Certs):
    def test_a_usual_wording_for_each_kind_is_offered_once(self):
        assert set(self.templates) == {"participation", "winner", "appreciation"}
        again = self.c("POST", "/certificate-templates/usual").json()
        assert len(again) == 3

    def test_the_wording_is_the_committees_own(self):
        r = self.c("POST", "/certificate-templates", json={"kind": "participation", "title": "Proof of Taking Part", "body": "{name} was part of {event}.", "signatories": [{"name": "Dr Rao", "title": "Principal"}, {"name": "Meera", "title": "Chairperson"}]})
        assert r.status_code == 201 and len(r.json()["signatories"]) == 2
        t = self.c("PATCH", f"/certificate-templates/{r.json()['id']}", json={"title": "Taking Part", "signatories": [{"name": "Dr Rao", "title": "Principal"}]}).json()
        assert t["title"] == "Taking Part" and len(t["signatories"]) == 1
        assert self.c("DELETE", f"/certificate-templates/{r.json()['id']}").status_code == 204

    def test_at_most_three_signatures_and_a_title_and_body_are_needed(self):
        sig = {"name": "A", "title": "x"}
        assert self.c("POST", "/certificate-templates", json={"title": "T", "body": "B", "signatories": [sig] * 4}).status_code == 422
        assert self.c("POST", "/certificate-templates", json={"title": "", "body": "B"}).status_code == 422
        assert self.c("POST", "/certificate-templates", json={"title": "T", "body": ""}).status_code == 422

    def test_a_wording_can_be_for_one_event_only(self):
        t = self.c("POST", "/certificate-templates", json={"event_id": self.show["id"], "kind": "winner", "title": "Band Winner", "body": "{name} won {event}."}).json()
        assert t["event_title"] == "Battle of Bands"
        other = self.make_event(title="Other event", is_paid=False, is_free=True, price=0)
        r = self.c("POST", "/certificates/issue-attended", json={"event_id": other["id"], "template_id": t["id"]})
        assert r.status_code == 400 and "different event" in r.json()["detail"]
        assert self.c("POST", "/certificate-templates", json={"event_id": 99999, "title": "T", "body": "B"}).status_code == 404

    def test_only_the_committee_manages_wordings(self):
        assert self.c("GET", "/certificate-templates", self.student).status_code == 403
        assert self.c("POST", "/certificate-templates", self.student, json={"title": "T", "body": "B"}).status_code == 403
        assert self.c("POST", "/certificate-templates/usual", self.student).status_code == 403


class TestIssuing(Certs):
    def test_everyone_who_attended_gets_one_and_only_them(self):
        other = user_token("Skipped", "skip@test.com")
        get_entry_pass(other, FEST)
        self.attend()
        r = self.issue_attended()
        assert r.status_code == 201 and r.json() == {"issued": 1, "skipped": 0}
        c = self.mine()[0]
        assert c["recipient_name"] == "Student User" or c["recipient_name"].startswith("Student")
        assert "Battle of Bands" in c["body"] and "Spectrum" not in c["body"] and c["event_title"] == "Battle of Bands" and c["fest_name"] == "Fest One"
        assert self.mine(other) == []

    def test_the_wording_is_filled_in_for_each_person(self):
        self.attend(); self.issue_attended()
        c = self.mine()[0]
        assert c["title"] == "Certificate of Participation" and c["body"].startswith("This is to certify that Student") and "5 December 2026" in c["body"] and "{" not in c["body"]

    def test_running_it_again_issues_nothing_new(self):
        self.attend(); self.issue_attended()
        assert self.issue_attended().json() == {"issued": 0, "skipped": 1}
        assert len(self.listing()) == 1

    def test_a_different_kind_is_a_separate_certificate(self):
        self.attend(); self.issue_attended("participation")
        assert self.issue_attended("appreciation").json()["issued"] == 1

    def test_withdrawing_one_lets_it_be_issued_again(self):
        self.attend(); self.issue_attended()
        cid = self.listing()[0]["id"]
        self.c("POST", f"/certificates/{cid}/revoke", json={"reason": "Wrong spelling"})
        assert self.issue_attended().json()["issued"] == 1

    def test_the_person_is_told(self):
        self.attend(); self.issue_attended()
        assert any("Certificate of Participation" in t for t, _ in notices_for("student@test.com", "certificate"))

    def test_nobody_attended_means_nothing_issued(self):
        assert self.issue_attended().json() == {"issued": 0, "skipped": 0}

    def test_each_certificate_has_its_own_short_code(self):
        other = user_token("Second", "second@test.com")
        code2 = get_entry_pass(other, FEST).json()["qr_code"]
        self.attend(); self.attend(pass_code=code2)
        self.issue_attended()
        codes = [c["code"] for c in self.listing()]
        assert len(codes) == 2 and len(set(codes)) == 2 and all(len(c) == 10 and c.isalnum() and c == c.upper() for c in codes)

    def test_one_can_be_given_by_hand_with_a_line_such_as_the_place(self):
        r = self.c("POST", "/certificates", json={"template_id": self.templates["winner"]["id"], "recipient_name": "Ravi Kumar", "event_id": self.show["id"], "award_text": "First place", "college_name": "NIT Surat"})
        c = r.json()
        assert r.status_code == 201 and c["award_text"] == "First place" and "Ravi Kumar secured First place in Battle of Bands" in c["body"] and c["has_account"] is False and c["college_name"] == "NIT Surat"

    def test_giving_an_email_puts_it_on_that_persons_page(self):
        self.c("POST", "/certificates", json={"template_id": self.templates["appreciation"]["id"], "recipient_name": "Asha", "email": "student@test.com"})
        assert len(self.mine()) == 1 and self.mine()[0]["has_account"] is True

    def test_an_email_with_no_account_is_refused(self):
        r = self.c("POST", "/certificates", json={"template_id": self.templates["appreciation"]["id"], "recipient_name": "Ghost", "email": "ghost@example.com"})
        assert r.status_code == 404

    def test_an_event_or_wording_of_another_fest_is_refused(self):
        self.start("fest-two")
        theirs = client.post("/api/fests/fest-two/certificate-templates/usual", headers=auth(self.owner)).json()[0]
        r = self.c("POST", "/certificates", json={"template_id": theirs["id"], "recipient_name": "X"})
        assert r.status_code == 404

    def test_only_the_committee_issues(self):
        assert self.c("POST", "/certificates", self.student, json={"template_id": self.templates["winner"]["id"], "recipient_name": "Me"}).status_code == 403
        assert self.c("POST", "/certificates/issue-attended", self.student, json={"event_id": self.show["id"], "template_id": self.templates["participation"]["id"]}).status_code == 403
        assert self.c("GET", "/certificates", self.student).status_code == 403

    def test_the_people_in_a_visiting_colleges_entries_get_theirs_without_accounts(self):
        db = TestingSessionLocal()
        fest = db.query(models.Fest).filter(models.Fest.slug == FEST).first()
        leader = db.query(models.User).filter(models.User.email == "student@test.com").first()
        db.add(models.ContingentSettings(fest_id=fest.id, enabled=True))
        c = models.Contingent(fest_id=fest.id, college_name="IIT Delhi", status="approved", leader_user_id=leader.id)
        db.add(c); db.flush()
        m1, m2 = models.ContingentMember(contingent_id=c.id, name="Asha Rao"), models.ContingentMember(contingent_id=c.id, name="Ravi Shah")
        db.add_all([m1, m2]); db.flush()
        entry = models.ContingentEntry(fest_id=fest.id, contingent_id=c.id, event_id=self.show["id"], status="confirmed")
        entry.members = [models.ContingentEntryMember(member_id=m1.id), models.ContingentEntryMember(member_id=m2.id)]
        db.add(entry); db.commit(); db.close()
        r = self.c("POST", "/certificates/issue-entries", json={"event_id": self.show["id"], "template_id": self.templates["participation"]["id"]})
        assert r.status_code == 201 and r.json() == {"issued": 2, "skipped": 0}
        rows = self.listing()
        assert {x["recipient_name"] for x in rows} == {"Asha Rao", "Ravi Shah"} and all(x["college_name"] == "IIT Delhi" and not x["has_account"] for x in rows)
        assert self.c("POST", "/certificates/issue-entries", json={"event_id": self.show["id"], "template_id": self.templates["participation"]["id"]}).json() == {"issued": 0, "skipped": 2}


class TestKeepingAndChecking(Certs):
    def issue_one(self, **extra):
        r = self.c("POST", "/certificates", json={"template_id": self.templates["winner"]["id"], "recipient_name": "Ravi Kumar", "event_id": self.show["id"], "award_text": "First place", **extra})
        assert r.status_code == 201
        return r.json()

    def test_anyone_with_the_code_can_check_it_without_signing_in(self):
        c = self.issue_one()
        r = self.check(c["code"])
        assert r.status_code == 200 and r.json()["valid"] is True and r.json()["certificate"]["recipient_name"] == "Ravi Kumar" and r.json()["certificate"]["event_title"] == "Battle of Bands"

    def test_the_code_works_in_any_case(self):
        c = self.issue_one()
        assert self.check(c["code"].lower()).json()["valid"] is True

    def test_an_unknown_code_is_simply_not_valid(self):
        r = self.check("NOSUCHCODE")
        assert r.status_code == 200 and r.json() == {"valid": False, "revoked": False, "certificate": None}

    def test_a_withdrawn_certificate_says_so(self):
        c = self.issue_one()
        r = self.c("POST", f"/certificates/{c['id']}/revoke", json={"reason": "Issued by mistake"}).json()
        assert r["revoked"] is True and r["revoked_reason"] == "Issued by mistake"
        check = self.check(c["code"]).json()
        assert check["valid"] is False and check["revoked"] is True and check["certificate"]["recipient_name"] == "Ravi Kumar"
        assert self.c("POST", f"/certificates/{c['id']}/revoke", json={"reason": "Again"}).status_code == 400

    def test_a_withdrawn_one_leaves_the_persons_page(self):
        c = self.issue_one(email="student@test.com")
        assert len(self.mine()) == 1
        self.c("POST", f"/certificates/{c['id']}/revoke", json={"reason": "Wrong person"})
        assert self.mine() == []

    def test_a_reason_is_needed_to_withdraw_one(self):
        c = self.issue_one()
        assert self.c("POST", f"/certificates/{c['id']}/revoke", json={"reason": "x"}).status_code == 422

    def test_what_was_issued_is_unchanged_when_the_wording_changes_or_goes(self):
        c = self.issue_one()
        self.c("PATCH", f"/certificate-templates/{self.templates['winner']['id']}", json={"title": "Totally different", "body": "New text"})
        self.c("DELETE", f"/certificate-templates/{self.templates['winner']['id']}")
        got = self.check(c["code"]).json()["certificate"]
        assert got["title"] == "Certificate of Achievement" and "secured First place" in got["body"]

    def test_the_committee_can_list_by_event(self):
        self.issue_one()
        self.c("POST", "/certificates", json={"template_id": self.templates["appreciation"]["id"], "recipient_name": "Someone"})
        assert len(self.listing()) == 2 and len(self.listing(event_id=self.show["id"])) == 1

    def test_a_person_sees_only_their_own(self):
        self.issue_one(email="student@test.com")
        other = user_token("Other", "other@test.com")
        assert len(self.mine()) == 1 and self.mine(other) == []
        assert client.get("/api/users/me/certificates").status_code == 401

    def test_unknown_braces_in_the_wording_are_left_as_written(self):
        t = self.c("POST", "/certificate-templates", json={"title": "Thanks {name}", "body": "Well done {name} {nickname}", "kind": "appreciation"}).json()
        r = self.c("POST", "/certificates", json={"template_id": t["id"], "recipient_name": "Asha"}).json()
        assert r["title"] == "Thanks Asha" and r["body"] == "Well done Asha {nickname}"

    def test_deleting_an_event_keeps_its_certificates(self):
        e = self.make_event(title="Short lived", is_paid=False, is_free=True, price=0)
        r = self.c("POST", "/certificates", json={"template_id": self.templates["participation"]["id"], "recipient_name": "Asha", "event_id": e["id"]}).json()
        client.delete(f"/api/events/{e['id']}", headers=auth(self.owner))
        got = self.check(r["code"]).json()
        assert got["valid"] is True and got["certificate"]["event_title"] == "Short lived"
