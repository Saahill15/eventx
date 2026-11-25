"""Sponsors and partners: the committee lists them with logos and tiers, and a live fest shows them to everyone."""

from test_full import client, auth, reset_db, TestingSessionLocal  # noqa: F401
from test_committee_structure import Committee
from app import models


class Sponsors(Committee):
    def add(self, name="Acme Bank", token=None, slug="fest-one", **extra):
        return client.post(f"/api/fests/{slug}/sponsors", json={"name": name, **extra}, headers=auth(token or self.owner))

    def listing(self, token=None, slug="fest-one"):
        return client.get(f"/api/fests/{slug}/sponsors", headers=auth(token) if token else {})

    def go_live(self):
        fest = client.get("/api/fests/fest-one/manage", headers=auth(self.owner)).json()
        self.fill()
        self.add_event(fest["id"])
        assert self.submit().status_code == 200
        assert client.post("/api/admin/fests/fest-one/approve", headers=auth(self.admin)).status_code == 200
        assert client.patch("/api/fests/fest-one/status", json={"status": "live"}, headers=auth(self.owner)).status_code == 200


class TestAddingSponsors(Sponsors):
    def test_a_sponsor_needs_only_a_name(self):
        r = self.add("Acme Bank")
        assert r.status_code == 201
        s = r.json()
        assert s["name"] == "Acme Bank" and s["level"] == 3 and s["tier_label"] == "Associate Sponsors" and s["logo_url"] is None

    def test_a_tier_without_a_label_gets_the_usual_name(self):
        assert self.add("A", level=1).json()["tier_label"] == "Title Sponsor"
        assert self.add("B", level=2).json()["tier_label"] == "Powered by"
        assert self.add("C", level=4).json()["tier_label"] == "Partners"

    def test_the_fest_can_use_its_own_wording(self):
        assert self.add("Fresh Juice Co", level=4, tier_label="Refreshment Partner").json()["tier_label"] == "Refreshment Partner"

    def test_a_logo_link_and_line_are_kept(self):
        s = self.add("Acme", logo_url="/api/media/abc123", website_url="https://acme.example", blurb="Banking partner since 2019").json()
        assert s["logo_url"] == "/api/media/abc123" and s["website_url"] == "https://acme.example" and s["blurb"] == "Banking partner since 2019"

    def test_bad_links_are_refused(self):
        assert self.add("X", website_url="javascript:alert(1)").status_code == 422
        assert self.add("X", website_url="acme.example").status_code == 422
        assert self.add("X", logo_url="javascript:alert(1)").status_code == 422
        assert self.add("X", website_url="/api/media/abc").status_code == 422

    def test_the_level_must_be_one_to_four(self):
        assert self.add("X", level=0).status_code == 422
        assert self.add("X", level=5).status_code == 422

    def test_a_name_is_needed_and_cannot_repeat(self):
        assert self.add("   ").status_code == 422
        self.add("Acme")
        assert self.add("acme").status_code == 400

    def test_a_fest_lists_at_most_forty(self):
        db = TestingSessionLocal()
        fest_id = db.query(models.Fest).filter(models.Fest.slug == "fest-one").first().id
        for i in range(40):
            db.add(models.FestSponsor(fest_id=fest_id, name=f"S{i}", tier_label="Partners", level=4, position=i))
        db.commit(); db.close()
        assert self.add("One more").status_code == 400

    def test_only_the_director_core_team_and_admins_can_add(self):
        assert self.add(token=self.core).status_code == 201
        assert self.add("B", token=self.admin).status_code == 201
        assert self.add("C", token=self.vol).status_code == 403
        assert self.add("D", token=self.student).status_code == 403
        assert client.post("/api/fests/fest-one/sponsors", json={"name": "E"}).status_code == 401

    def test_an_unknown_fest_is_not_found(self):
        assert self.add(slug="nope").status_code == 404


class TestOrderAndChanges(Sponsors):
    def test_the_list_runs_from_the_biggest_tier_down_then_in_the_order_added(self):
        self.add("Partner A", level=4)
        self.add("Assoc", level=3)
        self.add("Title Co", level=1)
        self.add("Partner B", level=4)
        self.add("Powered Co", level=2)
        names = [s["name"] for s in self.listing(self.owner).json()]
        assert names == ["Title Co", "Powered Co", "Assoc", "Partner A", "Partner B"]

    def test_a_sponsor_can_be_moved_up_and_down_inside_its_tier(self):
        a = self.add("A", level=4).json()["id"]; b = self.add("B", level=4).json()["id"]; c = self.add("C", level=4).json()["id"]
        client.post(f"/api/fests/fest-one/sponsors/{c}/move", json={"direction": "up"}, headers=auth(self.owner))
        assert [s["name"] for s in self.listing(self.owner).json()] == ["A", "C", "B"]
        client.post(f"/api/fests/fest-one/sponsors/{a}/move", json={"direction": "down"}, headers=auth(self.owner))
        assert [s["name"] for s in self.listing(self.owner).json()] == ["C", "A", "B"]
        assert b

    def test_moving_past_the_end_changes_nothing(self):
        a = self.add("A", level=4).json()["id"]; self.add("B", level=4)
        r = client.post(f"/api/fests/fest-one/sponsors/{a}/move", json={"direction": "up"}, headers=auth(self.owner))
        assert r.status_code == 200 and [s["name"] for s in r.json()] == ["A", "B"]

    def test_a_move_never_crosses_into_another_tier(self):
        t = self.add("T", level=1).json()["id"]; self.add("P", level=4)
        client.post(f"/api/fests/fest-one/sponsors/{t}/move", json={"direction": "down"}, headers=auth(self.owner))
        assert [s["name"] for s in self.listing(self.owner).json()] == ["T", "P"]

    def test_a_sponsor_can_be_renamed_and_given_a_logo_later(self):
        sid = self.add("Acme").json()["id"]
        r = client.patch(f"/api/fests/fest-one/sponsors/{sid}", json={"name": "Acme Group", "logo_url": "/api/media/xyz", "website_url": "https://acme.example"}, headers=auth(self.owner))
        assert r.status_code == 200 and r.json()["name"] == "Acme Group" and r.json()["logo_url"] == "/api/media/xyz"

    def test_a_logo_and_link_can_be_cleared(self):
        sid = self.add("Acme", logo_url="/api/media/xyz", website_url="https://acme.example").json()["id"]
        r = client.patch(f"/api/fests/fest-one/sponsors/{sid}", json={"logo_url": None, "website_url": None}, headers=auth(self.owner)).json()
        assert r["logo_url"] is None and r["website_url"] is None

    def test_changing_the_tier_puts_it_last_there_with_that_tiers_label(self):
        self.add("Old Partner", level=1)
        sid = self.add("Acme", level=4).json()["id"]
        r = client.patch(f"/api/fests/fest-one/sponsors/{sid}", json={"level": 1}, headers=auth(self.owner)).json()
        assert r["level"] == 1 and r["tier_label"] == "Title Sponsor"
        assert [s["name"] for s in self.listing(self.owner).json()] == ["Old Partner", "Acme"]

    def test_changing_the_tier_and_label_together_keeps_the_label(self):
        sid = self.add("Acme", level=4).json()["id"]
        r = client.patch(f"/api/fests/fest-one/sponsors/{sid}", json={"level": 2, "tier_label": "Presented by"}, headers=auth(self.owner)).json()
        assert r["tier_label"] == "Presented by"

    def test_a_rename_cannot_clash_with_another_sponsor(self):
        self.add("A"); b = self.add("B").json()["id"]
        assert client.patch(f"/api/fests/fest-one/sponsors/{b}", json={"name": "a"}, headers=auth(self.owner)).status_code == 400

    def test_others_cannot_change_move_or_remove(self):
        sid = self.add("Acme").json()["id"]
        for token in (self.vol, self.student):
            assert client.patch(f"/api/fests/fest-one/sponsors/{sid}", json={"name": "Hacked"}, headers=auth(token)).status_code == 403
            assert client.post(f"/api/fests/fest-one/sponsors/{sid}/move", json={"direction": "up"}, headers=auth(token)).status_code == 403
            assert client.delete(f"/api/fests/fest-one/sponsors/{sid}", headers=auth(token)).status_code == 403

    def test_a_sponsor_can_be_removed(self):
        sid = self.add("Acme").json()["id"]
        assert client.delete(f"/api/fests/fest-one/sponsors/{sid}", headers=auth(self.owner)).status_code == 204
        assert self.listing(self.owner).json() == []

    def test_one_fests_sponsor_cannot_be_reached_through_another(self):
        sid = self.add("Acme").json()["id"]
        client.post("/api/fests/", json={"slug": "fest-two", "name": "Two", "college_id": self.college_id}, headers=auth(self.owner))
        assert client.delete(f"/api/fests/fest-two/sponsors/{sid}", headers=auth(self.owner)).status_code == 404
        assert client.patch(f"/api/fests/fest-two/sponsors/{sid}", json={"name": "X"}, headers=auth(self.owner)).status_code == 404


class TestWhoSeesThem(Sponsors):
    def test_a_draft_fests_sponsors_are_private_to_its_committee_and_admins(self):
        self.add("Acme")
        assert len(self.listing(self.owner).json()) == 1
        assert len(self.listing(self.vol).json()) == 1
        assert len(self.listing(self.admin).json()) == 1
        assert self.listing().status_code == 404
        assert self.listing(self.student).status_code == 404

    def test_once_the_fest_is_live_everyone_sees_them_without_signing_in(self):
        self.add("Acme", level=1, logo_url="/api/media/xyz", website_url="https://acme.example")
        self.go_live()
        r = self.listing()
        assert r.status_code == 200 and r.json()[0]["name"] == "Acme" and r.json()[0]["tier_label"] == "Title Sponsor"
        assert self.listing(self.student).status_code == 200

    def test_nothing_private_is_in_the_public_list(self):
        self.add("Acme")
        self.go_live()
        assert set(self.listing().json()[0]) == {"id", "fest_id", "name", "level", "tier_label", "logo_url", "website_url", "blurb", "position"}
