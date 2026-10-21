"""Student verification (college email code and uploaded proof), students-only events and student pricing."""

import io
from datetime import datetime, timedelta

import pytest

from test_fixes import user_token, user_id  # noqa: F401
from test_full import (
    client, auth, create_college, create_fest, create_fest_event, get_entry_pass, reset_db, TestingSessionLocal,  # noqa: F401
)
from app import mailer, models
from app.routes import student as student_routes

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 300


@pytest.fixture
def mails(monkeypatch):
    sent = []
    monkeypatch.setattr(student_routes, "send_email", lambda to, subject, text: sent.append((to, subject, text)))
    return sent


def code_from(mails):
    return mails[-1][2].split("code is ")[1][:6]


class Setup:
    def setup_method(self):
        self.admin = user_token("Admin", "admin@test.com", "admin")
        self.student = user_token("Asha", "asha@gmail.com")
        self.other = user_token("Ben", "ben@gmail.com")
        r = client.post("/api/colleges/", json={"name": "IIT Bombay", "email_domains": "iitb.ac.in"}, headers=auth(self.admin))
        assert r.status_code == 200, r.text
        self.college_id = r.json()["id"]

    def status(self, token=None):
        return client.get("/api/users/me/student", headers=auth(token or self.student)).json()


class TestCollegeDomains(Setup):
    def test_domains_are_cleaned_and_validated(self):
        r = client.post("/api/colleges/", json={"name": "VJTI", "email_domains": " @VJTI.ac.in, vjti.ac.in ,xyz.edu"}, headers=auth(self.admin))
        assert r.json()["email_domains"] == "vjti.ac.in,xyz.edu"
        assert client.post("/api/colleges/", json={"name": "Bad", "email_domains": "not a domain"}, headers=auth(self.admin)).status_code == 422


class TestEmailVerification(Setup):
    def test_full_flow_with_a_known_college_domain(self, mails):
        r = client.post("/api/users/me/student/email", json={"email": "asha@iitb.ac.in"}, headers=auth(self.student))
        assert r.status_code == 200, r.text
        assert mails and mails[0][0] == "asha@iitb.ac.in"
        r = client.post("/api/users/me/student/email/confirm", json={"code": code_from(mails)}, headers=auth(self.student))
        assert r.status_code == 200 and r.json()["verified"] is True and r.json()["college_id"] == self.college_id
        me = client.get("/api/users/me", headers=auth(self.student)).json()
        assert me["is_student_verified"] is True and me["college_id"] == self.college_id

    def test_subdomains_of_a_college_domain_count(self, mails):
        r = client.post("/api/users/me/student/email", json={"email": "asha@cse.iitb.ac.in"}, headers=auth(self.student))
        assert r.status_code == 200

    def test_wrong_code_then_lockout(self, mails):
        client.post("/api/users/me/student/email", json={"email": "asha@iitb.ac.in"}, headers=auth(self.student))
        for _ in range(5):
            assert client.post("/api/users/me/student/email/confirm", json={"code": "000000"}, headers=auth(self.student)).status_code == 400
        r = client.post("/api/users/me/student/email/confirm", json={"code": code_from(mails)}, headers=auth(self.student))
        assert r.status_code == 400 and "Too many" in r.json()["detail"]
        assert self.status()["verified"] is False

    def test_expired_code(self, mails):
        client.post("/api/users/me/student/email", json={"email": "asha@iitb.ac.in"}, headers=auth(self.student))
        db = TestingSessionLocal()
        db.query(models.StudentVerification).update({"code_expires_at": datetime.utcnow() - timedelta(minutes=1)})
        db.commit(); db.close()
        r = client.post("/api/users/me/student/email/confirm", json={"code": code_from(mails)}, headers=auth(self.student))
        assert r.status_code == 400 and "expired" in r.json()["detail"]

    def test_non_college_email_is_refused(self, mails):
        r = client.post("/api/users/me/student/email", json={"email": "asha@yahoo.com"}, headers=auth(self.student))
        assert r.status_code == 400 and "college email" in r.json()["detail"]
        assert mails == []

    def test_unknown_academic_domain_needs_a_college_choice(self, mails):
        r = client.post("/api/users/me/student/email", json={"email": "asha@somecollege.edu.in"}, headers=auth(self.student))
        assert r.status_code == 400 and "Choose your college" in r.json()["detail"]
        r = client.post("/api/users/me/student/email", json={"email": "asha@somecollege.edu.in", "college_id": self.college_id}, headers=auth(self.student))
        assert r.status_code == 200

    def test_one_email_cannot_verify_two_accounts(self, mails):
        client.post("/api/users/me/student/email", json={"email": "shared@iitb.ac.in"}, headers=auth(self.student))
        client.post("/api/users/me/student/email/confirm", json={"code": code_from(mails)}, headers=auth(self.student))
        r = client.post("/api/users/me/student/email", json={"email": "shared@iitb.ac.in"}, headers=auth(self.other))
        assert r.status_code == 400 and "another account" in r.json()["detail"]

    def test_already_verified_cannot_start_again_until_renewal_window(self, mails):
        client.post("/api/users/me/student/email", json={"email": "asha@iitb.ac.in"}, headers=auth(self.student))
        client.post("/api/users/me/student/email/confirm", json={"code": code_from(mails)}, headers=auth(self.student))
        assert self.status()["can_verify"] is False
        assert client.post("/api/users/me/student/email", json={"email": "asha2@iitb.ac.in"}, headers=auth(self.student)).status_code == 400
        db = TestingSessionLocal()
        db.query(models.User).filter(models.User.email == "asha@gmail.com").update({"student_verified_until": datetime.utcnow() + timedelta(days=10)})
        db.commit(); db.close()
        assert self.status()["can_verify"] is True
        assert client.post("/api/users/me/student/email", json={"email": "asha2@iitb.ac.in"}, headers=auth(self.student)).status_code == 200

    def test_verification_expires_after_a_year(self, mails):
        client.post("/api/users/me/student/email", json={"email": "asha@iitb.ac.in"}, headers=auth(self.student))
        client.post("/api/users/me/student/email/confirm", json={"code": code_from(mails)}, headers=auth(self.student))
        db = TestingSessionLocal()
        db.query(models.User).filter(models.User.email == "asha@gmail.com").update({"student_verified_until": datetime.utcnow() - timedelta(days=1)})
        db.commit(); db.close()
        assert client.get("/api/users/me", headers=auth(self.student)).json()["is_student_verified"] is False

    def test_rate_limit(self, mails):
        codes = [client.post("/api/users/me/student/email", json={"email": "asha@iitb.ac.in"}, headers=auth(self.student)).status_code for _ in range(6)]
        assert codes[:5] == [200] * 5 and codes[5] == 429

    def test_missing_email_service_gives_a_clear_message(self, monkeypatch):
        def boom(*a, **k):
            raise mailer.MailNotConfigured()
        monkeypatch.setattr(student_routes, "send_email", boom)
        r = client.post("/api/users/me/student/email", json={"email": "asha@iitb.ac.in"}, headers=auth(self.student))
        assert r.status_code == 503 and "Upload a document" in r.json()["detail"]
        assert self.status()["pending"] is None

    def test_requires_login(self):
        assert client.post("/api/users/me/student/email", json={"email": "a@iitb.ac.in"}).status_code == 401


class TestProofUpload(Setup):
    def upload(self, token=None, content=PNG, name="id.png", doc="id_card", college=None):
        return client.post(
            "/api/users/me/student/proof",
            data={"college_id": str(college or self.college_id), "document_type": doc},
            files={"file": (name, io.BytesIO(content), "application/octet-stream")},
            headers=auth(token or self.student),
        )

    def test_upload_review_and_approve_deletes_the_file(self):
        r = self.upload()
        assert r.status_code == 200 and r.json()["pending"]["method"] == "proof" and r.json()["verified"] is False
        rows = client.get("/api/admin/student-verifications", headers=auth(self.admin)).json()
        assert len(rows) == 1 and rows[0]["user_email"] == "asha@gmail.com" and rows[0]["has_file"] is True
        f = client.get(f"/api/admin/student-verifications/{rows[0]['id']}/file", headers=auth(self.admin))
        assert f.status_code == 200 and f.content == PNG and f.headers["content-type"] == "image/png"
        assert f.headers["cache-control"] == "no-store"
        r = client.post(f"/api/admin/student-verifications/{rows[0]['id']}/approve", headers=auth(self.admin))
        assert r.status_code == 200 and r.json()["has_file"] is False
        assert self.status()["verified"] is True
        assert client.get(f"/api/admin/student-verifications/{rows[0]['id']}/file", headers=auth(self.admin)).status_code == 404

    def test_reject_with_reason_and_try_again(self):
        self.upload()
        vid = client.get("/api/admin/student-verifications", headers=auth(self.admin)).json()[0]["id"]
        assert client.post(f"/api/admin/student-verifications/{vid}/reject", json={"reason": ""}, headers=auth(self.admin)).status_code == 422
        r = client.post(f"/api/admin/student-verifications/{vid}/reject", json={"reason": "The photo is blurry"}, headers=auth(self.admin))
        assert r.status_code == 200
        s = self.status()
        assert s["verified"] is False and s["last_rejection"] == "The photo is blurry" and s["pending"] is None
        assert self.upload().status_code == 200
        assert self.status()["last_rejection"] is None

    def test_only_admins_review_and_decisions_are_final(self):
        self.upload()
        vid = client.get("/api/admin/student-verifications", headers=auth(self.admin)).json()[0]["id"]
        assert client.get("/api/admin/student-verifications", headers=auth(self.student)).status_code == 403
        assert client.get(f"/api/admin/student-verifications/{vid}/file", headers=auth(self.student)).status_code == 403
        assert client.post(f"/api/admin/student-verifications/{vid}/approve", headers=auth(self.student)).status_code == 403
        client.post(f"/api/admin/student-verifications/{vid}/approve", headers=auth(self.admin))
        assert client.post(f"/api/admin/student-verifications/{vid}/reject", json={"reason": "late"}, headers=auth(self.admin)).status_code == 400

    @pytest.mark.parametrize("content,name,expected", [
        (b"hello this is not an image" * 20, "x.png", "JPEG or PNG"),
        (b"MZ" + b"0" * 400, "x.pdf", "JPEG or PNG"),
        (b"x", "x.png", "empty"),
    ])
    def test_bad_files_are_refused(self, content, name, expected):
        r = self.upload(content=content, name=name)
        assert r.status_code == 400 and expected in r.json()["detail"]

    def test_too_large(self):
        r = self.upload(content=b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024 + 10))
        assert r.status_code == 400 and "too large" in r.json()["detail"]

    def test_pdf_is_accepted(self):
        assert self.upload(content=b"%PDF-1.4" + b"0" * 300, name="receipt.pdf", doc="fee_receipt").status_code == 200

    def test_one_pending_document_at_a_time_and_validation(self):
        assert self.upload().status_code == 200
        assert self.upload().status_code == 400
        assert self.upload(token=self.other, doc="selfie").status_code == 400
        assert self.upload(token=self.other, college=9999).status_code == 400

    def test_filename_cannot_escape(self):
        self.upload(name="../../etc/passwd.png")
        row = client.get("/api/admin/student-verifications", headers=auth(self.admin)).json()[0]
        assert row["document_name"] == "passwd.png"


class TestStudentOnlyAndPricing(Setup):
    def setup_method(self):
        super().setup_method()
        self.owner = user_token("Owner", "owner@test.com", "organizer")
        self.fest = create_fest(self.owner, self.college_id)
        self.slug = self.fest["slug"]
        get_entry_pass(self.student, self.slug)
        get_entry_pass(self.other, self.slug)

    def make_event(self, **kw):
        payload = {"event_type": "fest", "title": kw.pop("title", "Hack"), "date": "2026-12-01T10:00:00", "fest_id": self.fest["id"], "requires_registration": True}
        payload.update(kw)
        r = client.post("/api/events/", json=payload, headers=auth(self.owner))
        assert r.status_code == 200, r.text
        return r.json()

    def verify(self, token, email, mails):
        client.post("/api/users/me/student/email", json={"email": email}, headers=auth(token))
        code = code_from(mails)
        assert client.post("/api/users/me/student/email/confirm", json={"code": code}, headers=auth(token)).status_code == 200

    def test_students_only_event_blocks_unverified(self, mails):
        e = self.make_event(students_only=True)
        assert e["students_only"] is True
        r = client.post(f"/api/fest-events/{e['id']}/register", headers=auth(self.student))
        assert r.status_code == 403 and "verified students" in r.json()["detail"]
        self.verify(self.student, "asha@iitb.ac.in", mails)
        assert client.post(f"/api/fest-events/{e['id']}/register", headers=auth(self.student)).status_code == 201
        assert client.post(f"/api/fest-events/{e['id']}/register", headers=auth(self.other)).status_code == 403

    def test_open_events_stay_open(self):
        e = self.make_event()
        assert client.post(f"/api/fest-events/{e['id']}/register", headers=auth(self.other)).status_code == 201

    def test_student_price_applies_only_to_verified_students(self, mails):
        e = self.make_event(is_free=False, is_paid=True, price=200, student_price=120)
        self.verify(self.student, "asha@iitb.ac.in", mails)
        mine = client.post(f"/api/fest-events/{e['id']}/register", headers=auth(self.student)).json()
        other = client.post(f"/api/fest-events/{e['id']}/register", headers=auth(self.other)).json()
        assert mine["amount_due"] == 120 and other["amount_due"] == 200
        csv_text = client.get(f"/api/fest-events/{e['id']}/registrations.csv", headers=auth(self.owner)).text
        assert "Amount due (INR)" in csv_text and ",120," in csv_text and ",200," in csv_text

    def test_free_events_owe_nothing(self):
        e = self.make_event()
        assert client.post(f"/api/fest-events/{e['id']}/register", headers=auth(self.student)).json()["amount_due"] == 0

    def test_student_price_must_be_lower(self):
        r = client.post("/api/events/", json={"event_type": "fest", "title": "X", "date": "2026-12-01T10:00:00", "fest_id": self.fest["id"], "is_free": False, "price": 100, "student_price": 100}, headers=auth(self.owner))
        assert r.status_code == 422

    def test_free_event_ignores_student_price(self):
        e = self.make_event(student_price=50)
        assert e["student_price"] is None

    def test_locked_once_people_registered(self):
        e = self.make_event(is_free=False, is_paid=True, price=200, student_price=100)
        client.post(f"/api/fest-events/{e['id']}/register", headers=auth(self.other))
        r = client.patch(f"/api/events/{e['id']}", json={"students_only": True}, headers=auth(self.owner))
        assert r.status_code == 400 and "students_only" in r.json()["detail"]
        r = client.patch(f"/api/events/{e['id']}", json={"student_price": 50}, headers=auth(self.owner))
        assert r.status_code == 400

    def test_edit_before_registrations(self):
        e = self.make_event(is_free=False, is_paid=True, price=200)
        r = client.patch(f"/api/events/{e['id']}", json={"students_only": True, "student_price": 150}, headers=auth(self.owner))
        assert r.status_code == 200 and r.json()["students_only"] is True and r.json()["student_price"] == 150
        assert client.patch(f"/api/events/{e['id']}", json={"student_price": 250}, headers=auth(self.owner)).status_code == 400
