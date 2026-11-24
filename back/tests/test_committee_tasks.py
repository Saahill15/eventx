"""Committee tasks: who does what by when."""

from datetime import date, timedelta

from test_fixes import user_token, user_id  # noqa: F401
from test_full import client, auth, reset_db, TestingSessionLocal  # noqa: F401
from test_committee_structure import Committee, join, member_id
from app.routes import fest_tasks


def iso(days):
    return (date.today() + timedelta(days=days)).isoformat()


class Tasks(Committee):
    def setup_method(self):
        super().setup_method()
        self.other_vol = user_token("Other", "other@test.com")
        self.other_mid = join("fest-one", "other@test.com", "volunteer")

    def add(self, title="Print posters", token=None, slug="fest-one", **extra):
        return client.post(f"/api/fests/{slug}/tasks", json={"title": title, **extra}, headers=auth(token or self.owner))

    def patch(self, task_id, body, token=None, slug="fest-one"):
        return client.patch(f"/api/fests/{slug}/tasks/{task_id}", json=body, headers=auth(token or self.owner))

    def lst(self, token=None, slug="fest-one", query=""):
        r = client.get(f"/api/fests/{slug}/tasks{query}", headers=auth(token or self.owner))
        assert r.status_code == 200, r.text
        return r.json()


class TestAddingTasks(Tasks):
    def test_staff_can_add_a_task(self):
        for token in (self.owner, self.core, self.admin):
            r = self.add(token=token)
            assert r.status_code == 201 and r.json()["status"] == "todo" and r.json()["completed_at"] is None

    def test_volunteers_and_strangers_cannot(self):
        assert self.add(token=self.vol).status_code == 403
        assert self.add(token=self.student).status_code == 403

    def test_a_task_carries_everything_it_was_given(self):
        tid = client.post("/api/fests/fest-one/org/teams", json={"name": "PR"}, headers=auth(self.owner)).json()["id"]
        r = self.add("Design the poster", description="A3, two colours", due_date=iso(5), assignee_member_id=self.vol_mid, committee_team_id=tid)
        body = r.json()
        assert body["description"] == "A3, two colours" and body["due_date"] == iso(5) and body["assignee_name"].startswith("Vol") and body["team_name"] == "PR"
        assert body["created_by_name"].startswith("Owner")

    def test_a_blank_or_overlong_title_is_refused(self):
        assert self.add("   ").status_code == 422
        assert self.add("x" * 201).status_code == 422

    def test_the_assignee_must_be_on_this_committee(self):
        self.start("fest-two")
        other = member_id("fest-two", "owner@test.com")
        assert self.add(assignee_member_id=other).status_code == 400
        assert self.add(assignee_member_id=99999).status_code == 400

    def test_the_team_must_belong_to_this_fest(self):
        self.start("fest-two")
        other = client.post("/api/fests/fest-two/org/teams", json={"name": "Secret"}, headers=auth(self.owner)).json()["id"]
        assert self.add(committee_team_id=other).status_code == 400

    def test_a_task_can_start_already_done(self):
        r = self.add(status="done")
        assert r.json()["completed_at"] is not None

    def test_a_fest_is_limited_in_tasks(self, monkeypatch):
        monkeypatch.setattr(fest_tasks, "MAX_TASKS", 2)
        assert self.add("a").status_code == 201 and self.add("b").status_code == 201
        assert self.add("c").status_code == 400


class TestSeeingTasks(Tasks):
    def test_every_committee_member_can_see_tasks_but_strangers_cannot(self):
        self.add()
        for token in (self.owner, self.core, self.vol, self.admin):
            assert len(self.lst(token)) == 1
        assert client.get("/api/fests/fest-one/tasks", headers=auth(self.student)).status_code == 403

    def test_tasks_of_another_fest_never_show(self):
        self.start("fest-two")
        self.add(slug="fest-two")
        assert self.lst() == []

    def test_due_soonest_first_and_undated_last(self):
        self.add("later", due_date=iso(9))
        self.add("undated")
        self.add("soon", due_date=iso(1))
        assert [t["title"] for t in self.lst()] == ["soon", "later", "undated"]

    def test_filter_by_status(self):
        a = self.add("a").json()["id"]
        self.add("b")
        self.patch(a, {"status": "doing"})
        assert [t["title"] for t in self.lst(query="?status=doing")] == ["a"]
        assert len(self.lst(query="?status=todo")) == 1

    def test_filter_by_team(self):
        tid = client.post("/api/fests/fest-one/org/teams", json={"name": "PR"}, headers=auth(self.owner)).json()["id"]
        self.add("in team", committee_team_id=tid)
        self.add("no team")
        assert [t["title"] for t in self.lst(query=f"?team_id={tid}")] == ["in team"]

    def test_filter_to_my_tasks(self):
        self.add("mine", assignee_member_id=self.vol_mid)
        self.add("theirs", assignee_member_id=self.core_mid)
        assert [t["title"] for t in self.lst(token=self.vol, query="?assignee=me")] == ["mine"]
        assert [t["title"] for t in self.lst(query=f"?assignee={self.core_mid}")] == ["theirs"]

    def test_filter_to_overdue_tasks(self):
        self.add("late", due_date=iso(-2))
        self.add("today", due_date=iso(0))
        done = self.add("late but done", due_date=iso(-3)).json()["id"]
        self.patch(done, {"status": "done"})
        assert [t["title"] for t in self.lst(query="?overdue=true")] == ["late"]
        assert next(t for t in self.lst() if t["title"] == "late")["overdue"] is True
        assert next(t for t in self.lst() if t["title"] == "today")["overdue"] is False

    def test_a_bad_filter_is_refused(self):
        assert client.get("/api/fests/fest-one/tasks?status=maybe", headers=auth(self.owner)).status_code == 422
        assert client.get("/api/fests/fest-one/tasks?assignee=everyone", headers=auth(self.owner)).status_code == 422


class TestChangingTasks(Tasks):
    def test_status_moves_and_completion_time_follows(self):
        tid = self.add().json()["id"]
        done = self.patch(tid, {"status": "done"}).json()
        assert done["status"] == "done" and done["completed_at"] is not None
        back = self.patch(tid, {"status": "doing"}).json()
        assert back["status"] == "doing" and back["completed_at"] is None

    def test_staff_can_change_anything(self):
        tid = self.add().json()["id"]
        r = self.patch(tid, {"title": "New title", "description": "More", "due_date": iso(3), "assignee_member_id": self.vol_mid}, token=self.core)
        assert r.status_code == 200 and r.json()["title"] == "New title" and r.json()["assignee_name"].startswith("Vol")

    def test_null_clears_the_optional_fields(self):
        tid = self.add(due_date=iso(3), assignee_member_id=self.vol_mid, description="x").json()["id"]
        r = self.patch(tid, {"due_date": None, "assignee_member_id": None, "description": None}).json()
        assert r["due_date"] is None and r["assignee_member_id"] is None and r["description"] is None

    def test_only_what_is_sent_changes(self):
        tid = self.add(due_date=iso(3), assignee_member_id=self.vol_mid).json()["id"]
        r = self.patch(tid, {"title": "Renamed"}).json()
        assert r["due_date"] == iso(3) and r["assignee_member_id"] == self.vol_mid

    def test_a_blank_title_is_refused(self):
        tid = self.add().json()["id"]
        assert self.patch(tid, {"title": "   "}).status_code in (400, 422)

    def test_the_assignee_can_move_their_own_task(self):
        tid = self.add(assignee_member_id=self.vol_mid).json()["id"]
        assert self.patch(tid, {"status": "doing"}, token=self.vol).status_code == 200

    def test_the_assignee_cannot_change_its_details(self):
        tid = self.add(assignee_member_id=self.vol_mid).json()["id"]
        assert self.patch(tid, {"title": "Mine now"}, token=self.vol).status_code == 403
        assert self.patch(tid, {"status": "done", "due_date": iso(30)}, token=self.vol).status_code == 403

    def test_someone_else_cannot_touch_a_task_that_is_not_theirs(self):
        tid = self.add(assignee_member_id=self.vol_mid).json()["id"]
        assert self.patch(tid, {"status": "done"}, token=self.other_vol).status_code == 403
        assert self.patch(tid, {"status": "done"}, token=self.student).status_code == 403

    def test_an_unassigned_task_cannot_be_moved_by_a_volunteer(self):
        tid = self.add().json()["id"]
        assert self.patch(tid, {"status": "done"}, token=self.vol).status_code == 403

    def test_another_fests_task_is_not_found(self):
        self.start("fest-two")
        other = self.add(slug="fest-two").json()["id"]
        assert self.patch(other, {"status": "done"}).status_code == 404

    def test_the_new_assignee_must_be_on_the_committee(self):
        self.start("fest-two")
        stranger = member_id("fest-two", "owner@test.com")
        tid = self.add().json()["id"]
        assert self.patch(tid, {"assignee_member_id": stranger}).status_code == 400


class TestDeletingAndTidying(Tasks):
    def test_staff_can_delete_and_volunteers_cannot(self):
        tid = self.add().json()["id"]
        assert client.delete(f"/api/fests/fest-one/tasks/{tid}", headers=auth(self.vol)).status_code == 403
        assert client.delete(f"/api/fests/fest-one/tasks/{tid}", headers=auth(self.core)).status_code == 204
        assert self.lst() == []

    def test_another_fests_task_cannot_be_deleted(self):
        self.start("fest-two")
        other = self.add(slug="fest-two").json()["id"]
        assert client.delete(f"/api/fests/fest-one/tasks/{other}", headers=auth(self.owner)).status_code == 404

    def test_removing_a_person_unassigns_their_tasks(self):
        self.add("work", assignee_member_id=self.vol_mid)
        assert client.delete(f"/api/fests/fest-one/members/{user_id('vol@test.com')}", headers=auth(self.owner)).status_code == 204
        task = self.lst()[0]
        assert task["assignee_member_id"] is None and task["assignee_name"] is None

    def test_deleting_a_team_clears_it_from_its_tasks(self):
        tid = client.post("/api/fests/fest-one/org/teams", json={"name": "PR"}, headers=auth(self.owner)).json()["id"]
        self.add("work", committee_team_id=tid)
        client.delete(f"/api/fests/fest-one/org/teams/{tid}", headers=auth(self.owner))
        assert self.lst()[0]["committee_team_id"] is None
