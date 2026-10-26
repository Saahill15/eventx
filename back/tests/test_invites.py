"""Team invitations: a person joins a fest team only after they accept, and only if they are a verified student."""

from datetime import datetime, timedelta

import pytest

from test_fixes import user_token, user_id  # noqa: F401
from test_full import client, auth, create_college, create_fest, reset_db, verify_student, TestingSessionLocal, join_team  # noqa: F401
from app import models


class Setup:
    def setup_method(self):
        self.admin = user_token("Admin", "admin@test.com", "admin")
        self.college_id = create_college(self.admin)
        self.owner = user_token("Owner", "owner@test.com", "organizer")
        self.fest = create_fest(self.owner, self.college_id)
        self.slug = self.fest["slug"]
        self.student = user_token("Asha", "asha@test.com")
        self.other = user_token("Other", "other@test.com")

    def invite(self, email, role="volunteer", token=None):
        return client.post(f"/api/fests/{self.slug}/members", json={"email": email, "role": role}, headers=auth(token or self.owner))

    def members(self):
        return {m["user_email"] for m in client.get(f"/api/fests/{self.slug}/members", headers=auth(self.owner)).json()}

    def notices(self, token):
        return client.get("/api/users/me/account-notices", headers=auth(token)).json()


class TestWhoCanBeInvited(Setup):
    def test_unverified_person_can_be_invited_but_must_verify_to_accept(self):
        r = self.invite("asha@test.com")
        assert r.status_code == 201 and r.json()["status"] == "pending"
        invite_id = r.json()["id"]
        r = client.post(f"/api/fest-invites/{invite_id}/accept", headers=auth(self.student))
        assert r.status_code == 403 and "verified students" in r.json()["detail"]
        # the invitation is still open, so they can accept once they have verified
        assert client.get(f"/api/fests/{self.slug}/invites", headers=auth(self.owner)).json()[0]["id"] == invite_id
        verify_student("asha@test.com")
        assert client.post(f"/api/fest-invites/{invite_id}/accept", headers=auth(self.student)).status_code == 200
        assert "asha@test.com" in self.members()

    def test_admin_accounts_cannot_be_added_to_a_team(self):
        user_token("Root", "root@test.com", "admin")
        r = self.invite("root@test.com")
        assert r.status_code == 400 and r.json()["detail"] == "You can't add this user to a fest team."
        assert "root@test.com" not in self.members()
        assert client.get(f"/api/fests/{self.slug}/invites", headers=auth(self.owner)).json() == []

    def test_organiser_can_be_invited(self):
        user_token("Org", "org2@test.com", "organizer")
        assert self.invite("org2@test.com").status_code == 201


class TestAcceptFlow(Setup):
    def test_invite_does_not_add_member_until_accepted(self):
        verify_student("asha@test.com")
        invite_id = self.invite("asha@test.com").json()["id"]
        assert "asha@test.com" not in self.members()
        pending = client.get(f"/api/fests/{self.slug}/invites", headers=auth(self.owner)).json()
        assert [p["id"] for p in pending] == [invite_id]

        notes = self.notices(self.student)
        assert len(notes) == 1 and notes[0]["kind"] == "fest_invite" and notes[0]["invite_status"] == "pending"
        assert self.fest["name"] in notes[0]["title"]
        assert client.get("/api/users/me/account-notices/unread-count", headers=auth(self.student)).json() == {"count": 1}

    def test_accepting_makes_them_a_member_with_the_invited_role(self):
        verify_student("asha@test.com")
        invite_id = self.invite("asha@test.com", role="core").json()["id"]
        r = client.post(f"/api/fest-invites/{invite_id}/accept", headers=auth(self.student))
        assert r.status_code == 200 and r.json()["status"] == "accepted"
        assert "asha@test.com" in self.members()
        rows = client.get("/api/fests/mine", headers=auth(self.student)).json()
        assert rows[0]["my_role"] == "core"
        # the invitation notice is now read, and the organiser hears the answer
        assert self.notices(self.student)[0]["read_at"] is not None
        owner_notes = self.notices(self.owner)
        assert owner_notes[0]["kind"] == "fest_invite_answer" and "joined" in owner_notes[0]["title"]

    def test_declining_leaves_the_team_alone(self):
        verify_student("asha@test.com")
        invite_id = self.invite("asha@test.com").json()["id"]
        r = client.post(f"/api/fest-invites/{invite_id}/decline", headers=auth(self.student))
        assert r.status_code == 200 and r.json()["status"] == "declined"
        assert "asha@test.com" not in self.members()
        assert client.post(f"/api/fest-invites/{invite_id}/accept", headers=auth(self.student)).status_code == 400

    def test_only_the_invited_person_can_answer(self):
        verify_student("asha@test.com")
        invite_id = self.invite("asha@test.com").json()["id"]
        assert client.post(f"/api/fest-invites/{invite_id}/accept", headers=auth(self.other)).status_code == 404
        assert "asha@test.com" not in self.members()

    def test_withdrawn_invitation_cannot_be_accepted(self):
        verify_student("asha@test.com")
        invite_id = self.invite("asha@test.com").json()["id"]
        r = client.delete(f"/api/fests/{self.slug}/invites/{invite_id}", headers=auth(self.owner))
        assert r.status_code == 200 and r.json()["status"] == "cancelled"
        assert client.post(f"/api/fest-invites/{invite_id}/accept", headers=auth(self.student)).status_code == 400
        assert client.get(f"/api/fests/{self.slug}/invites", headers=auth(self.owner)).json() == []

    def test_inviting_again_updates_the_open_invitation(self):
        verify_student("asha@test.com")
        first = self.invite("asha@test.com", role="volunteer").json()["id"]
        second = self.invite("asha@test.com", role="core").json()
        assert second["id"] == first and second["role"] == "core"

    def test_verification_that_runs_out_blocks_accepting(self):
        verify_student("asha@test.com")
        invite_id = self.invite("asha@test.com").json()["id"]
        db = TestingSessionLocal()
        db.query(models.User).filter(models.User.email == "asha@test.com").update({"student_verified_until": datetime.utcnow() - timedelta(days=1)})
        db.commit()
        db.close()
        r = client.post(f"/api/fest-invites/{invite_id}/accept", headers=auth(self.student))
        assert r.status_code == 403 and "verified students" in r.json()["detail"]
        assert "asha@test.com" not in self.members()

    def test_non_staff_cannot_see_or_withdraw_invitations(self):
        verify_student("asha@test.com")
        invite_id = self.invite("asha@test.com").json()["id"]
        assert client.get(f"/api/fests/{self.slug}/invites", headers=auth(self.other)).status_code == 403
        assert client.delete(f"/api/fests/{self.slug}/invites/{invite_id}", headers=auth(self.other)).status_code == 403


class TestNoticeFeed(Setup):
    def test_read_one_and_read_all(self):
        verify_student("asha@test.com")
        self.invite("asha@test.com")
        self.invite("asha@test.com", role="volunteer")  # same open invitation, so still one notice to read
        db = TestingSessionLocal()
        # a second notice so read-all has more than one row to clear
        db.add(models.AccountNotice(user_id=user_id("asha@test.com"), kind="fest_invite", title="Hello", body="Test", created_at=datetime.utcnow()))
        db.commit()
        db.close()
        notes = self.notices(self.student)
        assert client.get("/api/users/me/account-notices/unread-count", headers=auth(self.student)).json()["count"] == 2

        first = client.post(f"/api/users/me/account-notices/{notes[0]['id']}/read", headers=auth(self.student))
        assert first.status_code == 200 and first.json()["read_at"] is not None
        assert client.get("/api/users/me/account-notices/unread-count", headers=auth(self.student)).json()["count"] == 1

        assert client.post("/api/users/me/account-notices/read-all", headers=auth(self.student)).json() == {"count": 0}
        assert client.get("/api/users/me/account-notices/unread-count", headers=auth(self.student)).json()["count"] == 0

    def test_notices_are_private(self):
        verify_student("asha@test.com")
        self.invite("asha@test.com")
        notice_id = self.notices(self.student)[0]["id"]
        assert client.post(f"/api/users/me/account-notices/{notice_id}/read", headers=auth(self.other)).status_code == 404
        assert self.notices(self.other) == []


def test_join_team_helper_makes_a_working_member():
    """The shared helper used by the older tests must still produce a real member."""
    admin = user_token("Admin", "admin@test.com", "admin")
    college = create_college(admin)
    owner = user_token("Owner", "owner@test.com", "organizer")
    fest = create_fest(owner, college)
    student = user_token("Asha", "asha@test.com")
    join_team(owner, fest["slug"], "asha@test.com", "volunteer", student)
    emails = {m["user_email"] for m in client.get(f"/api/fests/{fest['slug']}/members", headers=auth(owner)).json()}
    assert "asha@test.com" in emails
