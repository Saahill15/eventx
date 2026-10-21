"""Organiser tools: college partnership, fest listing and review, event details, uploads, custom questions, announcements."""

import io

import pytest

from test_fixes import user_token, user_id  # noqa: F401
from test_full import client, auth, create_college, create_fest_event, get_entry_pass, reset_db, TestingSessionLocal, make_organizer  # noqa: F401
from app import mailer, models
from app.routes import announcements as ann_routes

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 300

FEST_DETAILS = {
    "description": "Three days of music, tech and sport.",
    "start_date": "2026-12-04", "end_date": "2026-12-06",
    "campus_address": "IIT Bombay, Powai, Mumbai", "map_url": "https://maps.example.com/iitb",
    "banner_url": "https://img.example.com/banner.jpg",
    "contact_name": "Ravi Kumar", "contact_email": "ravi@college.example.com", "contact_phone": "+91 98765 43210",
}


def event_payload(fest_id, **kw):
    p = {"event_type": "fest", "title": "Battle of Bands", "date": "2026-12-05T18:00:00", "fest_id": fest_id,
         "location": "Main Stage", "time": "18:00", "end_time": "20:00", "description": "Live bands compete."}
    p.update(kw)
    return p


@pytest.fixture
def mails(monkeypatch):
    sent = []
    monkeypatch.setattr(ann_routes, "send_email", lambda to, subject, text: sent.append((to, subject, text)))
    monkeypatch.setattr(ann_routes, "SessionLocal", TestingSessionLocal)
    return sent


class Setup:
    def setup_method(self):
        self.admin = user_token("Admin", "admin@test.com", "admin")
        self.college_id = create_college(self.admin)
        self.owner = user_token("Owner", "owner@test.com")
        assert client.post(f"/api/admin/users/{user_id('owner@test.com')}/role", json={"role": "organizer", "college_ids": [self.college_id]}, headers=auth(self.admin)).status_code == 200
        self.student = user_token("Student", "student@test.com")

    def start(self, slug="fest-one", **extra):
        r = client.post("/api/fests/", json={"slug": slug, "name": "Fest One", "college_id": self.college_id, **extra}, headers=auth(self.owner))
        assert r.status_code == 201, r.text
        return r.json()

    def fill(self, slug="fest-one", **overrides):
        r = client.patch(f"/api/fests/{slug}", json={"tagline": "Music, tech and sport", **FEST_DETAILS, **overrides}, headers=auth(self.owner))
        assert r.status_code == 200, r.text
        return r.json()

    def add_event(self, fest_id, **kw):
        r = client.post("/api/events/", json=event_payload(fest_id, **kw), headers=auth(self.owner))
        assert r.status_code == 200, r.text
        return r.json()

    def submit(self, slug="fest-one"):
        return client.post(f"/api/fests/{slug}/submit", headers=auth(self.owner))

    def ready_and_approved(self, slug="fest-one"):
        fest = self.start(slug)
        self.fill(slug)
        self.add_event(fest["id"])
        assert self.submit(slug).status_code == 200
        assert client.post(f"/api/admin/fests/{slug}/approve", headers=auth(self.admin)).status_code == 200
        return fest


class TestPartnership(Setup):
    def test_only_partner_colleges_can_have_fests(self):
        r = client.post("/api/colleges/", json={"name": "Prospect College"}, headers=auth(self.admin))
        assert r.json()["partner_status"] == "prospect"
        pid = r.json()["id"]
        # an organiser cannot be assigned to a college that is not a partner yet
        r = client.post(f"/api/admin/users/{user_id('owner@test.com')}/colleges", json={}, headers=auth(self.admin))
        r = client.put(f"/api/admin/users/{user_id('owner@test.com')}/colleges", json={"college_ids": [pid]}, headers=auth(self.admin))
        assert r.status_code == 400 and "Not a partner" in r.json()["detail"]
        # and an admin can still start a fest for it, an assigned organiser cannot reach it at all
        r = client.post("/api/fests/", json={"slug": "nope", "name": "Nope", "college_id": pid}, headers=auth(self.owner))
        assert r.status_code == 403

    def test_organiser_needs_a_college_when_promoted(self):
        uid = user_id("student@test.com")
        assert client.post(f"/api/admin/users/{uid}/role", json={"role": "organizer"}, headers=auth(self.admin)).status_code == 400
        assert client.post(f"/api/admin/users/{uid}/role", json={"role": "organizer", "college_ids": [9999]}, headers=auth(self.admin)).status_code == 400

    def test_organiser_can_only_use_assigned_colleges(self):
        other = client.post("/api/colleges/", json={"name": "Other College", "partner_status": "partner"}, headers=auth(self.admin)).json()["id"]
        r = client.post("/api/fests/", json={"slug": "x-fest", "name": "X", "college_id": other}, headers=auth(self.owner))
        assert r.status_code == 403 and "your own college" in r.json()["detail"]
        client.put(f"/api/admin/users/{user_id('owner@test.com')}/colleges", json={"college_ids": [self.college_id, other]}, headers=auth(self.admin))
        assert client.post("/api/fests/", json={"slug": "x-fest", "name": "X", "college_id": other}, headers=auth(self.owner)).status_code == 201

    def test_members_cannot_start_fests(self):
        r = client.post("/api/fests/", json={"slug": "mine-x", "name": "X", "college_id": self.college_id}, headers=auth(self.student))
        assert r.status_code == 403 and "switched on" in r.json()["detail"]

    def test_partnership_details_are_admin_only(self):
        r = client.put(f"/api/colleges/{self.college_id}", json={"name": "IIT Bombay", "partner_status": "partner", "coordinator_name": "Dr Rao", "coordinator_phone": "+91 99999 11111", "coordinator_email": "rao@iitb.example.com", "partner_since": "2026-10-01", "partner_notes": "Met in person"}, headers=auth(self.admin))
        assert r.status_code == 200
        admin_list = client.get("/api/admin/colleges", headers=auth(self.admin)).json()
        assert admin_list[0]["coordinator_name"] == "Dr Rao" and admin_list[0]["partner_notes"] == "Met in person"
        public = client.get("/api/colleges/").json()[0]
        assert "coordinator_name" not in public and "coordinator_phone" not in public
        assert client.get("/api/admin/colleges", headers=auth(self.owner)).status_code == 403

    def test_demoting_clears_college_assignments(self):
        uid = user_id("owner@test.com")
        other = user_token("Org2", "org2@test.com")
        client.post(f"/api/admin/users/{user_id('org2@test.com')}/role", json={"role": "organizer", "college_ids": [self.college_id]}, headers=auth(self.admin))
        r = client.post(f"/api/admin/users/{user_id('org2@test.com')}/role", json={"role": "user"}, headers=auth(self.admin))
        assert r.json()["college_ids"] == []


class TestFestListingAndReview(Setup):
    def test_starting_a_fest_needs_only_the_basics(self):
        fest = self.start()
        assert fest["status"] == "draft" and fest["review_status"] == "draft"
        mine = client.get("/api/fests/mine", headers=auth(self.owner)).json()
        assert mine[0]["my_role"] == "owner" and mine[0]["review_status"] == "draft"

    def test_submit_lists_everything_missing(self):
        self.start()
        r = self.submit()
        assert r.status_code == 400
        missing = r.json()["detail"]["missing"]
        for expected in ("description", "start date", "campus address", "map link", "banner image", "committee contact phone", "at least one event"):
            assert expected in missing

    def test_submit_checks_event_details_and_dates(self):
        fest = self.start()
        self.fill()
        e = self.add_event(fest["id"], date="2026-12-20T18:00:00")
        missing = self.submit().json()["detail"]["missing"]
        assert any("outside the fest" in m for m in missing)
        client.patch(f"/api/events/{e['id']}", json={"date": "2026-12-05T18:00:00"}, headers=auth(self.owner))
        assert self.submit().status_code == 200

    def test_full_review_flow(self):
        fest = self.start()
        self.fill()
        self.add_event(fest["id"])
        # cannot go live yet
        assert client.patch("/api/fests/fest-one/status", json={"status": "live"}, headers=auth(self.owner)).status_code == 400
        r = self.submit()
        assert r.status_code == 200 and r.json()["fest"]["review_status"] == "in_review"

        queue = client.get("/api/admin/fests", headers=auth(self.admin)).json()
        assert len(queue) == 1
        item = queue[0]
        assert item["fest"]["slug"] == "fest-one" and item["fest"]["contact_phone"]
        assert item["college"]["name"] == "IIT Bombay" and item["college"]["partner_status"] == "partner"
        assert item["missing"] == [] and len(item["events"]) == 1
        assert item["owners"] == ["Owner <owner@test.com>"]

        r = client.post("/api/admin/fests/fest-one/request-changes", json={"note": "Please add a clearer banner"}, headers=auth(self.admin))
        assert r.status_code == 200
        mine = client.get("/api/fests/mine", headers=auth(self.owner)).json()[0]
        assert mine["review_status"] == "changes_requested" and mine["review_note"] == "Please add a clearer banner"

        # fix and resubmit, then approve
        self.fill(banner_url="https://img.example.com/better.jpg")
        assert self.submit().status_code == 200
        assert client.post("/api/admin/fests/fest-one/approve", json={"note": "Looks good"}, headers=auth(self.admin)).status_code == 200
        r = client.patch("/api/fests/fest-one/status", json={"status": "live"}, headers=auth(self.owner))
        assert r.status_code == 200 and r.json()["status"] == "live"
        assert client.get("/api/fests/fest-one").json()["status"] == "live"

    def test_rejection_can_be_fixed_and_resubmitted(self):
        self.ready_and_approved("a-fest")  # a different fest in the system
        fest = self.start("fest-two")
        self.fill("fest-two"); self.add_event(fest["id"])
        self.submit("fest-two")
        r = client.post("/api/admin/fests/fest-two/reject", json={"note": "Not a real committee"}, headers=auth(self.admin))
        assert r.status_code == 200
        assert client.get("/api/fests/mine", headers=auth(self.owner)).json()[0]["review_status"] in ("rejected", "approved")
        assert self.submit("fest-two").status_code == 200

    def test_decisions_need_a_note_and_only_for_fests_in_review(self):
        self.start()
        assert client.post("/api/admin/fests/fest-one/approve", headers=auth(self.admin)).status_code == 400
        fest = self.start("fest-b"); self.fill("fest-b"); self.add_event(fest["id"]); self.submit("fest-b")
        assert client.post("/api/admin/fests/fest-b/request-changes", json={"note": "no"}, headers=auth(self.admin)).status_code == 422
        assert client.post("/api/admin/fests/fest-b/reject", json={}, headers=auth(self.admin)).status_code == 422

    def test_organisers_cannot_review(self):
        self.start()
        assert client.get("/api/admin/fests", headers=auth(self.owner)).status_code == 403
        assert client.post("/api/admin/fests/fest-one/approve", headers=auth(self.owner)).status_code == 403

    def test_frozen_while_in_review_and_withdraw(self):
        fest = self.start(); self.fill(); self.add_event(fest["id"]); self.submit()
        assert client.patch("/api/fests/fest-one", json={"tagline": "New"}, headers=auth(self.owner)).status_code == 400
        assert client.post("/api/events/", json=event_payload(fest["id"], title="Another"), headers=auth(self.owner)).status_code == 400
        assert self.submit().status_code == 400
        assert client.post("/api/fests/fest-one/withdraw", headers=auth(self.owner)).status_code == 200
        assert client.patch("/api/fests/fest-one", json={"tagline": "New"}, headers=auth(self.owner)).status_code == 200

    def test_after_approval_dates_are_free_but_name_and_college_need_review(self):
        self.ready_and_approved()
        client.patch("/api/fests/fest-one/status", json={"status": "live"}, headers=auth(self.owner))
        r = client.patch("/api/fests/fest-one", json={"end_date": "2026-12-08", "description": "Updated"}, headers=auth(self.owner))
        assert r.status_code == 200 and r.json()["review_status"] == "approved" and r.json()["status"] == "live"
        r = client.patch("/api/fests/fest-one", json={"name": "A Brand New Name"}, headers=auth(self.owner))
        assert r.status_code == 200 and r.json()["review_status"] == "in_review" and r.json()["status"] == "draft"
        assert "name" in r.json()["review_note"]
        assert client.get("/api/fests/fest-one").status_code == 404  # offline until approved again

    def test_same_name_does_not_trigger_review(self):
        self.ready_and_approved()
        r = client.patch("/api/fests/fest-one", json={"name": "Fest One"}, headers=auth(self.owner))
        assert r.json()["review_status"] == "approved"

    def test_public_fest_hides_private_contacts(self):
        self.ready_and_approved()
        client.patch("/api/fests/fest-one/status", json={"status": "live"}, headers=auth(self.owner))
        public = client.get("/api/fests/fest-one").json()
        assert public["description"] and public["campus_address"] and public["map_url"]
        for private in ("contact_phone", "contact_email", "faculty_phone", "review_status", "review_note"):
            assert private not in public
        manage = client.get("/api/fests/fest-one/manage", headers=auth(self.owner)).json()
        assert manage["contact_phone"] == "+91 98765 43210"
        assert client.get("/api/fests/fest-one/manage", headers=auth(self.student)).status_code == 403

    def test_validation(self):
        self.start()
        assert client.patch("/api/fests/fest-one", json={"start_date": "2026-12-06", "end_date": "2026-12-01"}, headers=auth(self.owner)).status_code in (400, 422)
        assert client.patch("/api/fests/fest-one", json={"map_url": "javascript:alert(1)"}, headers=auth(self.owner)).status_code == 422
        assert client.patch("/api/fests/fest-one", json={"contact_phone": "abc"}, headers=auth(self.owner)).status_code == 422
        assert client.patch("/api/fests/fest-one", json={"contact_email": "not-an-email"}, headers=auth(self.owner)).status_code == 422

    def test_extra_sections(self):
        self.start()
        r = client.patch("/api/fests/fest-one", json={"extra_sections": [{"title": "Rules", "body": "Carry your ID"}, {"title": "Prizes", "body": "Trophies"}]}, headers=auth(self.owner))
        assert r.status_code == 200 and r.json()["extra_sections"][1]["title"] == "Prizes"
        too_many = [{"title": f"S{i}", "body": "x"} for i in range(11)]
        assert client.patch("/api/fests/fest-one", json={"extra_sections": too_many}, headers=auth(self.owner)).status_code == 422
        assert client.patch("/api/fests/fest-one", json={"extra_sections": [{"title": "", "body": "x"}]}, headers=auth(self.owner)).status_code == 422


class TestEventDetails(Setup):
    def setup_method(self):
        super().setup_method()
        self.fest = self.start()

    def test_fest_events_need_venue_times_and_description(self):
        for missing in ("location", "time", "end_time", "description"):
            payload = event_payload(self.fest["id"])
            payload.pop(missing)
            r = client.post("/api/events/", json=payload, headers=auth(self.owner))
            assert r.status_code == 422, missing

    def test_end_time_must_follow_start(self):
        r = client.post("/api/events/", json=event_payload(self.fest["id"], end_time="17:00"), headers=auth(self.owner))
        assert r.status_code == 422
        assert client.post("/api/events/", json=event_payload(self.fest["id"], time="9am"), headers=auth(self.owner)).status_code == 422

    def test_cannot_blank_required_details_on_edit(self):
        e = self.add_event(self.fest["id"])
        assert client.patch(f"/api/events/{e['id']}", json={"location": ""}, headers=auth(self.owner)).status_code == 400
        assert client.patch(f"/api/events/{e['id']}", json={"end_time": "17:00"}, headers=auth(self.owner)).status_code == 400
        assert client.patch(f"/api/events/{e['id']}", json={"location": "New Stage", "end_time": "21:00"}, headers=auth(self.owner)).status_code == 200

    def test_extra_sections_on_events(self):
        e = self.add_event(self.fest["id"], extra_sections=[{"title": "Rules", "body": "No outside instruments"}])
        assert e["extra_sections"][0]["title"] == "Rules"
        r = client.patch(f"/api/events/{e['id']}", json={"extra_sections": [{"title": "Prizes", "body": "₹10,000"}]}, headers=auth(self.owner))
        assert r.json()["extra_sections"][0]["title"] == "Prizes"

    def test_remove_event_only_when_nobody_registered(self):
        e = self.add_event(self.fest["id"], requires_registration=True)
        client.patch(f"/api/fests/{self.fest['slug']}/status", json={"status": "draft"}, headers=auth(self.owner))
        assert client.delete(f"/api/events/{e['id']}", headers=auth(self.owner)).status_code == 204
        assert client.get(f"/api/events/{e['id']}", headers=auth(self.owner)).status_code == 404

    def test_removing_an_event_with_registrations_asks_to_cancel(self):
        fest = self.ready_and_approved("fest-live")
        client.patch("/api/fests/fest-live/status", json={"status": "live"}, headers=auth(self.owner))
        e = self.add_event(fest["id"], requires_registration=True, title="Hack")
        get_entry_pass(self.student, "fest-live")
        assert client.post(f"/api/fest-events/{e['id']}/register", headers=auth(self.student)).status_code == 201
        r = client.delete(f"/api/events/{e['id']}", headers=auth(self.owner))
        assert r.status_code == 409 and "Cancel it instead" in r.json()["detail"]

    def test_students_cannot_delete(self):
        e = self.add_event(self.fest["id"])
        assert client.delete(f"/api/events/{e['id']}", headers=auth(self.student)).status_code == 403

    def test_cancelling_tells_the_people_registered(self, mails):
        fest = self.ready_and_approved("fest-live")
        client.patch("/api/fests/fest-live/status", json={"status": "live"}, headers=auth(self.owner))
        e = self.add_event(fest["id"], requires_registration=True, title="Hack")
        get_entry_pass(self.student, "fest-live")
        other = user_token("Other", "other@test.com")
        get_entry_pass(other, "fest-live")
        client.post(f"/api/fest-events/{e['id']}/register", headers=auth(self.student))
        r = client.post(f"/api/events/{e['id']}/cancel", json={"reason": "Heavy rain"}, headers=auth(self.owner))
        assert r.status_code == 200
        assert [m[0] for m in mails] == ["student@test.com"]
        assert "Cancelled: Hack" in mails[0][1] and "Heavy rain" in mails[0][2]
        notes = client.get("/api/users/me/notifications", headers=auth(self.student)).json()
        assert notes[0]["title"] == "Cancelled: Hack"
        assert client.get("/api/users/me/notifications", headers=auth(other)).json() == []


class TestMedia(Setup):
    def upload(self, token, content=PNG, name="a.png"):
        return client.post("/api/media", files={"file": (name, io.BytesIO(content), "application/octet-stream")}, headers=auth(token))

    def test_upload_and_public_download(self):
        r = self.upload(self.owner)
        assert r.status_code == 201 and r.json()["url"].startswith("/api/media/")
        got = client.get(r.json()["url"])
        assert got.status_code == 200 and got.content == PNG and got.headers["content-type"] == "image/png"
        assert "immutable" in got.headers["cache-control"] and got.headers["x-content-type-options"] == "nosniff"

    def test_uploaded_image_can_be_a_banner(self):
        url = self.upload(self.owner).json()["url"]
        self.start()
        r = client.patch("/api/fests/fest-one", json={"banner_url": url}, headers=auth(self.owner))
        assert r.status_code == 200 and r.json()["banner_url"] == url

    def test_members_cannot_upload(self):
        assert self.upload(self.student).status_code == 403
        assert client.post("/api/media", files={"file": ("a.png", io.BytesIO(PNG))}).status_code == 401

    @pytest.mark.parametrize("content", [b"not an image at all" * 30, b"%PDF-1.4" + b"0" * 300, b"GIF89a" + b"0" * 300])
    def test_only_images(self, content):
        assert self.upload(self.owner, content=content).status_code == 400

    def test_size_limit_and_webp(self):
        assert self.upload(self.owner, content=b"\x89PNG\r\n\x1a\n" + b"0" * (3 * 1024 * 1024 + 10)).status_code == 400
        assert self.upload(self.owner, content=b"RIFF\x00\x00\x00\x00WEBP" + b"0" * 300).status_code == 201

    def test_unknown_media_and_bad_links(self):
        assert client.get("/api/media/" + "0" * 32).status_code == 404
        self.start()
        assert client.patch("/api/fests/fest-one", json={"banner_url": "/etc/passwd"}, headers=auth(self.owner)).status_code == 422
        assert client.patch("/api/fests/fest-one", json={"banner_url": "ftp://x.test/a.png"}, headers=auth(self.owner)).status_code == 422


class TestCustomQuestions(Setup):
    def setup_method(self):
        super().setup_method()
        self.fest = self.ready_and_approved()
        client.patch("/api/fests/fest-one/status", json={"status": "live"}, headers=auth(self.owner))
        self.event = self.add_event(self.fest["id"], title="Hack", requires_registration=True)
        get_entry_pass(self.student, "fest-one")

    def put(self, questions, token=None):
        return client.put(f"/api/events/{self.event['id']}/questions", json={"questions": questions}, headers=auth(token or self.owner))

    QUESTIONS = [
        {"label": "Team name", "kind": "short_text", "required": True},
        {"label": "T-shirt size", "kind": "choice", "required": True, "options": ["S", "M", "L"]},
        {"label": "Need accommodation?", "kind": "yes_no", "required": False},
    ]

    def test_set_and_read_questions(self):
        r = self.put(self.QUESTIONS)
        assert r.status_code == 200 and [q["label"] for q in r.json()] == ["Team name", "T-shirt size", "Need accommodation?"]
        public = client.get(f"/api/events/{self.event['id']}/questions").json()
        assert public[1]["options"] == ["S", "M", "L"]

    def test_validation_of_question_definitions(self):
        assert self.put([{"label": "Size", "kind": "choice", "options": ["S"]}]).status_code == 422
        assert self.put([{"label": "Size", "kind": "choice", "options": ["S", "s"]}]).status_code == 422
        assert self.put([{"label": "", "kind": "short_text"}]).status_code == 422
        assert self.put([{"label": "x", "kind": "long_text"}]).status_code == 422
        assert self.put([{"label": f"q{i}", "kind": "short_text"} for i in range(11)]).status_code == 422

    def test_only_fest_staff_can_edit(self):
        assert self.put(self.QUESTIONS, token=self.student).status_code == 403

    def answer(self, *pairs, token=None):
        return client.post(f"/api/fest-events/{self.event['id']}/register", json={"answers": [{"question_id": q, "value": v} for q, v in pairs]}, headers=auth(token or self.student))

    def test_registration_checks_answers(self):
        qs = self.put(self.QUESTIONS).json()
        team, size, stay = qs[0]["id"], qs[1]["id"], qs[2]["id"]
        assert client.post(f"/api/fest-events/{self.event['id']}/register", headers=auth(self.student)).status_code == 400  # no answers at all
        assert "Team name" in self.answer((size, "M")).json()["detail"]
        assert self.answer((team, "Rockets"), (size, "XXL")).status_code == 400
        assert self.answer((team, "Rockets"), (size, "M"), (stay, "maybe")).status_code == 400
        assert self.answer((team, "Rockets"), (size, "M"), (999, "x")).status_code == 400
        r = self.answer((team, "Rockets"), (size, "M"), (stay, "YES"))
        assert r.status_code == 201, r.text

    def test_answers_reach_the_committee(self):
        qs = self.put(self.QUESTIONS).json()
        self.answer((qs[0]["id"], "Rockets"), (qs[1]["id"], "L"), (qs[2]["id"], "yes"))
        rows = client.get(f"/api/fest-events/{self.event['id']}/registrations", headers=auth(self.owner)).json()
        assert {a["label"]: a["answer"] for a in rows[0]["answers"]} == {"Team name": "Rockets", "T-shirt size": "L", "Need accommodation?": "yes"}
        csv_lines = client.get(f"/api/fest-events/{self.event['id']}/registrations.csv", headers=auth(self.owner)).text.splitlines()
        assert csv_lines[0].endswith("Team name,T-shirt size,Need accommodation?")
        assert csv_lines[1].endswith("Rockets,L,yes")

    def test_optional_questions_can_be_skipped(self):
        qs = self.put([{"label": "Anything else?", "kind": "short_text", "required": False}]).json()
        assert client.post(f"/api/fest-events/{self.event['id']}/register", headers=auth(self.student)).status_code == 201

    def test_questions_lock_once_people_registered(self):
        qs = self.put([{"label": "Team name", "kind": "short_text", "required": True}]).json()
        self.answer((qs[0]["id"], "Rockets"))
        keep = {"id": qs[0]["id"], "label": "Team name", "kind": "short_text", "required": True}
        assert self.put([]).status_code == 400
        assert self.put([{**keep, "label": "Squad name"}]).status_code == 400
        assert self.put([keep, {"label": "New required", "kind": "short_text", "required": True}]).status_code == 400
        assert self.put([keep, {"label": "New optional", "kind": "short_text", "required": False}]).status_code == 200

    def test_csv_neutralises_formulas_in_answers(self):
        qs = self.put([{"label": "Team", "kind": "short_text", "required": True}]).json()
        self.answer((qs[0]["id"], "=HYPERLINK(\"http://x\")"))
        text = client.get(f"/api/fest-events/{self.event['id']}/registrations.csv", headers=auth(self.owner)).text
        assert "'=HYPERLINK" in text and "\n=HYPERLINK" not in text and ",=HYPERLINK" not in text

    def test_frozen_while_in_review(self):
        client.patch("/api/fests/fest-one", json={"name": "Renamed Fest"}, headers=auth(self.owner))  # sends it back to review
        assert self.put(self.QUESTIONS).status_code == 400


class TestAnnouncements(Setup):
    def setup_method(self):
        super().setup_method()
        self.fest = self.ready_and_approved()
        client.patch("/api/fests/fest-one/status", json={"status": "live"}, headers=auth(self.owner))
        self.event = self.add_event(self.fest["id"], title="Hack", requires_registration=True)
        self.other = user_token("Other", "other@test.com")
        self.stranger = user_token("Stranger", "stranger@test.com")
        get_entry_pass(self.student, "fest-one")
        get_entry_pass(self.other, "fest-one")
        client.post(f"/api/fest-events/{self.event['id']}/register", headers=auth(self.student))

    def post(self, token=None, **kw):
        body = {"title": "Gate change", "body": "Use gate 3 today.", **kw}
        return client.post("/api/fests/fest-one/announcements", json=body, headers=auth(token or self.owner))

    def test_fest_wide_email_goes_to_every_pass_holder(self, mails):
        r = self.post(send_email=True)
        assert r.status_code == 201 and r.json()["email_requested"] is True
        assert sorted(m[0] for m in mails) == ["other@test.com", "student@test.com"]
        assert mails[0][1] == "[Fest One] Gate change" and "Use gate 3 today." in mails[0][2]
        assert client.get("/api/fests/fest-one/announcements").json()[0]["emails_sent"] == 2

    def test_event_announcement_goes_only_to_registrants(self, mails):
        self.post(event_id=self.event["id"], send_email=True)
        assert [m[0] for m in mails] == ["student@test.com"]

    def test_no_email_unless_asked(self, mails):
        self.post()
        assert mails == []

    def test_in_app_lists_and_notifications(self, mails):
        self.post(title="For everyone")
        self.post(title="For Hack only", event_id=self.event["id"])
        public = client.get("/api/fests/fest-one/announcements").json()
        assert {a["title"] for a in public} == {"For everyone", "For Hack only"}
        mine = [a["title"] for a in client.get("/api/users/me/notifications", headers=auth(self.student)).json()]
        assert set(mine) == {"For everyone", "For Hack only"}
        others = [a["title"] for a in client.get("/api/users/me/notifications", headers=auth(self.other)).json()]
        assert others == ["For everyone"]
        assert client.get("/api/users/me/notifications", headers=auth(self.stranger)).json() == []
        filtered = client.get("/api/fests/fest-one/announcements", params={"event_id": self.event["id"]}).json()
        assert len(filtered) == 2

    def test_only_staff_can_post_and_delete(self, mails):
        assert self.post(token=self.student).status_code == 403
        aid = self.post().json()["id"]
        assert client.delete(f"/api/fests/fest-one/announcements/{aid}", headers=auth(self.student)).status_code == 403
        assert client.delete(f"/api/fests/fest-one/announcements/{aid}", headers=auth(self.owner)).status_code == 204
        assert client.get("/api/fests/fest-one/announcements").json() == []

    def test_needs_a_live_fest_and_a_real_event(self, mails):
        assert self.post(event_id=9999).status_code == 400
        client.patch("/api/fests/fest-one/status", json={"status": "draft"}, headers=auth(self.owner))
        assert self.post().status_code == 400

    def test_daily_limit(self, mails):
        codes = [self.post(title=f"n{i}").status_code for i in range(11)]
        assert codes[:10] == [201] * 10 and codes[10] == 429

    def test_email_failures_are_counted_not_fatal(self, monkeypatch):
        def boom(to, subject, text):
            raise mailer.MailFailed()
        monkeypatch.setattr(ann_routes, "send_email", boom)
        monkeypatch.setattr(ann_routes, "SessionLocal", TestingSessionLocal)
        r = self.post(send_email=True)
        assert r.status_code == 201
        row = client.get("/api/fests/fest-one/announcements").json()[0]
        assert row["emails_failed"] == 2 and row["emails_sent"] == 0

    def test_validation(self, mails):
        assert self.post(title="").status_code == 422
        assert self.post(body="x" * 2001).status_code == 422
