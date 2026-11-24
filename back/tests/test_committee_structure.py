"""Committee structure: teams, titles and who reports to whom."""

from test_fixes import user_token, user_id  # noqa: F401
from test_full import client, auth, reset_db, TestingSessionLocal  # noqa: F401
from test_organiser import Setup
from app import models


def join(slug, email, role):
    """Put an existing account on a fest's committee directly, and return the member id."""
    db = TestingSessionLocal()
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    uid = db.query(models.User).filter(models.User.email == email).first().id
    member = models.FestMember(fest_id=fest.id, user_id=uid, role=models.FestMemberRoleEnum(role))
    db.add(member)
    db.commit()
    mid = member.id
    db.close()
    return mid


def member_id(slug, email):
    db = TestingSessionLocal()
    fest = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    m = db.query(models.FestMember).join(models.User, models.User.id == models.FestMember.user_id).filter(models.FestMember.fest_id == fest.id, models.User.email == email).first()
    mid = m.id
    db.close()
    return mid


class Committee(Setup):
    """A fest with a director (owner), a core member and a volunteer."""

    def setup_method(self):
        super().setup_method()
        self.start()
        self.core = user_token("Core", "core@test.com")
        self.vol = user_token("Vol", "vol@test.com")
        self.core_mid = join("fest-one", "core@test.com", "core")
        self.vol_mid = join("fest-one", "vol@test.com", "volunteer")
        self.owner_mid = member_id("fest-one", "owner@test.com")

    def org(self, token=None, slug="fest-one"):
        return client.get(f"/api/fests/{slug}/org", headers=auth(token or self.owner))

    def add_team(self, name="Sponsorship", token=None, slug="fest-one", **extra):
        return client.post(f"/api/fests/{slug}/org/teams", json={"name": name, **extra}, headers=auth(token or self.owner))

    def place(self, mid, body, token=None, slug="fest-one"):
        return client.patch(f"/api/fests/{slug}/org/members/{mid}", json=body, headers=auth(token or self.owner))


class TestTeams(Committee):
    def test_the_director_can_add_a_team(self):
        r = self.add_team("Sponsorship", description="Finds sponsors")
        assert r.status_code == 201 and r.json()["name"] == "Sponsorship" and r.json()["member_count"] == 0

    def test_core_members_can_add_teams(self):
        assert self.add_team("PR", token=self.core).status_code == 201

    def test_volunteers_and_strangers_cannot(self):
        assert self.add_team("PR", token=self.vol).status_code == 403
        assert self.add_team("PR", token=self.student).status_code == 403

    def test_admins_can(self):
        assert self.add_team("PR", token=self.admin).status_code == 201

    def test_team_names_are_unique_ignoring_case(self):
        self.add_team("Logistics")
        assert self.add_team("logistics").status_code == 400

    def test_two_fests_can_use_the_same_team_name(self):
        self.add_team("Logistics")
        self.start("fest-two")
        assert self.add_team("Logistics", slug="fest-two").status_code == 201

    def test_a_blank_name_is_refused(self):
        assert self.add_team("   ").status_code == 422

    def test_a_fest_is_limited_to_thirty_teams(self):
        for i in range(30):
            assert self.add_team(f"Team {i}").status_code == 201
        assert self.add_team("One too many").status_code == 400

    def test_suggested_teams_adds_the_usual_set(self):
        r = client.post("/api/fests/fest-one/org/teams/suggested", headers=auth(self.owner))
        assert r.status_code == 201
        names = [t["name"] for t in r.json()]
        assert "Sponsorship" in names and "Logistics" in names and len(names) == 9

    def test_suggested_teams_skips_names_that_exist_and_is_safe_to_repeat(self):
        self.add_team("Events")
        first = client.post("/api/fests/fest-one/org/teams/suggested", headers=auth(self.owner)).json()
        again = client.post("/api/fests/fest-one/org/teams/suggested", headers=auth(self.owner)).json()
        assert len(first) == 8 and again == []

    def test_suggested_teams_needs_staff(self):
        assert client.post("/api/fests/fest-one/org/teams/suggested", headers=auth(self.vol)).status_code == 403

    def test_a_team_can_be_renamed_and_described(self):
        tid = self.add_team("PR").json()["id"]
        r = client.patch(f"/api/fests/fest-one/org/teams/{tid}", json={"name": "PR and Marketing", "description": "Publicity"}, headers=auth(self.owner))
        assert r.status_code == 200 and r.json()["name"] == "PR and Marketing" and r.json()["description"] == "Publicity"

    def test_renaming_to_an_existing_name_is_refused_but_keeping_the_name_is_fine(self):
        a = self.add_team("A").json()["id"]
        self.add_team("B")
        assert client.patch(f"/api/fests/fest-one/org/teams/{a}", json={"name": "b"}, headers=auth(self.owner)).status_code == 400
        assert client.patch(f"/api/fests/fest-one/org/teams/{a}", json={"name": "A"}, headers=auth(self.owner)).status_code == 200

    def test_the_description_can_be_cleared(self):
        tid = self.add_team("PR", description="Publicity").json()["id"]
        r = client.patch(f"/api/fests/fest-one/org/teams/{tid}", json={"description": ""}, headers=auth(self.owner))
        assert r.json()["description"] is None

    def test_a_volunteer_cannot_rename_or_delete(self):
        tid = self.add_team("PR").json()["id"]
        assert client.patch(f"/api/fests/fest-one/org/teams/{tid}", json={"name": "X"}, headers=auth(self.vol)).status_code == 403
        assert client.delete(f"/api/fests/fest-one/org/teams/{tid}", headers=auth(self.vol)).status_code == 403

    def test_deleting_a_team_keeps_its_people_without_a_team(self):
        tid = self.add_team("PR").json()["id"]
        self.place(self.vol_mid, {"committee_team_id": tid})
        assert client.delete(f"/api/fests/fest-one/org/teams/{tid}", headers=auth(self.owner)).status_code == 204
        me = next(m for m in self.org().json()["members"] if m["id"] == self.vol_mid)
        assert me["committee_team_id"] is None and me["team_name"] is None

    def test_another_fests_team_is_not_found(self):
        self.start("fest-two")
        other = self.add_team("Secret", slug="fest-two").json()["id"]
        assert client.patch(f"/api/fests/fest-one/org/teams/{other}", json={"name": "X"}, headers=auth(self.owner)).status_code == 404
        assert client.delete(f"/api/fests/fest-one/org/teams/{other}", headers=auth(self.owner)).status_code == 404


class TestSeeingTheOrg(Committee):
    def test_every_committee_member_can_see_it(self):
        self.add_team("PR")
        for token in (self.owner, self.core, self.vol, self.admin):
            r = self.org(token)
            assert r.status_code == 200 and len(r.json()["members"]) == 3 and r.json()["teams"][0]["name"] == "PR"

    def test_strangers_cannot(self):
        assert self.org(self.student).status_code == 403

    def test_team_member_counts_are_shown(self):
        tid = self.add_team("PR").json()["id"]
        self.place(self.vol_mid, {"committee_team_id": tid})
        self.place(self.core_mid, {"committee_team_id": tid})
        assert self.org().json()["teams"][0]["member_count"] == 2

    def test_the_members_list_also_carries_the_new_fields(self):
        tid = self.add_team("PR").json()["id"]
        self.place(self.vol_mid, {"title": "Poster lead", "committee_team_id": tid})
        members = client.get("/api/fests/fest-one/members", headers=auth(self.owner)).json()
        vol = next(m for m in members if m["id"] == self.vol_mid)
        assert vol["title"] == "Poster lead" and vol["team_name"] == "PR"


class TestPlacement(Committee):
    def test_a_title_a_team_and_a_lead_can_be_set(self):
        tid = self.add_team("Sponsorship").json()["id"]
        r = self.place(self.vol_mid, {"title": "Outreach", "committee_team_id": tid, "reports_to_id": self.core_mid})
        assert r.status_code == 200
        body = r.json()
        assert body["title"] == "Outreach" and body["team_name"] == "Sponsorship" and body["reports_to_id"] == self.core_mid and body["reports_to_name"].startswith("Core")

    def test_only_what_is_sent_changes(self):
        tid = self.add_team("Sponsorship").json()["id"]
        self.place(self.vol_mid, {"title": "Outreach", "committee_team_id": tid})
        r = self.place(self.vol_mid, {"title": "Outreach lead"})
        assert r.json()["title"] == "Outreach lead" and r.json()["committee_team_id"] == tid

    def test_null_clears_a_field(self):
        tid = self.add_team("Sponsorship").json()["id"]
        self.place(self.vol_mid, {"title": "Outreach", "committee_team_id": tid, "reports_to_id": self.core_mid})
        r = self.place(self.vol_mid, {"title": None, "committee_team_id": None, "reports_to_id": None})
        body = r.json()
        assert body["title"] is None and body["committee_team_id"] is None and body["reports_to_id"] is None

    def test_a_blank_title_clears_it(self):
        self.place(self.vol_mid, {"title": "Outreach"})
        assert self.place(self.vol_mid, {"title": "   "}).json()["title"] is None

    def test_a_title_is_limited_to_eighty_characters(self):
        assert self.place(self.vol_mid, {"title": "x" * 81}).status_code == 422
        assert self.place(self.vol_mid, {"title": "x" * 80}).status_code == 200

    def test_nobody_reports_to_themselves(self):
        assert self.place(self.vol_mid, {"reports_to_id": self.vol_mid}).status_code == 400

    def test_the_chart_cannot_loop(self):
        self.place(self.vol_mid, {"reports_to_id": self.core_mid})
        assert self.place(self.core_mid, {"reports_to_id": self.vol_mid}).status_code == 400

    def test_a_longer_loop_is_caught_too(self):
        self.place(self.vol_mid, {"reports_to_id": self.core_mid})
        self.place(self.core_mid, {"reports_to_id": self.owner_mid})
        assert self.place(self.owner_mid, {"reports_to_id": self.vol_mid}).status_code == 400

    def test_a_lead_must_be_on_the_same_committee(self):
        self.start("fest-two")
        other = member_id("fest-two", "owner@test.com")
        assert self.place(self.vol_mid, {"reports_to_id": other}).status_code == 400
        assert self.place(self.vol_mid, {"reports_to_id": 99999}).status_code == 400

    def test_a_team_must_belong_to_this_fest(self):
        self.start("fest-two")
        other = self.add_team("Secret", slug="fest-two").json()["id"]
        assert self.place(self.vol_mid, {"committee_team_id": other}).status_code == 404

    def test_a_member_of_another_fest_is_not_found(self):
        self.start("fest-two")
        other = member_id("fest-two", "owner@test.com")
        assert self.place(other, {"title": "Hijack"}).status_code == 404

    def test_volunteers_cannot_place_anyone_not_even_themselves(self):
        assert self.place(self.vol_mid, {"title": "Boss"}, token=self.vol).status_code == 403

    def test_core_members_can_place_volunteers(self):
        assert self.place(self.vol_mid, {"title": "Gate lead"}, token=self.core).status_code == 200

    def test_only_the_director_or_an_admin_can_move_the_director(self):
        assert self.place(self.owner_mid, {"title": "Convenor"}, token=self.core).status_code == 403
        assert self.place(self.owner_mid, {"title": "Convenor"}, token=self.owner).status_code == 200
        assert self.place(self.owner_mid, {"title": "Festival director"}, token=self.admin).status_code == 200

    def test_removing_someone_clears_the_lead_of_those_who_reported_to_them(self):
        self.place(self.vol_mid, {"reports_to_id": self.core_mid})
        assert client.delete(f"/api/fests/fest-one/members/{user_id('core@test.com')}", headers=auth(self.owner)).status_code == 204
        vol = next(m for m in self.org().json()["members"] if m["id"] == self.vol_mid)
        assert vol["reports_to_id"] is None and vol["reports_to_name"] is None
