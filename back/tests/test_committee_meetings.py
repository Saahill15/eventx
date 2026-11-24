"""Committee meetings: agenda, invitations, attendance, minutes and action items."""

from datetime import datetime, timedelta

from test_fixes import user_id  # noqa: F401
from test_full import client, auth, reset_db, TestingSessionLocal  # noqa: F401
from test_committee_structure import member_id
from test_committee_tasks import Tasks
from app import models
from app.routes import fest_meetings


def when(days):
    return (datetime.now() + timedelta(days=days)).replace(microsecond=0).isoformat()


def notices_for(email, kind="meeting"):
    db = TestingSessionLocal()
    uid = db.query(models.User).filter(models.User.email == email).first().id
    rows = db.query(models.AccountNotice).filter(models.AccountNotice.user_id == uid, models.AccountNotice.kind == kind).order_by(models.AccountNotice.id).all()
    out = [(n.title, n.body) for n in rows]
    db.close()
    return out


class Meetings(Tasks):
    def schedule(self, title="Kick-off", token=None, slug="fest-one", starts=None, **extra):
        return client.post(f"/api/fests/{slug}/meetings", json={"title": title, "starts_at": starts or when(2), **extra}, headers=auth(token or self.owner))

    def edit(self, mid, body, token=None, slug="fest-one"):
        return client.patch(f"/api/fests/{slug}/meetings/{mid}", json=body, headers=auth(token or self.owner))

    def meetings(self, token=None, slug="fest-one", query=""):
        r = client.get(f"/api/fests/{slug}/meetings{query}", headers=auth(token or self.owner))
        assert r.status_code == 200, r.text
        return r.json()


class TestScheduling(Meetings):
    def test_staff_can_schedule_a_meeting(self):
        for token in (self.owner, self.core, self.admin):
            assert self.schedule(token=token).status_code == 201

    def test_volunteers_and_strangers_cannot(self):
        assert self.schedule(token=self.vol).status_code == 403
        assert self.schedule(token=self.student).status_code == 403

    def test_the_whole_committee_is_invited_by_default(self):
        body = self.schedule(location="Room 4", agenda="Budget, posters").json()
        assert body["invited_count"] == 4 and body["location"] == "Room 4" and body["agenda"] == "Budget, posters"
        assert len(body["attendees"]) == 4 and all(a["attended"] is False for a in body["attendees"])

    def test_only_chosen_people_can_be_invited(self):
        body = self.schedule(member_ids=[self.vol_mid, self.core_mid]).json()
        assert sorted(a["member_id"] for a in body["attendees"]) == sorted([self.vol_mid, self.core_mid])

    def test_an_empty_list_invites_nobody(self):
        assert self.schedule(member_ids=[]).json()["invited_count"] == 0

    def test_someone_from_another_fest_cannot_be_invited(self):
        self.start("fest-two")
        stranger = member_id("fest-two", "owner@test.com")
        assert self.schedule(member_ids=[stranger]).status_code == 400
        assert self.schedule(member_ids=[99999]).status_code == 400

    def test_a_blank_title_or_a_missing_time_is_refused(self):
        assert self.schedule("   ").status_code == 422
        assert client.post("/api/fests/fest-one/meetings", json={"title": "No time"}, headers=auth(self.owner)).status_code == 422

    def test_duplicate_invitees_are_counted_once(self):
        assert self.schedule(member_ids=[self.vol_mid, self.vol_mid]).json()["invited_count"] == 1

    def test_a_fest_is_limited_in_meetings(self, monkeypatch):
        monkeypatch.setattr(fest_meetings, "MAX_MEETINGS", 1)
        assert self.schedule("a").status_code == 201
        assert self.schedule("b").status_code == 400


class TestInvitations(Meetings):
    def test_the_people_invited_are_told_but_not_the_person_who_scheduled(self):
        self.schedule("Kick-off", location="Room 4")
        assert len(notices_for("vol@test.com")) == 1 and len(notices_for("core@test.com")) == 1
        assert notices_for("owner@test.com") == []
        title, body = notices_for("vol@test.com")[0]
        assert title == "New meeting: Kick-off" and "Room 4" in body and "Fest One" in body

    def test_people_who_were_not_invited_hear_nothing(self):
        self.schedule(member_ids=[self.vol_mid])
        assert notices_for("core@test.com") == [] and notices_for("other@test.com") == []

    def test_changing_the_time_tells_the_invitees(self):
        mid = self.schedule().json()["id"]
        self.edit(mid, {"starts_at": when(5)})
        assert [t for t, _ in notices_for("vol@test.com")] == ["New meeting: Kick-off", "Meeting changed: Kick-off"]

    def test_changing_the_place_tells_them_too(self):
        mid = self.schedule(location="Room 4").json()["id"]
        self.edit(mid, {"location": "Room 9"})
        assert "Meeting changed: Kick-off" in [t for t, _ in notices_for("vol@test.com")]

    def test_editing_the_agenda_or_minutes_does_not_send_notices(self):
        mid = self.schedule().json()["id"]
        self.edit(mid, {"agenda": "New agenda", "minutes": "We agreed on X"})
        assert len(notices_for("vol@test.com")) == 1

    def test_sending_the_same_time_again_is_not_a_change(self):
        start = when(2)
        mid = self.schedule(starts=start).json()["id"]
        self.edit(mid, {"starts_at": start})
        assert len(notices_for("vol@test.com")) == 1

    def test_a_newly_invited_person_is_told_and_others_are_not_told_twice(self):
        mid = self.schedule(member_ids=[self.vol_mid]).json()["id"]
        self.edit(mid, {"member_ids": [self.vol_mid, self.core_mid]})
        assert len(notices_for("core@test.com")) == 1 and len(notices_for("vol@test.com")) == 1

    def test_cancelling_a_future_meeting_tells_the_invitees(self):
        mid = self.schedule().json()["id"]
        client.delete(f"/api/fests/fest-one/meetings/{mid}", headers=auth(self.owner))
        assert "Meeting cancelled: Kick-off" in [t for t, _ in notices_for("vol@test.com")]

    def test_deleting_a_past_meeting_sends_no_notice(self):
        mid = self.schedule(starts=when(-3)).json()["id"]
        before = len(notices_for("vol@test.com"))
        client.delete(f"/api/fests/fest-one/meetings/{mid}", headers=auth(self.owner))
        assert len(notices_for("vol@test.com")) == before


class TestSeeingMeetings(Meetings):
    def test_upcoming_and_past_are_separate_and_ordered(self):
        self.schedule("later", starts=when(9))
        self.schedule("soon", starts=when(1))
        self.schedule("last week", starts=when(-7))
        self.schedule("yesterday", starts=when(-1))
        assert [m["title"] for m in self.meetings()] == ["soon", "later"]
        assert [m["title"] for m in self.meetings(query="?when=past")] == ["yesterday", "last week"]

    def test_every_committee_member_can_see_them_but_strangers_cannot(self):
        self.schedule()
        for token in (self.owner, self.core, self.vol, self.admin):
            assert len(self.meetings(token)) == 1
        assert client.get("/api/fests/fest-one/meetings", headers=auth(self.student)).status_code == 403
        mid = self.meetings()[0]["id"]
        assert client.get(f"/api/fests/fest-one/meetings/{mid}", headers=auth(self.student)).status_code == 403

    def test_another_fests_meetings_never_show(self):
        self.start("fest-two")
        self.schedule(slug="fest-two")
        assert self.meetings() == []
        other = client.get("/api/fests/fest-two/meetings", headers=auth(self.owner)).json()[0]["id"]
        assert client.get(f"/api/fests/fest-one/meetings/{other}", headers=auth(self.owner)).status_code == 404

    def test_a_bad_filter_is_refused(self):
        assert client.get("/api/fests/fest-one/meetings?when=never", headers=auth(self.owner)).status_code == 422


class TestChangingMeetings(Meetings):
    def test_staff_can_change_the_details(self):
        mid = self.schedule().json()["id"]
        r = self.edit(mid, {"title": "Budget meet", "location": "Library", "agenda": "Numbers", "minutes": "Agreed to cap at 2 lakh"}, token=self.core)
        body = r.json()
        assert body["title"] == "Budget meet" and body["location"] == "Library" and body["minutes"] == "Agreed to cap at 2 lakh"

    def test_null_clears_the_optional_fields(self):
        mid = self.schedule(location="Room 4", agenda="x").json()["id"]
        body = self.edit(mid, {"location": None, "agenda": None}).json()
        assert body["location"] is None and body["agenda"] is None

    def test_volunteers_cannot_change_anything(self):
        mid = self.schedule().json()["id"]
        assert self.edit(mid, {"minutes": "x"}, token=self.vol).status_code == 403

    def test_a_blank_title_is_refused(self):
        mid = self.schedule().json()["id"]
        assert self.edit(mid, {"title": "   "}).status_code in (400, 422)

    def test_attendance_survives_a_change_to_the_invitees(self):
        mid = self.schedule().json()["id"]
        client.put(f"/api/fests/fest-one/meetings/{mid}/attendance", json={"attended_member_ids": [self.vol_mid, self.core_mid]}, headers=auth(self.owner))
        body = self.edit(mid, {"member_ids": [self.vol_mid, self.owner_mid]}).json()
        by = {a["member_id"]: a["attended"] for a in body["attendees"]}
        assert by == {self.vol_mid: True, self.owner_mid: False}


class TestAttendance(Meetings):
    def test_staff_record_who_came(self):
        mid = self.schedule().json()["id"]
        r = client.put(f"/api/fests/fest-one/meetings/{mid}/attendance", json={"attended_member_ids": [self.owner_mid, self.vol_mid]}, headers=auth(self.core))
        assert r.status_code == 200 and r.json()["attended_count"] == 2

    def test_recording_again_replaces_the_list(self):
        mid = self.schedule().json()["id"]
        client.put(f"/api/fests/fest-one/meetings/{mid}/attendance", json={"attended_member_ids": [self.vol_mid]}, headers=auth(self.owner))
        r = client.put(f"/api/fests/fest-one/meetings/{mid}/attendance", json={"attended_member_ids": [self.core_mid]}, headers=auth(self.owner))
        assert [a["member_id"] for a in r.json()["attendees"] if a["attended"]] == [self.core_mid]

    def test_only_invited_people_can_be_marked(self):
        mid = self.schedule(member_ids=[self.vol_mid]).json()["id"]
        r = client.put(f"/api/fests/fest-one/meetings/{mid}/attendance", json={"attended_member_ids": [self.core_mid]}, headers=auth(self.owner))
        assert r.status_code == 400

    def test_volunteers_cannot_record_attendance(self):
        mid = self.schedule().json()["id"]
        assert client.put(f"/api/fests/fest-one/meetings/{mid}/attendance", json={"attended_member_ids": []}, headers=auth(self.vol)).status_code == 403


class TestActionItems(Meetings):
    def test_a_task_can_come_out_of_a_meeting(self):
        mid = self.schedule("Budget meet").json()["id"]
        t = self.add("Email the sponsor", meeting_id=mid, assignee_member_id=self.vol_mid)
        assert t.status_code == 201 and t.json()["meeting_id"] == mid and t.json()["meeting_title"] == "Budget meet"
        detail = client.get(f"/api/fests/fest-one/meetings/{mid}", headers=auth(self.owner)).json()
        assert detail["action_count"] == 1 and detail["open_action_count"] == 1 and detail["actions"][0]["title"] == "Email the sponsor"

    def test_finished_action_items_stop_counting_as_open(self):
        mid = self.schedule().json()["id"]
        tid = self.add("Do it", meeting_id=mid).json()["id"]
        self.patch(tid, {"status": "done"})
        detail = client.get(f"/api/fests/fest-one/meetings/{mid}", headers=auth(self.owner)).json()
        assert detail["action_count"] == 1 and detail["open_action_count"] == 0

    def test_the_meeting_must_belong_to_this_fest(self):
        self.start("fest-two")
        other = self.schedule(slug="fest-two").json()["id"]
        assert self.add("x", meeting_id=other).status_code == 400
        tid = self.add("y").json()["id"]
        assert self.patch(tid, {"meeting_id": other}).status_code == 400

    def test_a_task_can_be_attached_to_a_meeting_later(self):
        mid = self.schedule().json()["id"]
        tid = self.add("Loose task").json()["id"]
        assert self.patch(tid, {"meeting_id": mid}).json()["meeting_id"] == mid

    def test_the_list_of_meetings_counts_action_items(self):
        mid = self.schedule().json()["id"]
        self.add("a", meeting_id=mid)
        self.add("b", meeting_id=mid)
        assert self.meetings()[0]["action_count"] == 2

    def test_cancelling_a_meeting_keeps_its_action_items(self):
        mid = self.schedule().json()["id"]
        self.add("Keep me", meeting_id=mid)
        client.delete(f"/api/fests/fest-one/meetings/{mid}", headers=auth(self.owner))
        task = self.lst()[0]
        assert task["title"] == "Keep me" and task["meeting_id"] is None


class TestCancelling(Meetings):
    def test_staff_can_cancel_and_volunteers_cannot(self):
        mid = self.schedule().json()["id"]
        assert client.delete(f"/api/fests/fest-one/meetings/{mid}", headers=auth(self.vol)).status_code == 403
        assert client.delete(f"/api/fests/fest-one/meetings/{mid}", headers=auth(self.core)).status_code == 204
        assert self.meetings() == []

    def test_another_fests_meeting_cannot_be_cancelled(self):
        self.start("fest-two")
        other = self.schedule(slug="fest-two").json()["id"]
        assert client.delete(f"/api/fests/fest-one/meetings/{other}", headers=auth(self.owner)).status_code == 404

    def test_removing_someone_from_the_committee_removes_their_invitations(self):
        mid = self.schedule().json()["id"]
        client.delete(f"/api/fests/fest-one/members/{user_id('vol@test.com')}", headers=auth(self.owner))
        detail = client.get(f"/api/fests/fest-one/meetings/{mid}", headers=auth(self.owner)).json()
        assert detail["invited_count"] == 3 and self.vol_mid not in [a["member_id"] for a in detail["attendees"]]
