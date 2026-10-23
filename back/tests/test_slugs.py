"""Custom short addresses (hiveout.in/name): availability, blocked names, who may claim, and where they lead."""

from pathlib import Path

import pytest

from app.routes import short_links as short_link_routes
from app.short_links import RESERVED_SHORT_NAMES
from test_fixes import user_token, user_id  # noqa: F401
from test_full import client, auth, create_college, make_organizer, reset_db, TestingSessionLocal  # noqa: F401
from app import models

APP_DIR = Path(__file__).resolve().parents[2] / "front" / "src" / "app"


def site_routes():
    """Top-level addresses the website serves: its folders and route files, minus groups, dynamic segments and private folders."""
    names = set()
    for entry in APP_DIR.iterdir():
        name = entry.stem if entry.is_file() else entry.name
        if name.startswith(("(", "[", "_", "@")) or entry.suffix not in ("", ".ts", ".tsx"):
            continue
        if entry.is_file() and name in ("page", "layout", "template", "not-found", "globals", "loading", "error"):
            continue
        names.add(name)
    return names


@pytest.mark.skipif(not APP_DIR.exists(), reason="the website is not checked out next to the API")
def test_every_page_of_the_site_is_off_limits_to_short_names():
    missing = sorted(site_routes() - RESERVED_SHORT_NAMES)
    assert not missing, f"Add these to RESERVED_SHORT_NAMES in app/short_links.py, or someone could take their address: {missing}"


class Setup:
    def setup_method(self):
        short_link_routes.reset_rate_limit()
        self.admin = user_token("Admin", "admin@test.com", "admin")
        self.college = create_college(self.admin)
        self.owner = user_token("Owner", "owner@test.com")
        client.post(f"/api/admin/users/{user_id('owner@test.com')}/role", json={"role": "organizer", "college_ids": [self.college]}, headers=auth(self.admin))
        self.fest = client.post("/api/fests/", json={"slug": "mood-indigo", "name": "Mood Indigo", "college_id": self.college}, headers=auth(self.owner)).json()

    def claim(self, name, slug="mood-indigo", token=None):
        return client.put(f"/api/short-links/fests/{slug}", json={"name": name}, headers=auth(token or self.owner))

    def go_live(self, slug="mood-indigo"):
        db = TestingSessionLocal()
        f = db.query(models.Fest).filter(models.Fest.slug == slug).first()
        f.status, f.review_status = models.FestStatusEnum.live, "approved"
        db.commit(); db.close()


class TestAvailability(Setup):
    def check(self, name, **kw):
        return client.get("/api/short-links/check", params={"name": name, **kw}, headers=auth(self.owner)).json()

    def test_free_names_are_available(self):
        assert self.check("mood-indigo") == {"name": "mood-indigo", "available": True, "reason": None}

    def test_site_and_brand_names_are_reserved(self):
        for name in ("admin", "login", "dashboard", "fests", "events", "support", "hiveout"):
            assert self.check(name)["reason"] == "reserved", name

    def test_bad_formats_are_invalid(self):
        for name in ("ab", "Has Space", "-lead", "trail-", "double--hyphen", "x" * 41, "under_score"):
            assert self.check(name)["reason"] == "invalid", name

    def test_names_are_not_case_sensitive(self):
        assert self.check("MOOD-Indigo")["name"] == "mood-indigo"

    def test_only_organisers_can_check(self):
        member = user_token("Member", "member@test.com")
        assert client.get("/api/short-links/check", params={"name": "abc"}, headers=auth(member)).status_code == 403
        assert client.get("/api/short-links/check", params={"name": "abc"}).status_code == 401

    def test_checking_is_rate_limited(self):
        codes = [client.get("/api/short-links/check", params={"name": "abc"}, headers=auth(self.owner)).status_code for _ in range(45)]
        assert codes[0] == 200 and codes[-1] == 429


class TestClaiming(Setup):
    def test_claim_and_read_back(self):
        r = self.claim("mood-indigo")
        assert r.status_code == 200 and r.json()["path"] == "/mood-indigo" and r.json()["target_path"] == "/fests/mood-indigo"
        assert client.get("/api/short-links/fests/mood-indigo", headers=auth(self.owner)).json()["name"] == "mood-indigo"

    def test_a_taken_name_is_refused_for_everyone_else(self):
        self.claim("mood-indigo")
        other = user_token("Other", "other@test.com")
        client.post(f"/api/admin/users/{user_id('other@test.com')}/role", json={"role": "organizer", "college_ids": [self.college]}, headers=auth(self.admin))
        client.post("/api/fests/", json={"slug": "other-fest", "name": "Other", "college_id": self.college}, headers=auth(other))
        r = self.claim("mood-indigo", "other-fest", other)
        assert r.status_code == 409
        assert client.get("/api/short-links/check", params={"name": "mood-indigo"}, headers=auth(other)).json()["reason"] == "taken"

    def test_blocked_and_invalid_names_cannot_be_claimed(self):
        assert self.claim("admin").status_code == 400
        assert self.claim("no").status_code == 400

    def test_a_fest_holds_one_name_and_renaming_frees_the_old_one(self):
        self.claim("first-name")
        assert self.claim("second-name").json()["name"] == "second-name"
        assert client.get("/api/short-links/check", params={"name": "first-name"}, headers=auth(self.owner)).json()["available"] is True

    def test_giving_the_name_up_frees_it(self):
        self.claim("mood-indigo")
        assert client.delete("/api/short-links/fests/mood-indigo", headers=auth(self.owner)).json()["name"] is None
        assert client.get("/api/short-links/check", params={"name": "mood-indigo"}, headers=auth(self.owner)).json()["available"] is True

    def test_only_the_fests_staff_may_change_it(self):
        other = user_token("Other", "other@test.com", "organizer")
        assert self.claim("abc-fest", token=other).status_code == 404
        member = user_token("Member", "member@test.com")
        assert self.claim("abc-fest", token=member).status_code == 404
        self.claim("abc-fest")
        assert client.delete("/api/short-links/fests/mood-indigo", headers=auth(other)).status_code == 404

    def test_an_admin_can_take_a_name_back(self):
        self.claim("mood-indigo")
        assert client.delete("/api/admin/short-links/mood-indigo", headers=auth(self.admin)).status_code == 200
        assert client.delete("/api/admin/short-links/mood-indigo", headers=auth(self.admin)).status_code == 404
        assert client.delete("/api/admin/short-links/mood-indigo", headers=auth(self.owner)).status_code == 403

    def test_the_review_screen_shows_the_name(self):
        self.claim("mood-indigo")
        r = client.get("/api/admin/fests/mood-indigo", headers=auth(self.admin)).json()
        assert r["short_link"] == "mood-indigo"


class TestResolving(Setup):
    def test_a_live_fest_resolves(self):
        self.claim("mood-indigo"); self.go_live()
        assert client.get("/api/short-links/resolve/Mood-Indigo").json() == {"path": "/fests/mood-indigo"}

    def test_a_draft_fest_reveals_nothing(self):
        self.claim("mood-indigo")
        assert client.get("/api/short-links/resolve/mood-indigo").status_code == 404
        assert client.get("/api/short-links/resolve/never-claimed").status_code == 404


class TestPaidFeature(Setup):
    def test_free_by_default_and_lockable_later(self, monkeypatch):
        assert self.claim("free-for-now").status_code == 200
        monkeypatch.setenv("PAID_FEATURES", "short_links")
        r = self.claim("now-paid")
        assert r.status_code == 402 and "paid plan" in r.json()["detail"]
        assert client.get("/api/short-links/fests/mood-indigo", headers=auth(self.owner)).json()["enabled"] is False
