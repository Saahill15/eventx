"""Admin's user page: full details of one account, and corrections limited to non-security fields."""

import pytest  # noqa: F401

from test_fixes import user_token, user_id  # noqa: F401
from test_full import client, auth, create_college, reset_db  # noqa: F401


class Setup:
    def setup_method(self):
        self.admin = user_token("Admin", "admin@test.com", "admin")
        self.college_id = create_college(self.admin)
        self.member = user_token("Asha", "asha@test.com")
        self.member_id = user_id("asha@test.com")


class TestDetail(Setup):
    def test_detail_has_profile_sign_in_and_student_status(self):
        r = client.get(f"/api/admin/users/{self.member_id}", headers=auth(self.admin))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["email"] == "asha@test.com" and body["role"] == "user" and body["is_active"] is True
        assert body["student"]["verified"] is False
        assert body["active_sessions"] and body["last_seen_at"] is not None
        assert body["recent_sign_ins"] and body["recent_sign_ins"][0]["success"] is True

    def test_only_admins_can_see_it(self):
        assert client.get(f"/api/admin/users/{self.member_id}", headers=auth(self.member)).status_code == 403

    def test_unknown_user(self):
        assert client.get("/api/admin/users/99999", headers=auth(self.admin)).status_code == 404


class TestProfileCorrections(Setup):
    def test_admin_can_correct_profile_fields(self):
        r = client.patch(f"/api/admin/users/{self.member_id}/profile", json={"first_name": "Asha", "last_name": "Verma", "phone": "+91 98765 43210", "study_year": 2, "college_id": self.college_id}, headers=auth(self.admin))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["name"] == "Asha Verma" and body["study_year"] == 2 and body["home_college"] == "IIT Bombay"

    def test_security_fields_are_refused(self):
        for field in ({"email": "new@test.com"}, {"password": "whatever123"}, {"role": "admin"}, {"google_sub": "abc"}):
            r = client.patch(f"/api/admin/users/{self.member_id}/profile", json=field, headers=auth(self.admin))
            assert r.status_code == 422, field
        assert client.get(f"/api/admin/users/{self.member_id}", headers=auth(self.admin)).json()["email"] == "asha@test.com"

    def test_phone_must_be_unique(self):
        user_token("Other", "other@test.com")
        client.patch(f"/api/admin/users/{user_id('other@test.com')}/profile", json={"phone": "+91 11111 22222"}, headers=auth(self.admin))
        r = client.patch(f"/api/admin/users/{self.member_id}/profile", json={"phone": "+91 11111 22222"}, headers=auth(self.admin))
        assert r.status_code == 400 and "already in use" in r.json()["detail"]

    def test_members_cannot_use_the_admin_edit(self):
        assert client.patch(f"/api/admin/users/{self.member_id}/profile", json={"study_year": 3}, headers=auth(self.member)).status_code == 403
