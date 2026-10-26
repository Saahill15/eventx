"""Regression tests for the permission, visibility and validation fixes."""

import pytest

from test_full import (  # shared app, in-memory DB and helpers
    client, auth, signup, signup_payload, login, make_admin, make_organizer, TestingSessionLocal,
    create_college, create_fest, create_fest_event, approve_event, get_entry_pass, reset_db, join_team,  # noqa: F401
)
from app import models
from app.routes import auth as auth_routes


@pytest.fixture(autouse=True)
def fresh_throttle():
    auth_routes.reset_login_throttle()


def user_token(name, email, role=None):
    signup(name, email)
    if role == "admin":
        make_admin(email)
    elif role == "organizer":
        make_organizer(email)
    return login(email)


def city_event_payload(**overrides):
    payload = {"event_type": "city", "title": "Open Mic", "date": "2026-12-01T10:00:00", "category": "Music"}
    payload.update(overrides)
    return payload


def user_id(email):
    db = TestingSessionLocal()
    uid = db.query(models.User).filter(models.User.email == email).first().id
    db.close()
    return uid


class TestAccounts:
    def test_short_password_rejected(self):
        r = client.post("/api/auth/signup", json=signup_payload("A B", "a@test.com", "short"))
        assert r.status_code == 422

    def test_email_is_case_insensitive(self):
        signup("Alice", "Alice@Test.com")
        assert login("alice@test.com")
        r = client.post("/api/auth/signup", json=signup_payload("Alice2", "ALICE@test.com"))
        assert r.status_code == 400

    def test_blank_name_rejected(self):
        r = client.post("/api/auth/signup", json={**signup_payload("A B", "a@test.com"), "first_name": "   "})
        assert r.status_code == 422

    def test_disabled_account_cannot_log_in_or_use_token(self):
        token = user_token("Alice", "alice@test.com")
        db = TestingSessionLocal()
        db.query(models.User).filter(models.User.email == "alice@test.com").first().is_active = False
        db.commit()
        db.close()
        assert client.get("/api/users/me", headers=auth(token)).status_code == 403
        r = client.post("/api/auth/login", json={"email": "alice@test.com", "password": "password123"})
        assert r.status_code == 403

    def test_repeated_failed_logins_are_throttled(self):
        signup("Alice", "alice@test.com")
        codes = [
            client.post("/api/auth/login", json={"email": "alice@test.com", "password": "wrong-password"}).status_code
            for _ in range(11)
        ]
        assert codes[:10] == [401] * 10
        assert codes[10] == 429
        # even the right password is refused while throttled
        assert client.post("/api/auth/login", json={"email": "alice@test.com", "password": "password123"}).status_code == 429

    def test_unknown_interest_rejected(self):
        token = user_token("Alice", "alice@test.com")
        r = client.post("/api/users/interests", json={"interest_ids": [9999]}, headers=auth(token))
        assert r.status_code == 400


class TestEventVisibility:
    def setup_method(self):
        self.admin = user_token("Admin", "admin@test.com", "admin")
        self.org = user_token("Org", "org@test.com", "organizer")
        self.other_org = user_token("Org2", "org2@test.com", "organizer")
        r = client.post("/api/events/", json=city_event_payload(), headers=auth(self.org))
        assert r.status_code == 200, r.text
        self.event_id = r.json()["id"]

    def test_pending_event_hidden_from_public(self):
        assert client.get(f"/api/events/{self.event_id}").status_code == 404

    def test_pending_event_visible_to_owner_and_admin_only(self):
        assert client.get(f"/api/events/{self.event_id}", headers=auth(self.org)).status_code == 200
        assert client.get(f"/api/events/{self.event_id}", headers=auth(self.admin)).status_code == 200
        assert client.get(f"/api/events/{self.event_id}", headers=auth(self.other_org)).status_code == 404

    def test_city_list_never_falls_back_to_pending_events(self):
        assert client.get("/api/events/city").json() == []

    def test_approved_event_is_public(self):
        approve_event(self.admin, self.event_id)
        assert client.get(f"/api/events/{self.event_id}").status_code == 200

    def test_cannot_register_for_unapproved_event(self):
        buyer = user_token("Buyer", "buyer@test.com")
        assert client.post(f"/api/passes/{self.event_id}/register", headers=auth(buyer)).status_code == 404


class TestEventCreation:
    def setup_method(self):
        self.admin = user_token("Admin", "admin@test.com", "admin")
        self.owner = user_token("Owner", "owner@test.com", "organizer")
        self.outsider = user_token("Outsider", "outsider@test.com", "organizer")
        self.college_id = create_college(self.admin)
        self.fest = create_fest(self.owner, self.college_id)

    def fest_payload(self):
        return {"event_type": "fest", "title": "Talk", "date": "2026-12-01T10:00:00", "fest_id": self.fest["id"],
                "location": "Hall A", "time": "10:00", "end_time": "11:00", "description": "A talk."}

    def test_outsider_cannot_add_event_to_someone_elses_fest(self):
        r = client.post("/api/events/", json=self.fest_payload(), headers=auth(self.outsider))
        assert r.status_code == 403

    def test_fest_owner_can_add_event(self):
        assert client.post("/api/events/", json=self.fest_payload(), headers=auth(self.owner)).status_code == 200

    def test_unknown_fest_and_college_rejected(self):
        bad_fest = dict(self.fest_payload(), fest_id=9999)
        assert client.post("/api/events/", json=bad_fest, headers=auth(self.owner)).status_code == 400
        bad_college = city_event_payload(college_id=9999)
        assert client.post("/api/events/", json=bad_college, headers=auth(self.owner)).status_code == 400

    def test_negative_or_missing_price_rejected(self):
        r = client.post("/api/events/", json=city_event_payload(is_free=False, price=-5), headers=auth(self.owner))
        assert r.status_code == 422
        r = client.post("/api/events/", json=city_event_payload(is_free=False, price=0), headers=auth(self.owner))
        assert r.status_code == 422

    def test_free_event_price_forced_to_zero(self):
        r = client.post("/api/events/", json=city_event_payload(is_free=True, price=99), headers=auth(self.owner))
        assert r.status_code == 200
        assert r.json()["price"] == 0

    def test_null_price_in_update_is_ignored(self):
        r = client.post("/api/events/", json=city_event_payload(), headers=auth(self.owner))
        event_id = r.json()["id"]
        r = client.patch(f"/api/events/{event_id}", json={"price": None, "title": None}, headers=auth(self.owner))
        assert r.status_code == 200
        assert r.json()["title"] == "Open Mic"

    def test_event_missing_type_is_a_validation_error(self):
        payload = city_event_payload()
        del payload["event_type"]
        assert client.post("/api/events/", json=payload, headers=auth(self.owner)).status_code == 422


class TestFestPermissions:
    def setup_method(self):
        self.admin = user_token("Admin", "admin@test.com", "admin")
        self.owner = user_token("Owner", "owner@test.com", "organizer")
        self.core = user_token("Core", "core@test.com", "organizer")
        self.core2 = user_token("Core2", "core2@test.com", "organizer")
        self.volunteer = user_token("Vol", "vol@test.com")
        self.college_id = create_college(self.admin)
        self.fest = create_fest(self.owner, self.college_id)
        self.slug = self.fest["slug"]
        join_team(self.owner, self.slug, "core@test.com", "core", self.core)
        join_team(self.owner, self.slug, "core2@test.com", "core", self.core2)

    def add(self, token, email, role):
        return client.post(f"/api/fests/{self.slug}/members", json={"user_id": user_id(email), "role": role}, headers=auth(token))

    def test_core_cannot_demote_the_owner(self):
        r = self.add(self.core, "owner@test.com", "volunteer")
        assert r.status_code == 403

    def test_core_cannot_promote_or_change_core_members(self):
        assert self.add(self.core, "vol@test.com", "core").status_code == 403
        assert self.add(self.core, "core2@test.com", "volunteer").status_code == 403

    def test_core_can_add_volunteers(self):
        assert self.add(self.core, "vol@test.com", "volunteer").status_code == 201

    def test_core_cannot_remove_core_but_owner_can(self):
        r = client.delete(f"/api/fests/{self.slug}/members/{user_id('core2@test.com')}", headers=auth(self.core))
        assert r.status_code == 403
        r = client.delete(f"/api/fests/{self.slug}/members/{user_id('core2@test.com')}", headers=auth(self.owner))
        assert r.status_code == 204

    def test_draft_fest_hidden_from_public_but_not_staff(self):
        r = client.patch(f"/api/fests/{self.slug}/status", json={"status": "draft"}, headers=auth(self.owner))
        assert r.status_code == 200
        assert client.get(f"/api/fests/{self.slug}").status_code == 404
        assert client.get(f"/api/fests/{self.slug}/events").status_code == 404
        assert client.get(f"/api/fests/{self.slug}", headers=auth(self.owner)).status_code == 200
        assert client.get(f"/api/fests/{self.slug}", headers=auth(self.volunteer)).status_code == 404

    def test_invalid_status_rejected(self):
        r = client.patch(f"/api/fests/{self.slug}/status", json={"status": "bogus"}, headers=auth(self.owner))
        assert r.status_code == 400
        assert client.patch(f"/api/fests/{self.slug}/status", json={}, headers=auth(self.owner)).status_code == 400

    @pytest.mark.parametrize("slug", ["all", "Bad Slug", "UPPER", "a", "-x-"])
    def test_bad_fest_slugs_rejected(self, slug):
        r = client.post("/api/fests/", json={"slug": slug, "name": "X"}, headers=auth(self.owner))
        assert r.status_code == 422


class TestLegacyPassesAndFestRegistration:
    def setup_method(self):
        self.admin = user_token("Admin", "admin@test.com", "admin")
        self.owner = user_token("Owner", "owner@test.com", "organizer")
        self.user = user_token("User", "user@test.com")
        college_id = create_college(self.admin)
        self.fest = create_fest(self.owner, college_id)
        self.fest_event = create_fest_event(self.owner, self.fest["id"], college_id, requires_registration=True)

    def test_fest_events_cannot_use_the_legacy_pass_endpoint(self):
        approve_event(self.admin, self.fest_event["id"])
        r = client.post(f"/api/passes/{self.fest_event['id']}/register", headers=auth(self.user))
        assert r.status_code == 400

    def test_unapproved_fest_event_cannot_be_registered_for(self):
        client.post(f"/api/admin/events/{self.fest_event['id']}/reject", headers=auth(self.admin))
        get_entry_pass(self.user, self.fest["slug"])
        r = client.post(f"/api/fest-events/{self.fest_event['id']}/register", headers=auth(self.user))
        assert r.status_code == 404

    def test_my_fest_passes_lists_passes_with_fest_details(self):
        get_entry_pass(self.user, self.fest["slug"])
        r = client.get("/api/users/me/fest-passes", headers=auth(self.user))
        assert r.status_code == 200
        assert r.json()[0]["fest_slug"] == self.fest["slug"]
        assert r.json()[0]["fest_name"] == self.fest["name"]


class TestCommitteeOwnership:
    def setup_method(self):
        self.owner = user_token("Owner", "owner@test.com", "organizer")
        self.intruder = user_token("Intruder", "intruder@test.com", "organizer")
        event_id = client.post("/api/events/", json=city_event_payload(), headers=auth(self.owner)).json()["id"]
        r = client.post(f"/api/events/{event_id}/committees", json={"name": "Ops"}, headers=auth(self.owner))
        assert r.status_code == 200, r.text
        self.committee_id = r.json()["id"]

    def test_owner_can_build_the_committee(self):
        r = client.post(f"/api/events/committees/{self.committee_id}/departments", json={"name": "Logistics"}, headers=auth(self.owner))
        assert r.status_code == 200
        dept_id = r.json()["id"]
        r = client.post(f"/api/events/departments/{dept_id}/members", json={"user_id": user_id("owner@test.com")}, headers=auth(self.owner))
        assert r.status_code == 200

    def test_other_organizers_cannot_touch_it(self):
        r = client.post(f"/api/events/committees/{self.committee_id}/departments", json={"name": "Spam"}, headers=auth(self.intruder))
        assert r.status_code == 404
        r = client.post(f"/api/events/committees/{self.committee_id}/departments", json={"name": "Real"}, headers=auth(self.owner))
        dept_id = r.json()["id"]
        r = client.post(f"/api/events/departments/{dept_id}/members", json={"user_id": user_id("intruder@test.com")}, headers=auth(self.intruder))
        assert r.status_code == 404


class TestAdminRoles:
    def setup_method(self):
        self.admin = user_token("Admin", "admin@test.com", "admin")
        self.user = user_token("Asha Rao", "asha@test.com")
        self.other = user_token("Other", "other@test.com")
        self.college_id = create_college(self.admin)

    def test_requesting_organiser_access_no_longer_exists(self):
        assert client.post("/api/users/request-organizer", headers=auth(self.user)).status_code in (404, 405)
        assert client.get("/api/admin/organizer-requests", headers=auth(self.admin)).status_code in (404, 405)

    def test_admin_can_search_users_by_name_or_email(self):
        by_name = client.get("/api/admin/users", params={"q": "asha"}, headers=auth(self.admin)).json()
        assert [u["email"] for u in by_name] == ["asha@test.com"]
        by_email = client.get("/api/admin/users", params={"q": "OTHER@test"}, headers=auth(self.admin)).json()
        assert [u["name"] for u in by_email] == ["Other User"]
        assert "hashed_password" not in by_name[0]

    def test_only_admins_can_use_it(self):
        assert client.get("/api/admin/users", headers=auth(self.user)).status_code == 403
        assert client.post(f"/api/admin/users/{user_id('other@test.com')}/role", json={"role": "organizer"}, headers=auth(self.user)).status_code == 403

    def test_promote_and_demote(self):
        uid = user_id("asha@test.com")
        r = client.post(f"/api/admin/users/{uid}/role", json={"role": "organizer", "college_ids": [self.college_id]}, headers=auth(self.admin))
        assert r.status_code == 200 and r.json()["role"] == "organizer" and r.json()["college_ids"] == [self.college_id]
        # the new organiser can start a fest for that college straight away
        assert client.post("/api/fests/", json={"slug": "asha-fest", "name": "Asha Fest", "college_id": self.college_id}, headers=auth(self.user)).status_code == 201
        # but cannot be demoted while they own a fest
        r = client.post(f"/api/admin/users/{uid}/role", json={"role": "user"}, headers=auth(self.admin))
        assert r.status_code == 400 and "owns a fest" in r.json()["detail"]

    def test_demote_organiser_with_no_fest(self):
        uid = user_id("other@test.com")
        client.post(f"/api/admin/users/{uid}/role", json={"role": "organizer", "college_ids": [self.college_id]}, headers=auth(self.admin))
        r = client.post(f"/api/admin/users/{uid}/role", json={"role": "user"}, headers=auth(self.admin))
        assert r.status_code == 200 and r.json()["role"] == "user" and r.json()["college_ids"] == []

    def test_guards(self):
        admin_id = user_id("admin@test.com")
        assert client.post(f"/api/admin/users/{admin_id}/role", json={"role": "user"}, headers=auth(self.admin)).status_code == 400
        assert client.post("/api/admin/users/9999/role", json={"role": "organizer"}, headers=auth(self.admin)).status_code == 404
        assert client.post(f"/api/admin/users/{user_id('asha@test.com')}/role", json={"role": "admin"}, headers=auth(self.admin)).status_code == 422
