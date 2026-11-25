"""The organiser's home page: their fests, what needs them, their tasks and what is coming up."""

from datetime import date, datetime, timedelta

from test_fixes import user_token  # noqa: F401
from test_full import client, auth, reset_db, get_entry_pass, TestingSessionLocal  # noqa: F401
from test_organiser import event_payload
from test_committee_structure import Committee
from app import models


def day(n):
    return (date.today() + timedelta(days=n)).isoformat()


class Home(Committee):
    def home(self, token=None):
        r = client.get("/api/dashboard", headers=auth(token or self.owner))
        assert r.status_code == 200, r.text
        return r.json()

    def fest_card(self, token=None, slug="fest-one"):
        return next(f for f in self.home(token)["fests"] if f["slug"] == slug)

    def event(self, **kw):
        fest = client.get("/api/fests/fest-one/manage", headers=auth(self.owner)).json()
        r = client.post("/api/events/", json=event_payload(fest["id"], **kw), headers=auth(self.owner))
        assert r.status_code == 200, r.text
        return r.json()

    def task(self, **kw):
        r = client.post("/api/fests/fest-one/tasks", json={"title": "Print posters", **kw}, headers=auth(self.owner))
        assert r.status_code == 201, r.text
        return r.json()

    def kinds(self, token=None):
        return [a["kind"] for a in self.home(token)["attention"]]

    def go_live(self):
        self.fill()
        self.event()
        assert self.submit().status_code == 200
        assert client.post("/api/admin/fests/fest-one/approve", headers=auth(self.admin)).status_code == 200
        assert client.patch("/api/fests/fest-one/status", json={"status": "live"}, headers=auth(self.owner)).status_code == 200


class TestYourFests(Home):
    def test_someone_on_no_fest_gets_an_empty_page(self):
        h = self.home(self.student)
        assert h == {"fests": [], "attention": [], "my_tasks": [], "coming_up": []}

    def test_you_see_the_fests_you_are_on_and_your_role(self):
        c = self.fest_card()
        assert c["name"] == "Fest One" and c["my_role"] == "owner" and c["status"] == "draft"
        assert self.fest_card(self.core)["my_role"] == "core" and self.fest_card(self.vol)["my_role"] == "volunteer"

    def test_a_fest_you_are_not_on_is_not_listed(self):
        user_token("Elsewhere", "elsewhere@test.com")
        self.start("fest-two")
        slugs = [f["slug"] for f in self.home(self.owner)["fests"]]
        assert "fest-two" in slugs  # the owner of both
        assert [f["slug"] for f in self.home(self.core)["fests"]] == ["fest-one"]

    def test_an_admin_sees_every_fest(self):
        self.start("fest-two")
        assert {f["slug"] for f in self.home(self.admin)["fests"]} == {"fest-one", "fest-two"}
        assert self.fest_card(self.admin)["my_role"] == "admin"

    def test_dates_and_length_come_with_the_fest(self):
        self.fill(start_date="2026-12-04", end_date="2026-12-06")
        c = self.fest_card()
        assert c["days_count"] == 3 and c["start_date"] == "2026-12-04"

    def test_live_fests_are_listed_first(self):
        self.start("fest-two")
        self.go_live()
        assert [f["slug"] for f in self.home()["fests"]][0] == "fest-one"

    def test_the_numbers_are_only_for_the_director_and_core_team(self):
        c = self.fest_card()
        assert c["registered"] == 0 and c["pending"] == 0 and c["passes_issued"] == 0 and c["events"] == 0
        assert self.fest_card(self.core)["registered"] == 0
        v = self.fest_card(self.vol)
        assert v["registered"] is None and v["pending"] is None and v["passes_issued"] is None and v["setup"] is None


class TestSetupProgress(Home):
    def test_a_new_fest_shows_how_far_along_it_is_and_the_next_step(self):
        s = self.fest_card()["setup"]
        assert s["total"] == 7 and s["done"] < s["total"]
        assert s["next_label"] and s["next_tab"] in ("details", "events", "team")

    def test_finishing_things_moves_the_progress_on(self):
        before = self.fest_card()["setup"]["done"]
        self.fill()
        assert self.fest_card()["setup"]["done"] > before

    def test_a_fully_set_up_fest_has_nothing_left(self):
        self.fill()
        self.event()
        s = self.fest_card()["setup"]  # the committee is already in place in these tests
        assert s["done"] == s["total"] and s["next_label"] is None and s["next_tab"] is None

    def test_a_live_fest_has_no_setup(self):
        self.go_live()
        assert self.fest_card()["setup"] is None


class TestNeedsYou(Home):
    def test_nothing_is_waiting_on_a_quiet_fest(self):
        assert self.home()["attention"] == []

    def test_changes_asked_for_by_hiveout_come_with_their_note(self):
        self.fill(); self.event(); self.submit()
        client.post("/api/admin/fests/fest-one/request-changes", json={"note": "Please add a clearer banner"}, headers=auth(self.admin))
        a = self.home()["attention"][0]
        assert a["kind"] == "changes_requested" and a["tone"] == "red" and "clearer banner" in a["detail"] and a["tab"] == "overview"

    def test_an_approved_fest_that_is_not_live_is_a_prompt(self):
        self.fill(); self.event(); self.submit()
        client.post("/api/admin/fests/fest-one/approve", headers=auth(self.admin))
        assert "approved" in self.kinds()

    def test_registrations_waiting_for_approval_are_counted(self):
        self.go_live()
        fest = client.get("/api/fests/fest-one/manage", headers=auth(self.owner)).json()
        e = client.post("/api/events/", json=event_payload(fest["id"], requires_registration=True, approval_mode="manual", date=f"{day(20)}T10:00:00"), headers=auth(self.owner)).json()
        get_entry_pass(self.student, "fest-one")
        client.post(f"/api/fest-events/{e['id']}/register", headers=auth(self.student))
        a = next(x for x in self.home()["attention"] if x["kind"] == "approvals")
        assert a["title"] == "1 registration to approve" and a["tab"] == "registrations"
        assert self.fest_card()["pending"] == 1

    def test_an_event_soon_with_registration_not_open_is_flagged(self):
        self.event(requires_registration=True, registration_mode="not_set", date=f"{day(5)}T10:00:00")
        a = next(x for x in self.home()["attention"] if x["kind"] == "registration_closed")
        assert "not open yet" in a["title"] and a["tab"] == "events"

    def test_an_event_far_away_is_not_flagged_yet(self):
        self.event(requires_registration=True, registration_mode="not_set", date=f"{day(40)}T10:00:00")
        assert "registration_closed" not in self.kinds()

    def test_registration_closed_by_hand_is_flagged_but_one_that_ended_by_itself_is_not(self):
        e = self.event(requires_registration=True, date=f"{day(5)}T10:00:00", title="Closed by hand")
        client.post(f"/api/events/{e['id']}/registration", json={"action": "close"}, headers=auth(self.owner))
        self.event(requires_registration=True, date=f"{day(6)}T10:00:00", title="Ended itself", registration_deadline=day(-1))
        titles = [a["title"] for a in self.home()["attention"] if a["kind"] == "registration_closed"]
        assert titles == ["Registration for Closed by hand is closed"]

    def test_your_overdue_tasks_are_flagged(self):
        self.task(assignee_member_id=self.owner_mid, due_date=day(-2))
        a = next(x for x in self.home()["attention"] if x["kind"] == "overdue")
        assert a["title"] == "1 task of yours is overdue" and a["tab"] == "tasks"

    def test_someone_elses_overdue_task_is_not_yours_to_chase_here(self):
        self.task(assignee_member_id=self.vol_mid, due_date=day(-2))
        assert "overdue" not in self.kinds()
        assert "overdue" in self.kinds(self.vol)

    def test_a_volunteer_is_not_shown_the_committees_business(self):
        self.go_live()
        fest = client.get("/api/fests/fest-one/manage", headers=auth(self.owner)).json()
        e = client.post("/api/events/", json=event_payload(fest["id"], requires_registration=True, approval_mode="manual", date=f"{day(20)}T10:00:00"), headers=auth(self.owner)).json()
        get_entry_pass(self.student, "fest-one")
        client.post(f"/api/fest-events/{e['id']}/register", headers=auth(self.student))
        assert self.kinds(self.vol) == []

    def test_the_most_urgent_come_first(self):
        self.event(requires_registration=True, registration_mode="not_set", date=f"{day(5)}T10:00:00")
        self.task(assignee_member_id=self.owner_mid, due_date=day(-2))
        tones = [a["tone"] for a in self.home()["attention"]]
        assert tones == sorted(tones, key=lambda t: {"red": 0, "amber": 1, "green": 2}[t])


class TestMyTasks(Home):
    def test_only_my_open_tasks_soonest_first(self):
        self.task(title="Later", assignee_member_id=self.owner_mid, due_date=day(9))
        self.task(title="Sooner", assignee_member_id=self.owner_mid, due_date=day(1))
        self.task(title="No date", assignee_member_id=self.owner_mid)
        done = self.task(title="Done already", assignee_member_id=self.owner_mid)
        client.patch(f"/api/fests/fest-one/tasks/{done['id']}", json={"status": "done"}, headers=auth(self.owner))
        self.task(title="Not mine", assignee_member_id=self.vol_mid)
        assert [t["title"] for t in self.home()["my_tasks"]] == ["Sooner", "Later", "No date"]

    def test_overdue_is_marked(self):
        self.task(assignee_member_id=self.owner_mid, due_date=day(-1))
        assert self.home()["my_tasks"][0]["overdue"] is True

    def test_a_volunteer_sees_their_own(self):
        self.task(title="Man the gate", assignee_member_id=self.vol_mid, due_date=day(2))
        assert [t["title"] for t in self.home(self.vol)["my_tasks"]] == ["Man the gate"]


class TestComingUp(Home):
    def test_events_in_the_next_two_weeks_are_listed_in_order(self):
        self.event(title="Later", date=f"{day(10)}T10:00:00")
        self.event(title="Sooner", date=f"{day(2)}T10:00:00")
        self.event(title="Too far", date=f"{day(40)}T10:00:00")
        assert [u["title"] for u in self.home()["coming_up"] if u["kind"] == "event"] == ["Sooner", "Later"]

    def test_cancelled_events_are_left_out(self):
        e = self.event(title="Off", date=f"{day(3)}T10:00:00")
        client.post(f"/api/events/{e['id']}/cancel", json={"reason": "Rain"}, headers=auth(self.owner))
        assert self.home()["coming_up"] == []

    def test_a_multi_day_event_already_under_way_shows_which_day_it_is_on(self):
        self.event(title="Expo", date=f"{day(-1)}T10:00:00", span_days=3)
        u = self.home()["coming_up"][0]
        assert u["title"] == "Expo" and u["detail"] == "day 2 of 3"

    def test_an_event_that_has_ended_is_left_out(self):
        self.event(title="Over", date=f"{day(-5)}T10:00:00")
        assert self.home()["coming_up"] == []

    def test_meetings_are_mixed_in_by_time(self):
        self.event(title="Event", date=f"{day(5)}T10:00:00")
        client.post("/api/fests/fest-one/meetings", json={"title": "Kick-off", "starts_at": (datetime.now() + timedelta(days=2)).replace(microsecond=0).isoformat()}, headers=auth(self.owner))
        assert [(u["kind"], u["title"]) for u in self.home()["coming_up"]] == [("meeting", "Kick-off"), ("event", "Event")]

    def test_a_volunteer_sees_only_meetings_they_are_invited_to(self):
        when = (datetime.now() + timedelta(days=2)).replace(microsecond=0).isoformat()
        client.post("/api/fests/fest-one/meetings", json={"title": "Core only", "starts_at": when, "member_ids": [self.core_mid]}, headers=auth(self.owner))
        client.post("/api/fests/fest-one/meetings", json={"title": "Everyone", "starts_at": when}, headers=auth(self.owner))
        assert [u["title"] for u in self.home(self.vol)["coming_up"] if u["kind"] == "meeting"] == ["Everyone"]
        assert {u["title"] for u in self.home(self.owner)["coming_up"]} == {"Core only", "Everyone"}

    def test_a_meeting_in_the_past_or_far_off_is_left_out(self):
        for days in (-1, 30):
            client.post("/api/fests/fest-one/meetings", json={"title": f"M{days}", "starts_at": (datetime.now() + timedelta(days=days)).replace(microsecond=0).isoformat()}, headers=auth(self.owner))
        assert self.home()["coming_up"] == []

    def test_it_says_which_fest_each_item_belongs_to(self):
        self.event(title="E", date=f"{day(2)}T10:00:00")
        u = self.home()["coming_up"][0]
        assert u["fest_slug"] == "fest-one" and u["fest_name"] == "Fest One" and u["tab"] == "events"
