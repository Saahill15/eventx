"""Team events (create a team, share the code, join, committee decides per team) and handing a fest to another organiser."""

from test_fixes import user_token, user_id  # noqa: F401
from test_full import client, auth, create_college, create_fest, get_entry_pass, reset_db, TestingSessionLocal  # noqa: F401
from app import models


def team_event_payload(fest_id, **kw):
    p = {"event_type": "fest", "title": "Hackathon", "date": "2026-12-01T10:00:00", "fest_id": fest_id, "location": "Lab 1",
         "time": "10:00", "end_time": "18:00", "description": "Build something.", "requires_registration": True,
         "is_team_event": True, "team_min": 2, "team_max": 3, "approval_mode": "auto"}
    p.update(kw)
    return p


class Setup:
    def setup_method(self):
        self.admin = user_token("Admin", "admin@test.com", "admin")
        self.college = create_college(self.admin)
        self.owner = user_token("Owner", "owner@test.com", "organizer")
        self.fest = create_fest(self.owner, self.college, slug="techfest")
        self.people = {n: user_token(n.title(), f"{n}@test.com") for n in ("ana", "ben", "cai", "dev")}
        for tok in self.people.values():
            get_entry_pass(tok, "techfest")

    def event(self, **kw):
        r = client.post("/api/events/", json=team_event_payload(self.fest["id"], **kw), headers=auth(self.owner))
        assert r.status_code == 200, r.text
        return r.json()

    def create(self, who, event_id, name="Bit Busters", **kw):
        return client.post(f"/api/fest-events/{event_id}/teams", json={"name": name, **kw}, headers=auth(self.people[who]))

    def join(self, who, code, **kw):
        return client.post("/api/fest-events/teams/join", json={"code": code, **kw}, headers=auth(self.people[who]))


class TestTeamSettings(Setup):
    def test_team_events_need_registration_and_sizes(self):
        base = team_event_payload(self.fest["id"])
        assert client.post("/api/events/", json={**base, "requires_registration": False}, headers=auth(self.owner)).status_code == 422
        assert client.post("/api/events/", json={**base, "team_max": None}, headers=auth(self.owner)).status_code == 422
        assert client.post("/api/events/", json={**base, "team_min": 4, "team_max": 3}, headers=auth(self.owner)).status_code == 422
        assert client.post("/api/events/", json={**base, "event_type": "city", "fest_id": None}, headers=auth(self.owner)).status_code == 422

    def test_sizes_are_locked_the_safe_way_once_teams_exist(self):
        ev = self.event()
        self.create("ana", ev["id"])
        assert client.patch(f"/api/events/{ev['id']}", json={"team_max": 2}, headers=auth(self.owner)).status_code == 400
        assert client.patch(f"/api/events/{ev['id']}", json={"is_team_event": False}, headers=auth(self.owner)).status_code == 400
        assert client.patch(f"/api/events/{ev['id']}", json={"team_max": 5}, headers=auth(self.owner)).status_code == 200


class TestTeams(Setup):
    def test_create_share_and_join(self):
        ev = self.event()
        t = self.create("ana", ev["id"]).json()
        assert t["i_am_leader"] and t["size"] == 1 and t["complete"] is False and len(t["code"]) == 6
        t = self.join("ben", t["code"].lower()).json()
        assert t["size"] == 2 and t["complete"] is True and t["status"] == "approved"
        mine = client.get(f"/api/fest-events/{ev['id']}/my-team", headers=auth(self.people["ben"])).json()
        assert mine["name"] == "Bit Busters" and mine["i_am_leader"] is False and [m["is_leader"] for m in mine["members"]] == [True, False]
        assert all(m["email"] is None for m in mine["members"])   # teammates do not see each other's email

    def test_teams_have_a_size_limit(self):
        ev = self.event()
        code = self.create("ana", ev["id"]).json()["code"]
        self.join("ben", code); self.join("cai", code)
        r = self.join("dev", code)
        assert r.status_code == 400 and "full" in r.json()["detail"]

    def test_one_registration_per_person(self):
        ev = self.event()
        code = self.create("ana", ev["id"]).json()["code"]
        assert self.create("ana", ev["id"], name="Other").status_code == 400
        assert self.join("ana", code).status_code == 400
        assert client.post(f"/api/fest-events/{ev['id']}/register", headers=auth(self.people["ben"])).status_code == 400   # team events need a team

    def test_names_are_unique_per_event_and_codes_must_exist(self):
        ev = self.event()
        self.create("ana", ev["id"])
        assert self.create("ben", ev["id"], name="bit busters").status_code == 400
        assert self.join("ben", "ZZZZZZ").status_code == 404

    def test_seat_limit_counts_teams(self):
        ev = self.event(registration_limit=1)
        code = self.create("ana", ev["id"]).json()["code"]
        assert self.join("ben", code).status_code == 200   # joining an existing team does not use a seat
        r = self.create("cai", ev["id"], name="Second")
        assert r.status_code == 400 and "full" in r.json()["detail"].lower()

    def test_manual_approval_is_per_team(self):
        ev = self.event(approval_mode="manual")
        t = self.create("ana", ev["id"]).json()
        self.join("ben", t["code"])
        assert t["status"] == "pending"
        teams = client.get(f"/api/fest-events/{ev['id']}/teams", headers=auth(self.owner)).json()
        assert teams[0]["members"][0]["email"] == "ana@test.com"   # the committee sees emails
        regs = client.get(f"/api/fest-events/{ev['id']}/registrations", headers=auth(self.owner)).json()
        assert {r["team_name"] for r in regs} == {"Bit Busters"} and sum(r["is_team_leader"] for r in regs) == 1
        assert client.post(f"/api/fest-events/registrations/{regs[0]['id']}/approve", headers=auth(self.owner)).status_code == 400
        out = client.post(f"/api/fest-events/teams/{t['id']}/approve", headers=auth(self.owner)).json()
        assert out["status"] == "approved" and all(m["approval_status"] == "approved" for m in out["members"])
        assert self.join("cai", t["code"]).json()["status"] == "approved"   # later members follow the team

    def test_rejected_teams_cannot_grow(self):
        ev = self.event(approval_mode="manual")
        t = self.create("ana", ev["id"]).json()
        client.post(f"/api/fest-events/teams/{t['id']}/reject", headers=auth(self.owner))
        assert self.join("ben", t["code"]).status_code == 400

    def test_only_the_committee_decides(self):
        ev = self.event(approval_mode="manual")
        t = self.create("ana", ev["id"]).json()
        assert client.post(f"/api/fest-events/teams/{t['id']}/approve", headers=auth(self.people["ana"])).status_code == 403
        assert client.get(f"/api/fest-events/{ev['id']}/teams", headers=auth(self.people["ana"])).status_code == 403

    def test_a_member_leaving_frees_their_place_and_a_leader_leaving_breaks_up_the_team(self):
        ev = self.event()
        t = self.create("ana", ev["id"]).json()
        self.join("ben", t["code"]); self.join("cai", t["code"])
        assert client.delete(f"/api/fest-events/{ev['id']}/register", headers=auth(self.people["cai"])).status_code == 204
        assert self.join("dev", t["code"]).status_code == 200
        assert client.delete(f"/api/fest-events/{ev['id']}/register", headers=auth(self.people["ana"])).status_code == 204
        assert client.get(f"/api/fest-events/{ev['id']}/my-team", headers=auth(self.people["ben"])).status_code == 404
        assert client.get(f"/api/fest-events/{ev['id']}/teams", headers=auth(self.owner)).json() == []

    def test_questions_are_answered_by_each_member(self):
        ev = self.event()
        client.put(f"/api/events/{ev['id']}/questions", json={"questions": [{"label": "T-shirt size", "kind": "choice", "required": True, "options": ["S", "M", "L"]}]}, headers=auth(self.owner))
        q = client.get(f"/api/events/{ev['id']}/questions").json()[0]["id"]
        assert self.create("ana", ev["id"]).status_code == 400   # the required question is missing
        t = self.create("ana", ev["id"], answers=[{"question_id": q, "value": "M"}]).json()
        assert self.join("ben", t["code"]).status_code == 400
        assert self.join("ben", t["code"], answers=[{"question_id": q, "value": "L"}]).status_code == 200

    def test_the_csv_shows_teams(self):
        ev = self.event()
        t = self.create("ana", ev["id"]).json()
        self.join("ben", t["code"])
        csv_text = client.get(f"/api/fest-events/{ev['id']}/registrations.csv", headers=auth(self.owner)).text
        assert "Team,Team leader" in csv_text.splitlines()[0] and "Bit Busters,yes" in csv_text and "Bit Busters,no" in csv_text

    def test_team_members_check_in_individually(self):
        ev = self.event()
        t = self.create("ana", ev["id"]).json()
        code = client.get("/api/fests/techfest/my-pass", headers=auth(self.people["ana"])).json()["qr_code"]
        r = client.post(f"/api/fest-events/{ev['id']}/check-in", json={"qr_code": code}, headers=auth(self.owner))
        assert r.status_code == 200 and r.json()["attended"] is True


class TestTransfers(Setup):
    def setup_method(self):
        super().setup_method()
        self.new = user_token("New Director", "new@test.com")
        client.post(f"/api/admin/users/{user_id('new@test.com')}/role", json={"role": "organizer", "college_ids": [self.college]}, headers=auth(self.admin))

    def offer(self, email="new@test.com", token=None, keep_me=True):
        return client.post("/api/fests/techfest/transfer", json={"email": email, "keep_me": keep_me}, headers=auth(token or self.owner))

    def role_of(self, email):
        db = TestingSessionLocal()
        uid = db.query(models.User).filter(models.User.email == email).first().id
        m = db.query(models.FestMember).filter(models.FestMember.user_id == uid).first()
        db.close()
        return m.role.value if m else None

    def test_offer_accept_and_the_old_director_stays_as_core(self):
        t = self.offer().json()
        assert t["status"] == "pending" and t["to_email"] == "new@test.com"
        assert self.role_of("new@test.com") is None   # nothing changes until they accept
        mine = client.get("/api/users/me/fest-transfers", headers=auth(self.new)).json()
        assert [x["fest_name"] for x in mine] == ["TechFest 2026"]
        r = client.post(f"/api/fest-transfers/{t['id']}/accept", headers=auth(self.new))
        assert r.status_code == 200 and r.json()["status"] == "accepted"
        assert (self.role_of("new@test.com"), self.role_of("owner@test.com")) == ("owner", "core")

    def test_the_old_director_can_choose_to_leave(self):
        t = self.offer(keep_me=False).json()
        client.post(f"/api/fest-transfers/{t['id']}/accept", headers=auth(self.new))
        assert self.role_of("owner@test.com") is None

    def test_decline_and_withdraw(self):
        t = self.offer().json()
        assert client.post(f"/api/fest-transfers/{t['id']}/decline", headers=auth(self.new)).json()["status"] == "declined"
        assert self.role_of("owner@test.com") == "owner"
        self.offer()
        assert client.delete("/api/fests/techfest/transfer", headers=auth(self.owner)).json()["status"] == "cancelled"
        assert client.get("/api/fests/techfest/transfer", headers=auth(self.owner)).json() is None

    def test_only_the_director_can_offer_and_only_the_recipient_can_answer(self):
        assert self.offer(token=self.people["ana"]).status_code == 403
        t = self.offer().json()
        assert client.post(f"/api/fest-transfers/{t['id']}/accept", headers=auth(self.people["ana"])).status_code == 404
        assert client.post(f"/api/fest-transfers/{t['id']}/accept", headers=auth(self.owner)).status_code == 404

    def test_the_new_director_must_be_an_organiser_for_the_college(self):
        assert self.offer("ana@test.com").status_code == 400          # not an organiser
        assert self.offer("ghost@test.com").status_code == 404        # no account
        assert self.offer("owner@test.com").status_code == 400        # already runs it
        other_college = client.post("/api/colleges/", json={"name": "Other College", "partner_status": "partner"}, headers=auth(self.admin)).json()["id"]
        client.put(f"/api/admin/users/{user_id('new@test.com')}/colleges", json={"college_ids": [other_college]}, headers=auth(self.admin))
        r = self.offer()
        assert r.status_code == 400 and "not set up for" in r.json()["detail"]

    def test_accepting_checks_the_recipient_again(self):
        t = self.offer().json()
        other_college = client.post("/api/colleges/", json={"name": "Other College", "partner_status": "partner"}, headers=auth(self.admin)).json()["id"]
        client.put(f"/api/admin/users/{user_id('new@test.com')}/colleges", json={"college_ids": [other_college]}, headers=auth(self.admin))
        r = client.post(f"/api/fest-transfers/{t['id']}/accept", headers=auth(self.new))
        assert r.status_code == 400 and "not set up for" in r.json()["detail"]
        assert self.role_of("owner@test.com") == "owner"

    def test_answered_offers_are_final(self):
        t = self.offer().json()
        client.post(f"/api/fest-transfers/{t['id']}/decline", headers=auth(self.new))
        assert client.post(f"/api/fest-transfers/{t['id']}/accept", headers=auth(self.new)).status_code == 400

    def test_a_new_offer_replaces_the_old_one(self):
        first = self.offer().json()
        third = user_token("Third", "third@test.com")
        client.post(f"/api/admin/users/{user_id('third@test.com')}/role", json={"role": "organizer", "college_ids": [self.college]}, headers=auth(self.admin))
        self.offer("third@test.com")
        assert client.post(f"/api/fest-transfers/{first['id']}/accept", headers=auth(self.new)).status_code == 400
        assert len(client.get("/api/users/me/fest-transfers", headers=auth(third)).json()) == 1

    def test_the_director_can_be_demoted_after_handing_over(self):
        t = self.offer(keep_me=False).json()
        client.post(f"/api/fest-transfers/{t['id']}/accept", headers=auth(self.new))
        r = client.post(f"/api/admin/users/{user_id('owner@test.com')}/role", json={"role": "user"}, headers=auth(self.admin))
        assert r.status_code == 200

    def test_admins_can_move_a_fest_at_once(self):
        self.offer()
        r = client.post("/api/admin/fests/techfest/owner", json={"email": "new@test.com", "keep_previous_owner": False}, headers=auth(self.admin))
        assert r.status_code == 200
        assert (self.role_of("new@test.com"), self.role_of("owner@test.com")) == ("owner", None)
        assert client.get("/api/fests/techfest/transfer", headers=auth(self.new)).json() is None   # the open offer was withdrawn
        assert client.post("/api/admin/fests/techfest/owner", json={"email": "new@test.com"}, headers=auth(self.owner)).status_code == 403
