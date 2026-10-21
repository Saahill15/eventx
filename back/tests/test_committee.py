"""Committee dashboard endpoints: my fests, event management, registrations, CSV, team invites."""

import pytest

from test_fixes import user_token, user_id, city_event_payload  # noqa: F401
from test_full import (
    client, auth, create_college, create_fest, create_fest_event, get_entry_pass, reset_db,  # noqa: F401
)


class Setup:
    def setup_method(self):
        self.admin = user_token("Admin", "admin@test.com", "admin")
        self.owner = user_token("Owner", "owner@test.com", "organizer")
        self.core = user_token("Core", "core@test.com")
        self.student = user_token("Student", "student@test.com")
        self.stranger = user_token("Stranger", "stranger@test.com", "organizer")
        self.college_id = create_college(self.admin)
        self.fest = create_fest(self.owner, self.college_id)
        self.slug = self.fest["slug"]
        r = client.post(f"/api/fests/{self.slug}/members", json={"email": "core@test.com", "role": "core"}, headers=auth(self.owner))
        assert r.status_code == 201, r.text


class TestMyFests(Setup):
    def test_lists_fests_with_my_role(self):
        assert client.get("/api/fests/mine", headers=auth(self.owner)).json()[0]["my_role"] == "owner"
        assert client.get("/api/fests/mine", headers=auth(self.core)).json()[0]["my_role"] == "core"

    def test_non_members_see_nothing_and_admin_sees_all(self):
        assert client.get("/api/fests/mine", headers=auth(self.student)).json() == []
        assert client.get("/api/fests/mine", headers=auth(self.admin)).json()[0]["my_role"] == "admin"

    def test_requires_login(self):
        assert client.get("/api/fests/mine").status_code == 401


class TestEventManagement(Setup):
    def test_fest_events_are_published_without_admin_review(self):
        event = create_fest_event(self.owner, self.fest["id"], self.college_id, title="Hackathon")
        assert event["status"] == "approved"
        assert any(e["id"] == event["id"] for e in client.get(f"/api/fests/{self.slug}/events").json())

    def test_manage_list_has_counts_and_is_staff_only(self):
        event = create_fest_event(self.owner, self.fest["id"], self.college_id, requires_registration=True, approval_mode="manual")
        get_entry_pass(self.student, self.slug)
        client.post(f"/api/fest-events/{event['id']}/register", headers=auth(self.student))
        rows = client.get(f"/api/fests/{self.slug}/manage/events", headers=auth(self.core)).json()
        assert rows[0]["registration_count"] == 1 and rows[0]["pending_count"] == 1
        assert client.get(f"/api/fests/{self.slug}/manage/events", headers=auth(self.student)).status_code == 403
        assert client.get(f"/api/fests/{self.slug}/manage/events", headers=auth(self.stranger)).status_code == 403

    def test_staff_can_edit_fest_details_others_cannot(self):
        r = client.patch(f"/api/fests/{self.slug}", json={"tagline": "New tagline"}, headers=auth(self.core))
        assert r.status_code == 200 and r.json()["tagline"] == "New tagline"
        assert client.patch(f"/api/fests/{self.slug}", json={"tagline": "x"}, headers=auth(self.stranger)).status_code == 403
        assert client.patch(f"/api/fests/{self.slug}", json={"name": None}, headers=auth(self.owner)).json()["name"] == "TechFest 2026"


class TestRegistrations(Setup):
    def setup_method(self):
        super().setup_method()
        self.event = create_fest_event(self.owner, self.fest["id"], self.college_id, requires_registration=True, approval_mode="manual")
        get_entry_pass(self.student, self.slug)
        self.reg = client.post(f"/api/fest-events/{self.event['id']}/register", headers=auth(self.student)).json()

    def test_list_shows_who_registered(self):
        rows = client.get(f"/api/fest-events/{self.event['id']}/registrations", headers=auth(self.owner)).json()
        assert rows[0]["user_name"] == "Student" and rows[0]["user_email"] == "student@test.com"
        assert rows[0]["approval_status"] == "pending"

    def test_students_cannot_see_the_list_or_decide(self):
        assert client.get(f"/api/fest-events/{self.event['id']}/registrations", headers=auth(self.student)).status_code == 403
        assert client.post(f"/api/fest-events/registrations/{self.reg['id']}/approve", headers=auth(self.student)).status_code == 403
        assert client.post(f"/api/fest-events/registrations/{self.reg['id']}/approve", headers=auth(self.stranger)).status_code == 403

    def test_core_member_can_approve_once(self):
        r = client.post(f"/api/fest-events/registrations/{self.reg['id']}/approve", headers=auth(self.core))
        assert r.status_code == 200 and r.json()["approval_status"] == "approved"
        assert client.post(f"/api/fest-events/registrations/{self.reg['id']}/reject", headers=auth(self.core)).status_code == 400

    def test_reject(self):
        r = client.post(f"/api/fest-events/registrations/{self.reg['id']}/reject", headers=auth(self.owner))
        assert r.json()["approval_status"] == "rejected"

    def test_csv_export(self):
        r = client.get(f"/api/fest-events/{self.event['id']}/registrations.csv", headers=auth(self.owner))
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        lines = r.text.strip().splitlines()
        assert lines[0].startswith("Name,Email")
        assert "student@test.com" in lines[1]
        assert client.get(f"/api/fest-events/{self.event['id']}/registrations.csv", headers=auth(self.student)).status_code == 403

    def test_csv_neutralises_formulas(self):
        evil = user_token("=HYPERLINK(\"http://x\")", "evil@test.com")
        get_entry_pass(evil, self.slug)
        client.post(f"/api/fest-events/{self.event['id']}/register", headers=auth(evil))
        r = client.get(f"/api/fest-events/{self.event['id']}/registrations.csv", headers=auth(self.owner))
        assert "'=HYPERLINK" in r.text
        assert "\n=HYPERLINK" not in r.text


class TestTeam(Setup):
    def test_members_list_shows_names_and_emails(self):
        rows = client.get(f"/api/fests/{self.slug}/members", headers=auth(self.owner)).json()
        assert {r["user_email"] for r in rows} == {"owner@test.com", "core@test.com"}

    def test_invite_by_email_is_case_insensitive(self):
        r = client.post(f"/api/fests/{self.slug}/members", json={"email": "STUDENT@test.com", "role": "volunteer"}, headers=auth(self.core))
        assert r.status_code == 201 and r.json()["user_name"] == "Student"

    def test_unknown_email_explains_what_to_do(self):
        r = client.post(f"/api/fests/{self.slug}/members", json={"email": "nobody@test.com"}, headers=auth(self.owner))
        assert r.status_code == 404 and "sign up" in r.json()["detail"]

    def test_needs_user_or_email(self):
        assert client.post(f"/api/fests/{self.slug}/members", json={"role": "core"}, headers=auth(self.owner)).status_code == 422
