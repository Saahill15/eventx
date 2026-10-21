"""Gate check-in, registration and event cancellation, committee stats, student profile, migrations."""

import pytest

from test_fixes import user_token, user_id, city_event_payload  # noqa: F401
from test_full import (
    client, auth, create_college, create_fest, create_fest_event, get_entry_pass, reset_db,  # noqa: F401
)


class Setup:
    def setup_method(self):
        self.admin = user_token("Admin", "admin@test.com", "admin")
        self.owner = user_token("Owner", "owner@test.com", "organizer")
        self.volunteer = user_token("Vol", "vol@test.com")
        self.student = user_token("Student", "student@test.com")
        self.other = user_token("Other", "other@test.com")
        self.college_id = create_college(self.admin)
        self.fest = create_fest(self.owner, self.college_id)
        self.slug = self.fest["slug"]
        r = client.post(f"/api/fests/{self.slug}/members", json={"email": "vol@test.com", "role": "volunteer"}, headers=auth(self.owner))
        assert r.status_code == 201, r.text
        self.pass_data = get_entry_pass(self.student, self.slug).json()
        self.code = self.pass_data["qr_code"]


class TestGateByQr(Setup):
    def test_volunteer_can_look_up_and_check_in(self):
        r = client.get(f"/api/fests/{self.slug}/gate/lookup", params={"code": self.code}, headers=auth(self.volunteer))
        assert r.status_code == 200
        assert r.json()["user_name"] == "Student" and r.json()["checked_in"] is False
        r = client.post(f"/api/fests/{self.slug}/gate/check-in", json={"qr_code": self.code}, headers=auth(self.volunteer))
        assert r.status_code == 200 and r.json()["checked_in"] is True and r.json()["checked_in_at"]

    def test_second_scan_is_refused_with_the_time(self):
        client.post(f"/api/fests/{self.slug}/gate/check-in", json={"qr_code": self.code}, headers=auth(self.owner))
        r = client.post(f"/api/fests/{self.slug}/gate/check-in", json={"qr_code": self.code}, headers=auth(self.volunteer))
        assert r.status_code == 400 and "already used" in r.json()["detail"]

    def test_students_cannot_scan_or_look_up(self):
        assert client.post(f"/api/fests/{self.slug}/gate/check-in", json={"qr_code": self.code}, headers=auth(self.other)).status_code == 403
        assert client.get(f"/api/fests/{self.slug}/gate/lookup", params={"code": self.code}, headers=auth(self.student)).status_code == 403

    def test_unknown_code(self):
        r = client.post(f"/api/fests/{self.slug}/gate/check-in", json={"qr_code": "not-a-real-code-1234"}, headers=auth(self.owner))
        assert r.status_code == 404

    def test_code_from_another_fest_is_not_accepted(self):
        other_fest = create_fest(self.owner, self.college_id, slug="other-fest")
        r = client.post(f"/api/fests/{other_fest['slug']}/gate/check-in", json={"qr_code": self.code}, headers=auth(self.owner))
        assert r.status_code == 404

    def test_only_staff_can_undo(self):
        client.post(f"/api/fests/{self.slug}/gate/check-in", json={"qr_code": self.code}, headers=auth(self.volunteer))
        assert client.post(f"/api/fests/{self.slug}/gate/undo", json={"qr_code": self.code}, headers=auth(self.volunteer)).status_code == 403
        r = client.post(f"/api/fests/{self.slug}/gate/undo", json={"qr_code": self.code}, headers=auth(self.owner))
        assert r.status_code == 200 and r.json()["checked_in"] is False
        assert client.post(f"/api/fests/{self.slug}/gate/check-in", json={"qr_code": self.code}, headers=auth(self.volunteer)).status_code == 200

    def test_volunteer_can_use_the_old_pass_id_scan_too(self):
        r = client.post(f"/api/fests/{self.slug}/gate-scan/{self.pass_data['id']}", headers=auth(self.volunteer))
        assert r.status_code == 200


class TestEventCheckIn(Setup):
    def setup_method(self):
        super().setup_method()
        self.event = create_fest_event(self.owner, self.fest["id"], self.college_id, requires_registration=True, approval_mode="auto")
        client.post(f"/api/fest-events/{self.event['id']}/register", headers=auth(self.student))

    def test_registered_student_is_checked_in_once(self):
        url = f"/api/fest-events/{self.event['id']}/check-in"
        r = client.post(url, json={"qr_code": self.code}, headers=auth(self.volunteer))
        assert r.status_code == 200 and r.json()["attended"] is True
        assert client.post(url, json={"qr_code": self.code}, headers=auth(self.volunteer)).status_code == 400

    def test_unregistered_student_is_refused(self):
        other_pass = get_entry_pass(self.other, self.slug).json()
        r = client.post(f"/api/fest-events/{self.event['id']}/check-in", json={"qr_code": other_pass["qr_code"]}, headers=auth(self.volunteer))
        assert r.status_code == 400 and "not registered" in r.json()["detail"]

    def test_pending_registration_is_refused(self):
        manual = create_fest_event(self.owner, self.fest["id"], self.college_id, title="Manual", requires_registration=True, approval_mode="manual")
        client.post(f"/api/fest-events/{manual['id']}/register", headers=auth(self.student))
        r = client.post(f"/api/fest-events/{manual['id']}/check-in", json={"qr_code": self.code}, headers=auth(self.volunteer))
        assert r.status_code == 400 and "not approved" in r.json()["detail"]

    def test_open_event_records_attendance_without_registration(self):
        open_event = create_fest_event(self.owner, self.fest["id"], self.college_id, title="Open", requires_registration=False)
        r = client.post(f"/api/fest-events/{open_event['id']}/check-in", json={"qr_code": self.code}, headers=auth(self.volunteer))
        assert r.status_code == 200 and r.json()["attended"] is True

    def test_students_cannot_check_people_in(self):
        r = client.post(f"/api/fest-events/{self.event['id']}/check-in", json={"qr_code": self.code}, headers=auth(self.other))
        assert r.status_code == 403

    def test_attendance_shows_in_csv_and_stats(self):
        client.post(f"/api/fest-events/{self.event['id']}/check-in", json={"qr_code": self.code}, headers=auth(self.volunteer))
        csv_text = client.get(f"/api/fest-events/{self.event['id']}/registrations.csv", headers=auth(self.owner)).text
        assert "Attended this event" in csv_text.splitlines()[0]
        assert csv_text.splitlines()[1].split(",")[5] == "yes"
        stats = client.get(f"/api/fests/{self.slug}/manage/stats", headers=auth(self.owner)).json()
        row = next(e for e in stats["events"] if e["id"] == self.event["id"])
        assert row["registered"] == 1 and row["attended"] == 1


class TestCancelRegistration(Setup):
    def setup_method(self):
        super().setup_method()
        self.event = create_fest_event(self.owner, self.fest["id"], self.college_id, requires_registration=True, registration_limit=1)
        assert client.post(f"/api/fest-events/{self.event['id']}/register", headers=auth(self.student)).status_code == 201

    def test_cancelling_frees_the_seat(self):
        get_entry_pass(self.other, self.slug)
        assert client.post(f"/api/fest-events/{self.event['id']}/register", headers=auth(self.other)).status_code == 400  # full
        assert client.delete(f"/api/fest-events/{self.event['id']}/register", headers=auth(self.student)).status_code == 204
        assert client.post(f"/api/fest-events/{self.event['id']}/register", headers=auth(self.other)).status_code == 201

    def test_can_register_again_after_cancelling(self):
        client.delete(f"/api/fest-events/{self.event['id']}/register", headers=auth(self.student))
        assert client.post(f"/api/fest-events/{self.event['id']}/register", headers=auth(self.student)).status_code == 201

    def test_cannot_cancel_someone_elses_or_a_missing_registration(self):
        assert client.delete(f"/api/fest-events/{self.event['id']}/register", headers=auth(self.other)).status_code == 404

    def test_cannot_cancel_after_attending(self):
        client.post(f"/api/fest-events/{self.event['id']}/check-in", json={"qr_code": self.code}, headers=auth(self.owner))
        assert client.delete(f"/api/fest-events/{self.event['id']}/register", headers=auth(self.student)).status_code == 400


class TestCancelEvent(Setup):
    def setup_method(self):
        super().setup_method()
        self.event = create_fest_event(self.owner, self.fest["id"], self.college_id, requires_registration=True)

    def test_committee_can_cancel_and_restore(self):
        r = client.post(f"/api/events/{self.event['id']}/cancel", json={"reason": "Rain"}, headers=auth(self.owner))
        assert r.status_code == 200 and r.json()["cancelled"] is True and r.json()["cancel_reason"] == "Rain"
        assert client.get(f"/api/events/{self.event['id']}").json()["cancelled"] is True
        r = client.post(f"/api/events/{self.event['id']}/restore", headers=auth(self.owner))
        assert r.json()["cancelled"] is False

    def test_registration_is_blocked_while_cancelled(self):
        client.post(f"/api/events/{self.event['id']}/cancel", json={}, headers=auth(self.owner))
        r = client.post(f"/api/fest-events/{self.event['id']}/register", headers=auth(self.student))
        assert r.status_code == 400 and "cancelled" in r.json()["detail"]

    def test_outsiders_cannot_cancel(self):
        stranger = user_token("Stranger", "stranger@test.com", "organizer")
        assert client.post(f"/api/events/{self.event['id']}/cancel", json={}, headers=auth(stranger)).status_code == 403
        assert client.post(f"/api/events/{self.event['id']}/cancel", json={}, headers=auth(self.student)).status_code == 403

    def test_cannot_cancel_twice(self):
        client.post(f"/api/events/{self.event['id']}/cancel", json={}, headers=auth(self.owner))
        assert client.post(f"/api/events/{self.event['id']}/cancel", json={}, headers=auth(self.owner)).status_code == 400

    def test_city_event_cancel_blocks_legacy_pass(self):
        r = client.post("/api/events/", json=city_event_payload(), headers=auth(self.owner))
        event_id = r.json()["id"]
        client.post(f"/api/admin/events/{event_id}/approve", headers=auth(self.admin))
        client.post(f"/api/events/{event_id}/cancel", json={}, headers=auth(self.owner))
        assert client.post(f"/api/passes/{event_id}/register", headers=auth(self.student)).status_code == 400


class TestStats(Setup):
    def test_counts_and_permissions(self):
        e = create_fest_event(self.owner, self.fest["id"], self.college_id, requires_registration=True, approval_mode="manual")
        client.post(f"/api/fest-events/{e['id']}/register", headers=auth(self.student))
        client.post(f"/api/fests/{self.slug}/gate/check-in", json={"qr_code": self.code}, headers=auth(self.owner))
        stats = client.get(f"/api/fests/{self.slug}/manage/stats", headers=auth(self.owner)).json()
        assert stats["passes_issued"] == 1 and stats["passes_checked_in"] == 1
        assert stats["events"][0]["pending"] == 1
        assert client.get(f"/api/fests/{self.slug}/manage/stats", headers=auth(self.volunteer)).status_code == 403
        assert client.get(f"/api/fests/{self.slug}/manage/stats", headers=auth(self.student)).status_code == 403


class TestProfile(Setup):
    def test_update_profile_fields(self):
        r = client.patch("/api/users/me", json={"name": "  New Name ", "college_id": self.college_id, "study_year": 2, "phone": "+91 98765 43210"}, headers=auth(self.student))
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "New Name" and body["college_id"] == self.college_id and body["study_year"] == 2
        assert client.get("/api/users/me", headers=auth(self.student)).json()["study_year"] == 2

    def test_validation(self):
        assert client.patch("/api/users/me", json={"college_id": 9999}, headers=auth(self.student)).status_code == 400
        assert client.patch("/api/users/me", json={"study_year": 12}, headers=auth(self.student)).status_code == 422
        assert client.patch("/api/users/me", json={"phone": "abc"}, headers=auth(self.student)).status_code == 422

    def test_phone_must_be_unique(self):
        client.patch("/api/users/me", json={"phone": "9876543210"}, headers=auth(self.student))
        assert client.patch("/api/users/me", json={"phone": "9876543210"}, headers=auth(self.other)).status_code == 400

    def test_blank_name_is_ignored_not_saved(self):
        r = client.patch("/api/users/me", json={"name": None}, headers=auth(self.student))
        assert r.json()["name"] == "Student"

    def test_change_password(self):
        assert client.post("/api/users/me/password", json={"current_password": "wrong-password", "new_password": "a-new-password-1"}, headers=auth(self.student)).status_code == 400
        assert client.post("/api/users/me/password", json={"current_password": "password123", "new_password": "short"}, headers=auth(self.student)).status_code == 422
        assert client.post("/api/users/me/password", json={"current_password": "password123", "new_password": "a-new-password-1"}, headers=auth(self.student)).status_code == 200
        r = client.post("/api/auth/login", json={"email": "student@test.com", "password": "a-new-password-1"})
        assert r.status_code == 200
        assert client.post("/api/auth/login", json={"email": "student@test.com", "password": "password123"}).status_code == 401


class TestMigrations:
    def test_fresh_database_reaches_head_and_matches_models(self, tmp_path, monkeypatch):
        from sqlalchemy import create_engine, inspect
        db_url = f"sqlite:///{tmp_path}/m.db"
        eng = create_engine(db_url)
        from alembic import command
        from alembic.config import Config
        from app import migrate
        cfg = Config(str(migrate.BACKEND_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(migrate.BACKEND_DIR / "migrations"))
        from app import database
        monkeypatch.setattr(database, "engine", eng)
        command.upgrade(cfg, "head")
        tables = set(inspect(eng).get_table_names())
        assert {"users", "events", "fest_passes", "event_registrations", "alembic_version"} <= tables
        cols = {c["name"] for c in inspect(eng).get_columns("event_registrations")}
        assert {"attended", "attended_at", "attended_by"} <= cols
