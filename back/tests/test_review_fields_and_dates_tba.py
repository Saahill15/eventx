"""Field-level review notes, and fests listed as "Dates coming soon"."""

import pytest

from test_full import client, auth, reset_db, TestingSessionLocal  # noqa: F401
from test_organiser import Setup, FEST_DETAILS, event_payload  # noqa: F401


def checklist(setup, slug="fest-one"):
    r = client.get(f"/api/fests/{slug}/manage/checklist", headers=auth(setup.owner))
    assert r.status_code == 200, r.text
    return r.json()


def item(data, key):
    return next(i for i in data["items"] if i["key"] == key)


def manage(setup, slug="fest-one"):
    return client.get(f"/api/fests/{slug}/manage", headers=auth(setup.owner)).json()


class InReview(Setup):
    """A fest that has been submitted and is waiting for the admin."""

    def submitted(self, slug="fest-one"):
        fest = self.start(slug)
        self.fill(slug)
        self.add_event(fest["id"])
        assert self.submit(slug).status_code == 200
        return fest

    def decide(self, action, body, slug="fest-one"):
        return client.post(f"/api/admin/fests/{slug}/{action}", json=body, headers=auth(self.admin))


class TestFieldNotes(InReview):
    def test_the_admin_can_flag_specific_fields(self):
        self.submitted()
        r = self.decide("request-changes", {"fields": [{"key": "banner", "note": "The banner is blurry"}, {"key": "contact", "note": "Add a working phone number"}]})
        assert r.status_code == 200, r.text
        assert manage(self)["review_fields"] == [{"key": "banner", "note": "The banner is blurry"}, {"key": "contact", "note": "Add a working phone number"}]

    def test_a_general_note_and_fields_can_be_sent_together(self):
        self.submitted()
        r = self.decide("request-changes", {"note": "Nearly there, two small things.", "fields": [{"key": "description", "note": "Say what the fest is about"}]})
        assert r.status_code == 200
        m = manage(self)
        assert m["review_note"] == "Nearly there, two small things." and m["review_fields"][0]["key"] == "description"

    def test_a_note_alone_still_works(self):
        self.submitted()
        assert self.decide("request-changes", {"note": "Please fix the dates."}).status_code == 200
        assert manage(self)["review_fields"] == []

    def test_fields_alone_work_with_no_general_note(self):
        self.submitted()
        assert self.decide("request-changes", {"fields": [{"key": "dates", "note": "These dates clash with exams"}]}).status_code == 200
        assert manage(self)["review_note"] is None

    def test_saying_nothing_is_refused(self):
        self.submitted()
        assert self.decide("request-changes", {}).status_code == 422
        assert self.decide("request-changes", {"fields": []}).status_code == 422

    def test_an_unknown_field_is_refused(self):
        self.submitted()
        assert self.decide("request-changes", {"fields": [{"key": "salary", "note": "x"}]}).status_code == 422

    def test_the_same_field_cannot_be_flagged_twice(self):
        self.submitted()
        assert self.decide("request-changes", {"fields": [{"key": "banner", "note": "a"}, {"key": "banner", "note": "b"}]}).status_code == 422

    def test_an_empty_field_note_is_refused(self):
        self.submitted()
        assert self.decide("request-changes", {"fields": [{"key": "banner", "note": "   "}]}).status_code == 422

    def test_rejecting_can_flag_fields_too(self):
        self.submitted()
        assert self.decide("reject", {"note": "This is not a college fest.", "fields": [{"key": "name", "note": "Misleading name"}]}).status_code == 200
        assert manage(self)["review_fields"][0]["key"] == "name"

    def test_taking_an_approved_fest_offline_can_flag_fields(self):
        self.ready_and_approved()
        r = self.decide("unpublish", {"fields": [{"key": "links", "note": "The Instagram link goes somewhere else"}]})
        assert r.status_code == 200, r.text
        assert manage(self)["review_fields"][0]["key"] == "links"

    def test_only_admins_can_decide(self):
        self.submitted()
        r = client.post("/api/admin/fests/fest-one/request-changes", json={"note": "Nope, not allowed."}, headers=auth(self.owner))
        assert r.status_code == 403


class TestFlagsOnTheChecklist(InReview):
    def test_a_flag_rides_on_the_matching_task(self):
        self.submitted()
        self.decide("request-changes", {"fields": [{"key": "banner", "note": "The banner is blurry"}]})
        data = checklist(self)
        assert item(data, "banner")["flag"] == "The banner is blurry"
        assert item(data, "description")["flag"] is None

    def test_fields_without_a_task_are_still_listed_in_the_manage_view(self):
        self.submitted()
        self.decide("request-changes", {"fields": [{"key": "tagline", "note": "Shorter please"}]})
        assert all(i["flag"] is None for i in checklist(self)["items"])
        assert manage(self)["review_fields"][0]["key"] == "tagline"

    def test_submitting_again_clears_the_flags(self):
        self.submitted()
        self.decide("request-changes", {"fields": [{"key": "banner", "note": "Blurry"}]})
        assert self.submit().status_code == 200
        assert manage(self)["review_fields"] == []

    def test_approving_clears_the_flags(self):
        self.submitted()
        self.decide("request-changes", {"fields": [{"key": "banner", "note": "Blurry"}]})
        self.submit()
        assert client.post("/api/admin/fests/fest-one/approve", headers=auth(self.admin)).status_code == 200
        assert manage(self)["review_fields"] == []

    def test_flags_are_not_shown_on_the_checklist_once_the_fest_is_approved(self):
        self.submitted()
        self.decide("request-changes", {"fields": [{"key": "banner", "note": "Blurry"}]})
        self.submit()
        client.post("/api/admin/fests/fest-one/approve", headers=auth(self.admin))
        assert all(i["flag"] is None for i in checklist(self)["items"])


class TestDatesComingSoon(Setup):
    def tba(self, slug="fest-one", value=True):
        return client.patch(f"/api/fests/{slug}", json={"dates_tba": value}, headers=auth(self.owner))

    def ready_without_dates(self):
        self.start()
        self.fill(start_date=None, end_date=None)
        r = self.tba()
        assert r.status_code == 200, r.text

    def test_a_fest_can_be_marked_dates_coming_soon(self):
        self.start()
        r = self.tba()
        assert r.status_code == 200 and r.json()["dates_tba"] is True
        assert r.json()["start_date"] is None and r.json()["end_date"] is None

    def test_it_counts_as_done_for_the_dates_task_and_events_become_optional(self):
        self.start()
        self.tba()
        data = checklist(self)
        assert item(data, "dates")["done"] is True
        assert item(data, "events")["required"] is False and item(data, "events")["done"] is False

    def test_it_can_be_submitted_with_no_dates_and_no_events(self):
        self.ready_without_dates()
        r = self.submit()
        assert r.status_code == 200, r.text
        assert checklist(self)["missing"] == []

    def test_what_is_missing_leaves_out_dates_and_events(self):
        self.start()
        self.tba()
        missing = self.submit().json()["detail"]["missing"]
        assert "start date" not in missing and "end date" not in missing and "at least one event" not in missing
        assert "description" in missing  # everything else is still needed

    def test_without_the_flag_dates_and_events_are_still_required(self):
        self.start()
        missing = self.submit().json()["detail"]["missing"]
        assert "start date" in missing and "at least one event" in missing

    def test_the_admin_can_approve_it_and_it_can_go_live_with_the_flag_public(self):
        self.ready_without_dates()
        self.submit()
        assert client.post("/api/admin/fests/fest-one/approve", headers=auth(self.admin)).status_code == 200
        assert client.patch("/api/fests/fest-one/status", json={"status": "live"}, headers=auth(self.owner)).status_code == 200
        public = client.get("/api/fests/fest-one").json()
        assert public["dates_tba"] is True and public["start_date"] is None
        assert any(f["slug"] == "fest-one" and f["dates_tba"] is True for f in client.get("/api/fests/").json())

    def test_events_cannot_be_added_while_dates_are_coming_soon(self):
        fest = self.start()
        self.tba()
        r = client.post("/api/events/", json=event_payload(fest["id"]), headers=auth(self.owner))
        assert r.status_code == 400 and "Dates coming soon" in r.json()["detail"]

    def test_the_csv_import_is_blocked_too(self):
        self.start()
        self.tba()
        r = client.post("/api/fests/fest-one/events/import", files={"file": ("events.csv", b"title\n", "text/csv")}, headers=auth(self.owner))
        assert r.status_code == 400 and "Dates coming soon" in r.json()["detail"]

    def test_it_cannot_be_chosen_once_the_fest_has_events(self):
        fest = self.start()
        self.fill()
        self.add_event(fest["id"])
        r = self.tba()
        assert r.status_code == 400 and "events need dates" in r.json()["detail"]
        assert client.get("/api/fests/fest-one/manage", headers=auth(self.owner)).json()["start_date"] == "2026-12-04"  # nothing was cleared

    def test_setting_dates_switches_it_off(self):
        fest = self.start()
        self.tba()
        r = client.patch("/api/fests/fest-one", json={"start_date": "2026-12-04", "end_date": "2026-12-06"}, headers=auth(self.owner))
        assert r.status_code == 200 and r.json()["dates_tba"] is False
        assert client.post("/api/events/", json=event_payload(fest["id"]), headers=auth(self.owner)).status_code == 200

    def test_choosing_it_again_clears_dates_that_were_set(self):
        self.start(start_date="2026-12-04", end_date="2026-12-06")
        r = self.tba()
        assert r.status_code == 200 and r.json()["start_date"] is None and r.json()["dates_tba"] is True

    def test_it_can_be_switched_off_without_giving_dates(self):
        self.start()
        self.tba()
        r = self.tba(value=False)
        assert r.status_code == 200 and r.json()["dates_tba"] is False
        assert "start date" in client.post("/api/fests/fest-one/submit", headers=auth(self.owner)).json()["detail"]["missing"]

    def test_giving_dates_and_the_flag_together_keeps_the_dates(self):
        self.start()
        r = client.patch("/api/fests/fest-one", json={"dates_tba": True, "start_date": "2026-12-04", "end_date": "2026-12-06"}, headers=auth(self.owner))
        assert r.status_code == 200 and r.json()["dates_tba"] is False and r.json()["start_date"] == "2026-12-04"

    def test_a_stranger_cannot_change_it(self):
        self.start()
        r = client.patch("/api/fests/fest-one", json={"dates_tba": True}, headers=auth(self.student))
        assert r.status_code == 403

    def test_the_fest_stays_editable_by_staff_only_while_in_review_is_locked(self):
        self.ready_without_dates()
        self.submit()
        assert self.tba(value=False).status_code == 400  # waiting for review: frozen like everything else
