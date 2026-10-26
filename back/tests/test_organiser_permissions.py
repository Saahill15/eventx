"""Fest hosting and city events are switched on separately for each organiser. Being an organiser alone grants neither."""

import pytest

from test_fixes import user_token, user_id  # noqa: F401
from test_full import client, auth, create_college, reset_db, TestingSessionLocal  # noqa: F401
from app import models

CITY = {"event_type": "city", "title": "Open Mic", "date": "2026-12-01T10:00:00"}


def fest_payload(college_id, slug="fest-one"):
    return {"slug": slug, "name": "Fest One", "college_id": college_id}


class Setup:
    def setup_method(self):
        self.admin = user_token("Admin", "admin@test.com", "admin")
        self.college_id = create_college(self.admin)
        self.org = user_token("Org", "org@test.com")
        self.org_id = user_id("org@test.com")

    def promote(self, **body):
        r = client.post(f"/api/admin/users/{self.org_id}/role", json={"role": "organizer", **body}, headers=auth(self.admin))
        assert r.status_code == 200, r.text
        return r.json()

    def set_permissions(self, fests, city):
        r = client.put(f"/api/admin/users/{self.org_id}/permissions", json={"can_host_fests": fests, "can_host_city_events": city}, headers=auth(self.admin))
        assert r.status_code == 200, r.text
        return r.json()

    def create_city(self):
        return client.post("/api/events/", json=CITY, headers=auth(self.org))

    def create_fest(self):
        return client.post("/api/fests/", json=fest_payload(self.college_id), headers=auth(self.org))


class TestPromotion(Setup):
    def test_default_promotion_gives_fests_only(self):
        out = self.promote(college_ids=[self.college_id])
        assert out["can_host_fests"] is True
        assert out["can_host_city_events"] is False
        assert self.create_fest().status_code == 201
        assert self.create_city().status_code == 403

    def test_city_only_promotion_needs_no_college(self):
        out = self.promote(can_host_fests=False, can_host_city_events=True)
        assert out["can_host_fests"] is False and out["can_host_city_events"] is True
        assert out["college_ids"] == []
        assert self.create_city().status_code == 200
        assert self.create_fest().status_code == 403

    def test_fest_promotion_still_needs_a_college(self):
        r = client.post(f"/api/admin/users/{self.org_id}/role", json={"role": "organizer", "can_host_fests": True}, headers=auth(self.admin))
        assert r.status_code == 400

    def test_removing_organiser_clears_both_permissions(self):
        self.promote(college_ids=[self.college_id], can_host_city_events=True)
        out = client.post(f"/api/admin/users/{self.org_id}/role", json={"role": "user"}, headers=auth(self.admin)).json()
        assert out["can_host_fests"] is False and out["can_host_city_events"] is False


class TestToggles(Setup):
    def test_admin_can_switch_city_events_on_and_off(self):
        self.promote(college_ids=[self.college_id])
        assert self.create_city().status_code == 403

        self.set_permissions(fests=True, city=True)
        assert self.create_city().status_code == 200

        self.set_permissions(fests=True, city=False)
        assert self.create_city().status_code == 403
        assert client.get("/api/events/mine", headers=auth(self.org)).json() == []

    def test_switching_fests_off_blocks_fest_work(self):
        self.promote(college_ids=[self.college_id])
        fest = self.create_fest()
        assert fest.status_code == 201
        slug = fest.json()["slug"]

        self.set_permissions(fests=False, city=False)
        assert client.patch(f"/api/fests/{slug}", json={"tagline": "Changed"}, headers=auth(self.org)).status_code == 403
        assert self.create_fest().status_code == 403

        self.set_permissions(fests=True, city=False)
        assert client.patch(f"/api/fests/{slug}", json={"tagline": "Changed"}, headers=auth(self.org)).status_code == 200

    def test_toggles_only_apply_to_organisers(self):
        r = client.put(f"/api/admin/users/{self.org_id}/permissions", json={"can_host_fests": True, "can_host_city_events": True}, headers=auth(self.admin))
        assert r.status_code == 404

    def test_admin_is_not_affected_by_flags(self):
        db = TestingSessionLocal()
        admin_row = db.query(models.User).filter(models.User.email == "admin@test.com").first()
        admin_row.can_host_city_events = False
        db.commit()
        db.close()
        assert client.post("/api/events/", json=CITY, headers=auth(self.admin)).status_code == 200
