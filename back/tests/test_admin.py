"""Admin dashboard: overview numbers and suspending accounts."""

from test_fixes import user_token, user_id  # noqa: F401
from test_full import client, auth, create_college, login, reset_db, signup_payload  # noqa: F401


class TestAdminDashboard:
    def setup_method(self):
        self.admin = user_token("Admin", "admin@test.com", "admin")
        self.member = user_token("Member", "member@test.com")

    def test_overview_is_admin_only(self):
        assert client.get("/api/admin/overview", headers=auth(self.member)).status_code == 403
        assert client.get("/api/admin/overview").status_code == 401

    def test_overview_counts(self):
        create_college(self.admin)
        o = client.get("/api/admin/overview", headers=auth(self.admin)).json()
        assert o["admins"] == 1 and o["members"] == 1 and o["organizers"] == 0
        assert o["suspended"] == 0 and o["fests_in_review"] == 0 and o["verifications_pending"] == 0

    def test_suspend_and_reactivate(self):
        uid = user_id("member@test.com")
        r = client.post(f"/api/admin/users/{uid}/active", json={"is_active": False}, headers=auth(self.admin))
        assert r.status_code == 200 and r.json()["is_active"] is False
        assert client.get("/api/users/me", headers=auth(self.member)).status_code == 403
        assert client.get("/api/admin/overview", headers=auth(self.admin)).json()["suspended"] == 1
        assert client.post(f"/api/admin/users/{uid}/active", json={"is_active": True}, headers=auth(self.admin)).json()["is_active"] is True
        # suspending ended their sessions, so reactivating means signing in again
        assert client.get("/api/users/me", headers=auth(self.member)).status_code == 401
        assert client.get("/api/users/me", headers=auth(login("member@test.com"))).status_code == 200

    def test_cannot_suspend_self_or_other_admins(self):
        me = user_id("admin@test.com")
        assert client.post(f"/api/admin/users/{me}/active", json={"is_active": False}, headers=auth(self.admin)).status_code == 400
        user_token("Other", "other@test.com", "admin")
        other = user_id("other@test.com")
        assert client.post(f"/api/admin/users/{other}/active", json={"is_active": False}, headers=auth(self.admin)).status_code == 400

    def test_members_cannot_suspend(self):
        me = user_id("member@test.com")
        assert client.post(f"/api/admin/users/{me}/active", json={"is_active": False}, headers=auth(self.member)).status_code == 403


class TestSignupFields:
    def test_signup_stores_the_new_fields(self):
        admin = user_token("Admin", "admin@test.com", "admin")
        r = client.post("/api/auth/signup", json=signup_payload("Asha Rao", "asha@test.com"))
        assert r.status_code == 200, r.text
        me = client.get("/api/users/me", headers=auth(r.json()["access_token"])).json()
        assert (me["first_name"], me["last_name"], me["name"], me["college_id"]) == ("Asha", "Rao", "Asha Rao", None)

    def test_required_fields_and_terms(self):
        base = signup_payload("Asha Rao", "asha@test.com")
        for missing in ("first_name", "last_name", "date_of_birth", "email", "password"):
            assert client.post("/api/auth/signup", json={k: v for k, v in base.items() if k != missing}).status_code == 422, missing
        assert client.post("/api/auth/signup", json={**base, "accept_terms": False}).status_code == 422

    def test_date_of_birth_is_checked(self):
        from datetime import date
        today = date.today()
        too_young = today.replace(year=today.year - 12).isoformat()
        old_enough = today.replace(year=today.year - 13).isoformat()
        assert client.post("/api/auth/signup", json=signup_payload("Kid One", "kid@test.com", date_of_birth=too_young)).status_code == 422
        assert client.post("/api/auth/signup", json=signup_payload("Kid Two", "kid2@test.com", date_of_birth=today.isoformat())).status_code == 422
        assert client.post("/api/auth/signup", json=signup_payload("Old One", "old@test.com", date_of_birth="1850-01-01")).status_code == 422
        ok = client.post("/api/auth/signup", json=signup_payload("Teen One", "teen@test.com", date_of_birth=old_enough))
        assert ok.status_code == 200
        me = client.get("/api/users/me", headers=auth(ok.json()["access_token"])).json()
        assert me["date_of_birth"] == old_enough

    def test_sign_up_does_not_ask_for_a_phone_number(self):
        assert "phone" not in signup_payload("Asha Rao", "asha@test.com")
        r = client.post("/api/auth/signup", json=signup_payload("Asha Rao", "asha@test.com"))
        assert r.status_code == 200
        assert client.get("/api/users/me", headers=auth(r.json()["access_token"])).json()["phone"] is None

    def test_changing_names_updates_the_display_name(self):
        t = user_token("Asha Rao", "asha@test.com")
        me = client.patch("/api/users/me", json={"last_name": "Iyer"}, headers=auth(t)).json()
        assert me["name"] == "Asha Iyer"


class TestOrganiserPromotion:
    def setup_method(self):
        self.admin = user_token("Admin", "admin@test.com", "admin")
        self.college = create_college(self.admin)
        self.member = user_token("Member", "member@test.com")
        self.uid = user_id("member@test.com")

    def test_welcome_shows_once_after_promotion(self):
        assert client.get("/api/users/me", headers=auth(self.member)).json()["organizer_welcome_pending"] is False
        client.post(f"/api/admin/users/{self.uid}/role", json={"role": "organizer", "college_ids": [self.college]}, headers=auth(self.admin))
        me = client.get("/api/users/me", headers=auth(self.member)).json()
        assert me["role"] == "organizer" and me["organizer_welcome_pending"] is True and me["college_ids"] == [self.college]
        assert client.post("/api/users/me/organizer-welcome/seen", headers=auth(self.member)).status_code == 200
        assert client.get("/api/users/me", headers=auth(self.member)).json()["organizer_welcome_pending"] is False

    def test_changing_colleges_does_not_show_it_again(self):
        client.post(f"/api/admin/users/{self.uid}/role", json={"role": "organizer", "college_ids": [self.college]}, headers=auth(self.admin))
        client.post("/api/users/me/organizer-welcome/seen", headers=auth(self.member))
        client.put(f"/api/admin/users/{self.uid}/colleges", json={"college_ids": [self.college]}, headers=auth(self.admin))
        assert client.get("/api/users/me", headers=auth(self.member)).json()["organizer_welcome_pending"] is False

    def test_city_event_rejection_carries_a_reason(self):
        org = user_token("Org", "org@test.com", "organizer")
        ev = client.post("/api/events/", json={"event_type": "city", "title": "Open Mic", "date": "2026-12-01T10:00:00"}, headers=auth(org)).json()
        assert client.post(f"/api/admin/events/{ev['id']}/reject", json={"reason": "Please add a venue"}, headers=auth(self.admin)).status_code == 200
        mine = client.get("/api/events/mine", headers=auth(org)).json()
        assert mine[0]["status"] == "rejected" and mine[0]["reject_reason"] == "Please add a venue"

    def test_editing_a_city_event_sends_it_back_to_review(self):
        org = user_token("Org2", "org2@test.com", "organizer")
        ev = client.post("/api/events/", json={"event_type": "city", "title": "Open Mic", "date": "2026-12-01T10:00:00"}, headers=auth(org)).json()
        client.post(f"/api/admin/events/{ev['id']}/approve", headers=auth(self.admin))
        assert client.get(f"/api/events/{ev['id']}").status_code == 200
        client.patch(f"/api/events/{ev['id']}", json={"title": "Something else"}, headers=auth(org))
        assert client.get(f"/api/events/{ev['id']}").status_code == 404  # hidden until HiveOut approves the change
        assert client.get("/api/events/mine", headers=auth(org)).json()[0]["status"] == "pending"


class TestAdminSignIn:
    def setup_method(self):
        from app.routes import auth as auth_routes
        auth_routes.reset_login_throttle()
        self.admin = user_token("Admin", "admin@test.com", "admin")
        self.member = user_token("Member", "member@test.com")
        self.creds = {"email": "admin@test.com", "password": "password123"}

    def test_admins_cannot_use_the_public_sign_in(self):
        r = client.post("/api/auth/login", json=self.creds)
        assert r.status_code == 403 and "admin" in r.json()["detail"].lower()
        assert "access_token" not in r.json()

    def test_a_wrong_password_on_the_public_page_does_not_reveal_an_admin(self):
        r = client.post("/api/auth/login", json={**self.creds, "password": "wrong-password"})
        assert r.status_code == 401 and r.json()["detail"] == "Invalid credentials"

    def test_admin_sign_in_works_for_admins_only(self):
        assert client.post("/api/auth/admin/login", json=self.creds).status_code == 200
        r = client.post("/api/auth/admin/login", json={"email": "member@test.com", "password": "password123"})
        assert r.status_code == 401 and r.json()["detail"] == "Invalid credentials"   # same answer as a wrong password
        assert client.post("/api/auth/admin/login", json={"email": "nobody@test.com", "password": "password123"}).status_code == 401

    def test_members_still_sign_in_normally(self):
        assert client.post("/api/auth/login", json={"email": "member@test.com", "password": "password123"}).status_code == 200

    def test_admin_sign_in_locks_after_five_failures(self):
        for _ in range(5):
            assert client.post("/api/auth/admin/login", json={**self.creds, "password": "nope-nope"}).status_code == 401
        assert client.post("/api/auth/admin/login", json=self.creds).status_code == 429   # even the right password waits

    def test_every_attempt_is_logged(self):
        client.post("/api/auth/admin/login", json={**self.creds, "password": "nope-nope"})
        client.post("/api/auth/admin/login", json={"email": "member@test.com", "password": "password123"})
        client.post("/api/auth/login", json=self.creds)
        ok = client.post("/api/auth/admin/login", json=self.creds).json()["access_token"]
        rows = client.get("/api/admin/security-log", headers=auth(ok)).json()
        reasons = [(r["portal"], r["success"], r["reason"]) for r in rows]
        assert ("admin", False, "bad_credentials") in reasons and ("admin", False, "not_admin") in reasons
        assert ("public", False, "admin_on_public_page") in reasons and ("admin", True, "ok") in reasons
        assert all("password" not in str(r).lower() for r in rows)
        assert len(client.get("/api/admin/security-log?failed_only=true", headers=auth(ok)).json()) < len(rows)
        assert client.get("/api/admin/security-log", headers=auth(self.member)).status_code == 403
