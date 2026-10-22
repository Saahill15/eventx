"""Access control and sessions: who may call what, and when a sign-in stops working."""

import re
from datetime import datetime, timedelta

from fastapi.routing import APIRoute

from app import models
from app.main import app
from app.auth import sessions
from test_fixes import user_token, user_id  # noqa: F401
from test_full import client, auth, create_college, reset_db, TestingSessionLocal  # noqa: F401

# Endpoints anyone may call without signing in. Anything not listed here must refuse anonymous callers.
PUBLIC = {
    ("GET", "/"), ("POST", "/api/auth/signup"), ("POST", "/api/auth/login"), ("POST", "/api/auth/admin/login"),
    ("GET", "/api/colleges/"), ("GET", "/api/colleges/{college_id}"), ("GET", "/api/colleges/{college_id}/events"),
    ("GET", "/api/events/"), ("GET", "/api/events/city"), ("GET", "/api/events/{event_id}"),
    ("GET", "/api/fests/"), ("GET", "/api/fests/{slug}"), ("GET", "/api/fests/{slug}/events"),
    ("GET", "/api/fests/{slug}/announcements"), ("GET", "/api/users/interests/all"), ("GET", "/api/events/{event_id}/questions"),
    ("GET", "/api/media/{media_id}"),
}


def concrete(path):
    return re.sub(r"\{[^}]+\}", "1", path)


def api_routes():
    for r in app.routes:
        if isinstance(r, APIRoute) and r.path.startswith(("/api", "/")) and r.path not in ("/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"):
            for m in r.methods - {"HEAD", "OPTIONS"}:
                yield m, r.path


class TestRouteProtection:
    def setup_method(self):
        self.member = user_token("Member", "member@test.com")
        self.organizer = user_token("Org", "org@test.com", "organizer")

    def test_every_non_public_route_refuses_anonymous_callers(self):
        leaks = []
        for method, path in api_routes():
            if (method, path) in PUBLIC:
                continue
            r = client.request(method, concrete(path), json={})
            if r.status_code != 401:
                leaks.append(f"{method} {path} -> {r.status_code}")
        assert not leaks, "reachable without signing in:\n" + "\n".join(leaks)

    def test_every_admin_route_refuses_members_and_organisers(self):
        leaks = []
        for method, path in api_routes():
            if not path.startswith("/api/admin") and not (method, path) in {("POST", "/api/colleges/"), ("PUT", "/api/colleges/{college_id}"), ("DELETE", "/api/colleges/{college_id}")}:
                continue
            for who, token in (("member", self.member), ("organiser", self.organizer)):
                r = client.request(method, concrete(path), json={}, headers=auth(token))
                if r.status_code != 403:
                    leaks.append(f"{who}: {method} {path} -> {r.status_code}")
        assert not leaks, "admin routes open to non-admins:\n" + "\n".join(leaks)

    def test_forged_and_tampered_tokens_are_refused(self):
        assert client.get("/api/users/me", headers=auth("not.a.token")).status_code == 401
        assert client.get("/api/users/me", headers=auth(self.member[:-3] + "abc")).status_code == 401

    def test_old_style_token_without_a_session_is_refused(self):
        from app.auth.jwt import create_token
        legacy = create_token({"sub": str(user_id("member@test.com")), "role": "user"})
        assert client.get("/api/users/me", headers=auth(legacy)).status_code == 401

    def test_cors_only_allows_the_site(self):
        ok = client.options("/api/users/me", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
        assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
        bad = client.options("/api/users/me", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
        assert "access-control-allow-origin" not in bad.headers

    def test_security_headers(self):
        r = client.get("/api/users/me", headers=auth(self.member))
        assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
        assert r.headers["cache-control"] == "no-store"


class TestSessions:
    def setup_method(self):
        self.admin = user_token("Admin", "admin@test.com", "admin")
        self.member = user_token("Member", "member@test.com")

    def _age(self, token_user_email, **delta):
        db = TestingSessionLocal()
        uid = db.query(models.User).filter(models.User.email == token_user_email).first().id
        for s in db.query(models.AuthSession).filter(models.AuthSession.user_id == uid):
            s.last_seen_at = datetime.utcnow() - timedelta(**delta)
        db.commit()
        db.close()

    def test_logout_kills_the_token(self):
        assert client.get("/api/users/me", headers=auth(self.member)).status_code == 200
        assert client.post("/api/auth/logout", headers=auth(self.member)).status_code == 200
        assert client.get("/api/users/me", headers=auth(self.member)).status_code == 401

    def test_admin_times_out_after_inactivity_but_members_do_not(self):
        self._age("admin@test.com", minutes=sessions.ADMIN_IDLE_MINUTES + 1)
        self._age("member@test.com", minutes=sessions.ADMIN_IDLE_MINUTES + 1)
        assert client.get("/api/admin/overview", headers=auth(self.admin)).status_code == 401
        assert client.get("/api/users/me", headers=auth(self.member)).status_code == 200

    def test_activity_keeps_an_admin_session_alive(self):
        self._age("admin@test.com", minutes=sessions.ADMIN_IDLE_MINUTES - 1)
        assert client.get("/api/admin/overview", headers=auth(self.admin)).status_code == 200  # refreshes last seen
        self._age("admin@test.com", minutes=sessions.ADMIN_IDLE_MINUTES - 1)
        assert client.get("/api/admin/overview", headers=auth(self.admin)).status_code == 200

    def test_login_reports_the_timeouts(self):
        r = client.post("/api/auth/admin/login", json={"email": "admin@test.com", "password": "password123"})
        assert r.status_code == 200 and r.json()["idle_timeout_seconds"] == sessions.ADMIN_IDLE_MINUTES * 60

    def test_suspending_and_role_changes_end_sessions(self):
        uid = user_id("member@test.com")
        client.post(f"/api/admin/users/{uid}/active", json={"is_active": False}, headers=auth(self.admin))
        client.post(f"/api/admin/users/{uid}/active", json={"is_active": True}, headers=auth(self.admin))
        assert client.get("/api/users/me", headers=auth(self.member)).status_code == 401  # session was ended

    def test_admin_can_sign_a_user_out(self):
        uid = user_id("member@test.com")
        assert client.post(f"/api/admin/users/{uid}/sign-out", headers=auth(self.admin)).json()["sessions_ended"] >= 1
        assert client.get("/api/users/me", headers=auth(self.member)).status_code == 401

    def test_password_change_ends_other_sessions_only(self):
        from test_fixes import login
        other_device = login("member@test.com")
        client.post("/api/users/me/password", json={"current_password": "password123", "new_password": "newpassword456"}, headers=auth(self.member))
        assert client.get("/api/users/me", headers=auth(self.member)).status_code == 200
        assert client.get("/api/users/me", headers=auth(other_device)).status_code == 401

    def test_sessions_list_and_end_one(self):
        from test_fixes import login
        second = login("member@test.com")
        rows = client.get("/api/auth/sessions", headers=auth(self.member)).json()
        assert len(rows) >= 2 and sum(r["current"] for r in rows) == 1
        other = next(r for r in rows if not r["current"])
        assert client.delete(f"/api/auth/sessions/{other['id']}", headers=auth(self.member)).status_code == 200
        assert client.get("/api/users/me", headers=auth(second)).status_code == 401
        # nobody else can end my sessions
        assert client.delete(f"/api/auth/sessions/{rows[0]['id']}", headers=auth(self.admin)).status_code == 404
