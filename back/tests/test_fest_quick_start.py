"""Starting a fest in under a minute: optional dates at creation, a prefilled contact, and the guided checklist."""

from test_full import client, auth, reset_db, TestingSessionLocal  # noqa: F401
from test_organiser import Setup, FEST_DETAILS, event_payload  # noqa: F401


def checklist(setup, slug="fest-one"):
    r = client.get(f"/api/fests/{slug}/manage/checklist", headers=auth(setup.owner))
    assert r.status_code == 200, r.text
    return r.json()


def item(data, key):
    return next(i for i in data["items"] if i["key"] == key)


class TestStartingAFest(Setup):
    def test_dates_are_optional_at_creation(self):
        fest = self.start()
        assert fest["start_date"] is None and fest["end_date"] is None

    def test_dates_are_saved_when_given(self):
        fest = self.start(start_date="2026-12-04", end_date="2026-12-06")
        assert fest["start_date"] == "2026-12-04" and fest["end_date"] == "2026-12-06"

    def test_a_start_date_alone_makes_a_one_day_fest(self):
        fest = self.start(start_date="2026-12-04")
        assert fest["end_date"] == "2026-12-04"

    def test_an_end_date_without_a_start_is_refused(self):
        r = client.post("/api/fests/", json={"slug": "fest-one", "name": "Fest One", "college_id": self.college_id, "end_date": "2026-12-06"}, headers=auth(self.owner))
        assert r.status_code == 422

    def test_an_end_before_the_start_is_refused(self):
        r = client.post("/api/fests/", json={"slug": "fest-one", "name": "Fest One", "college_id": self.college_id, "start_date": "2026-12-06", "end_date": "2026-12-04"}, headers=auth(self.owner))
        assert r.status_code == 422

    def test_the_contact_starts_as_the_person_creating_the_fest(self):
        self.start()
        manage = client.get("/api/fests/fest-one/manage", headers=auth(self.owner)).json()
        assert manage["contact_name"].startswith("Owner") and manage["contact_email"] == "owner@test.com"


class TestChecklist(Setup):
    def test_a_new_fest_has_the_tasks_in_order_and_the_optional_one_last(self):
        self.start()
        data = checklist(self)
        assert [i["key"] for i in data["items"]] == ["dates", "banner", "description", "venue", "contact", "events", "team"]
        assert item(data, "team")["required"] is False
        assert all(i["required"] for i in data["items"] if i["key"] != "team")

    def test_nothing_is_done_except_what_was_prefilled(self):
        self.start()
        data = checklist(self)
        assert [i["key"] for i in data["items"] if i["done"]] == []
        assert item(data, "contact")["done"] is False  # name and email are prefilled; the phone number is still needed

    def test_dates_given_at_creation_tick_that_task_off(self):
        self.start(start_date="2026-12-04", end_date="2026-12-06")
        assert item(checklist(self), "dates")["done"] is True

    def test_the_contact_is_done_once_a_phone_number_is_added(self):
        self.start()
        client.patch("/api/fests/fest-one", json={"contact_phone": "+91 98765 43210"}, headers=auth(self.owner))
        assert item(checklist(self), "contact")["done"] is True

    def test_everything_required_is_done_when_the_fest_is_ready(self):
        fest = self.start()
        self.fill()
        self.add_event(fest["id"])
        data = checklist(self)
        assert data["missing"] == []
        assert all(i["done"] for i in data["items"] if i["required"])

    def test_an_event_outside_the_dates_is_reported_under_events(self):
        fest = self.start()
        self.fill()
        self.add_event(fest["id"], date="2026-12-20T18:00:00")
        events = item(checklist(self), "events")
        assert events["done"] is False and any("outside the fest" in p for p in events["problems"])

    def test_the_checklist_agrees_with_what_submit_will_say(self):
        self.start()
        assert checklist(self)["missing"] == self.submit().json()["detail"]["missing"]

    def test_only_the_committee_can_see_it(self):
        self.start()
        assert client.get("/api/fests/fest-one/manage/checklist", headers=auth(self.student)).status_code == 403


class TestOptionalFields(Setup):
    def test_a_fest_without_a_tagline_or_map_link_can_be_submitted(self):
        fest = self.start()
        self.fill(tagline=None, map_url=None)
        self.add_event(fest["id"])
        r = self.submit()
        assert r.status_code == 200, r.text

    def test_the_optional_team_task_never_blocks_submitting(self):
        fest = self.start()
        self.fill()
        self.add_event(fest["id"])
        assert item(checklist(self), "team")["done"] is False
        assert self.submit().status_code == 200
