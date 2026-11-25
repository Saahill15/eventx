"""Team heads and co-heads, what a team's leaders may do, and joining a committee straight into a team."""

from test_fixes import user_token  # noqa: F401
from test_full import client, auth, reset_db, verify_student, TestingSessionLocal  # noqa: F401
from test_committee_structure import Committee, join, member_id
from app import models


class Crew(Committee):
    """The committee plus four more people, all volunteers, each with a sign-in."""

    def setup_method(self):
        super().setup_method()
        self.tok, self.mid = {}, {}
        for name in ("ann", "bob", "cat", "dev"):
            self.tok[name] = user_token(name.title(), f"{name}@test.com")
            self.mid[name] = join("fest-one", f"{name}@test.com", "volunteer")
        self.team = self.add_team("Sponsorship").json()
        self.pr = self.add_team("PR").json()

    def lead(self, team=None, token=None, **body):
        team = team or self.team
        return client.patch(f"/api/fests/fest-one/org/teams/{team['id']}", json=body, headers=auth(token or self.owner))

    def team_out(self, team=None):
        team = team or self.team
        return next(t for t in self.org().json()["teams"] if t["id"] == team["id"])

    def member(self, name):
        return next(m for m in self.org().json()["members"] if m["id"] == self.mid[name])

    def task(self, token, **body):
        return client.post("/api/fests/fest-one/tasks", json={"title": "Call sponsors", **body}, headers=auth(token))


class TestChoosingLeaders(Crew):
    def test_a_head_and_co_heads_can_be_chosen(self):
        r = self.lead(head_member_id=self.mid["ann"], co_head_member_ids=[self.mid["bob"], self.mid["cat"]])
        assert r.status_code == 200, r.text
        t = r.json()
        assert t["head"]["name"].startswith("Ann") and [c["name"].split()[0] for c in t["co_heads"]] == ["Bob", "Cat"] and t["member_count"] == 3
        assert self.member("ann")["team_role"] == "head" and self.member("bob")["team_role"] == "co_head"
        assert self.member("ann")["committee_team_id"] == self.team["id"]

    def test_a_new_team_has_no_leaders(self):
        t = self.team_out()
        assert t["head"] is None and t["co_heads"] == [] and t["leaders_manage_team"] is True

    def test_the_same_person_cannot_lead_twice(self):
        assert self.lead(head_member_id=self.mid["ann"], co_head_member_ids=[self.mid["ann"]]).status_code == 400
        assert self.lead(co_head_member_ids=[self.mid["bob"], self.mid["bob"]]).status_code == 400

    def test_at_most_three_co_heads(self):
        r = self.lead(co_head_member_ids=[self.mid[n] for n in ("ann", "bob", "cat", "dev")])
        assert r.status_code == 422

    def test_a_stranger_cannot_be_made_a_leader(self):
        assert self.lead(head_member_id=999999).status_code == 400

    def test_replacing_the_head_leaves_the_old_one_as_a_plain_member(self):
        self.lead(head_member_id=self.mid["ann"])
        self.lead(head_member_id=self.mid["bob"])
        assert self.member("ann")["team_role"] == "member" and self.member("ann")["committee_team_id"] == self.team["id"]
        assert self.team_out()["head"]["name"].startswith("Bob")

    def test_clearing_the_head_keeps_the_co_heads(self):
        self.lead(head_member_id=self.mid["ann"], co_head_member_ids=[self.mid["bob"]])
        t = self.lead(head_member_id=None).json()
        assert t["head"] is None and len(t["co_heads"]) == 1

    def test_choosing_someone_moves_them_out_of_their_old_team(self):
        self.lead(self.pr, head_member_id=self.mid["ann"])
        self.lead(head_member_id=self.mid["ann"])
        assert self.team_out(self.pr)["head"] is None and self.team_out(self.pr)["member_count"] == 0
        assert self.member("ann")["committee_team_id"] == self.team["id"]

    def test_only_the_core_team_chooses_leaders(self):
        assert self.lead(token=self.vol, head_member_id=self.mid["ann"]).status_code == 403
        assert self.lead(token=self.student, head_member_id=self.mid["ann"]).status_code == 403
        assert self.lead(token=self.core, head_member_id=self.mid["ann"]).status_code == 200

    def test_a_team_can_be_renamed_and_still_has_its_leaders(self):
        self.lead(head_member_id=self.mid["ann"])
        t = self.lead(name="Partnerships").json()
        assert t["name"] == "Partnerships" and t["head"]["name"].startswith("Ann")

    def test_deleting_a_team_sends_everyone_back_to_plain_members(self):
        self.lead(head_member_id=self.mid["ann"])
        client.delete(f"/api/fests/fest-one/org/teams/{self.team['id']}", headers=auth(self.owner))
        m = self.member("ann")
        assert m["committee_team_id"] is None and m["team_role"] == "member"


class TestAccessFollowsPosition(Crew):
    def test_the_director_can_give_the_head_core_access_in_the_same_step(self):
        self.lead(head_member_id=self.mid["ann"], co_head_member_ids=[self.mid["bob"]], give_core_access=True)
        assert self.member("ann")["role"] == "core"

    def test_co_heads_keep_the_access_they_have(self):
        self.lead(head_member_id=self.mid["ann"], co_head_member_ids=[self.mid["bob"]], give_core_access=True)
        assert self.member("bob")["role"] == "volunteer"

    def test_without_the_option_access_stays_as_it_was(self):
        self.lead(head_member_id=self.mid["ann"])
        assert self.member("ann")["role"] == "volunteer"

    def test_the_core_team_cannot_hand_out_core_access(self):
        self.lead(token=self.core, head_member_id=self.mid["ann"], give_core_access=True)
        assert self.member("ann")["role"] == "volunteer"

    def test_leaders_are_never_lowered(self):
        self.lead(head_member_id=self.core_mid, give_core_access=True)
        assert self.member_by_id(self.core_mid)["role"] == "core"
        self.lead(head_member_id=None)
        assert self.member_by_id(self.core_mid)["role"] == "core"

    def member_by_id(self, mid):
        return next(m for m in self.org().json()["members"] if m["id"] == mid)

    def test_a_volunteer_who_leads_still_has_volunteer_access(self):
        self.lead(head_member_id=self.mid["ann"])
        assert client.get("/api/fests/fest-one/manage", headers=auth(self.tok["ann"])).status_code == 403


class TestTheChartFillsItselfIn(Crew):
    def test_the_head_reports_to_the_director_and_the_team_reports_to_the_head(self):
        self.place(self.mid["cat"], {"committee_team_id": self.team["id"]})
        self.lead(head_member_id=self.mid["ann"], co_head_member_ids=[self.mid["bob"]])
        assert self.member("ann")["reports_to_id"] == self.owner_mid
        assert self.member("bob")["reports_to_id"] == self.mid["ann"]
        assert self.member("cat")["reports_to_id"] == self.mid["ann"]

    def test_someone_placed_in_a_team_later_reports_to_its_head(self):
        self.lead(head_member_id=self.mid["ann"])
        self.place(self.mid["dev"], {"committee_team_id": self.team["id"]})
        assert self.member("dev")["reports_to_id"] == self.mid["ann"]

    def test_an_existing_lead_is_not_overridden(self):
        self.place(self.mid["cat"], {"reports_to_id": self.core_mid})
        self.lead(head_member_id=self.mid["ann"], co_head_member_ids=[self.mid["cat"]])
        assert self.member("cat")["reports_to_id"] == self.core_mid

    def test_a_new_head_takes_over_the_team_from_the_old_one(self):
        self.lead(head_member_id=self.mid["ann"], co_head_member_ids=[self.mid["cat"]])
        self.lead(head_member_id=self.mid["bob"], co_head_member_ids=[self.mid["cat"]])
        assert self.member("cat")["reports_to_id"] == self.mid["bob"]

    def test_the_chart_never_loops(self):
        self.lead(head_member_id=self.mid["ann"], co_head_member_ids=[self.mid["bob"]])
        # Ann leads the team; making Bob (who reports to Ann) the head must not make Ann report to Bob and Bob to Ann
        self.lead(head_member_id=self.mid["bob"], co_head_member_ids=[self.mid["ann"]])
        by_id = {m["id"]: m for m in self.org().json()["members"]}
        seen, cur = set(), self.mid["ann"]
        while cur is not None:
            assert cur not in seen
            seen.add(cur)
            cur = by_id[cur]["reports_to_id"]


class TestPositionOnAPerson(Crew):
    def test_a_person_can_be_given_a_position_directly(self):
        r = self.place(self.mid["ann"], {"committee_team_id": self.team["id"], "team_role": "head"})
        assert r.status_code == 200 and r.json()["team_role"] == "head"

    def test_making_someone_head_makes_the_old_head_a_co_head(self):
        self.place(self.mid["ann"], {"committee_team_id": self.team["id"], "team_role": "head"})
        self.place(self.mid["bob"], {"committee_team_id": self.team["id"], "team_role": "head"})
        assert self.member("ann")["team_role"] == "co_head" and self.member("bob")["team_role"] == "head"

    def test_a_position_needs_a_team(self):
        assert self.place(self.mid["ann"], {"team_role": "head"}).status_code == 400

    def test_changing_position_inside_the_same_team(self):
        self.place(self.mid["ann"], {"committee_team_id": self.team["id"]})
        r = self.place(self.mid["ann"], {"team_role": "co_head"})
        assert r.json()["team_role"] == "co_head" and r.json()["committee_team_id"] == self.team["id"]

    def test_leaving_the_team_means_a_plain_member_again(self):
        self.place(self.mid["ann"], {"committee_team_id": self.team["id"], "team_role": "head"})
        r = self.place(self.mid["ann"], {"committee_team_id": None})
        assert r.json()["team_role"] == "member" and r.json()["committee_team_id"] is None

    def test_moving_to_another_team_drops_the_position(self):
        self.place(self.mid["ann"], {"committee_team_id": self.team["id"], "team_role": "head"})
        r = self.place(self.mid["ann"], {"committee_team_id": self.pr["id"]})
        assert r.json()["team_role"] == "member" and r.json()["committee_team_id"] == self.pr["id"]

    def test_an_unknown_position_is_refused(self):
        assert self.place(self.mid["ann"], {"team_role": "boss"}).status_code == 422


class TestWhatLeadersMayDo(Crew):
    def setup_method(self):
        super().setup_method()
        self.lead(head_member_id=self.mid["ann"], co_head_member_ids=[self.mid["bob"]])
        self.ann, self.bob = self.tok["ann"], self.tok["bob"]

    def test_a_head_and_a_co_head_can_describe_their_team(self):
        assert self.lead(token=self.ann, description="We find sponsors").status_code == 200
        assert self.lead(token=self.bob, description="We find sponsors, fast").json()["description"] == "We find sponsors, fast"

    def test_but_not_rename_it_or_choose_its_leaders_or_permissions(self):
        for body in ({"name": "Mine"}, {"head_member_id": self.mid["cat"]}, {"co_head_member_ids": []}, {"leaders_manage_team": False}):
            assert self.lead(token=self.ann, **body).status_code == 403

    def test_they_cannot_touch_another_team(self):
        assert self.lead(self.pr, token=self.ann, description="Mine now").status_code == 403

    def test_a_head_can_bring_someone_into_their_team_and_title_them(self):
        r = self.place(self.mid["cat"], {"committee_team_id": self.team["id"], "title": "Outreach"}, token=self.ann)
        assert r.status_code == 200 and r.json()["title"] == "Outreach" and r.json()["reports_to_id"] == self.mid["ann"]

    def test_a_head_can_send_a_member_out_of_their_team(self):
        self.place(self.mid["cat"], {"committee_team_id": self.team["id"]}, token=self.ann)
        assert self.place(self.mid["cat"], {"committee_team_id": None}, token=self.ann).status_code == 200

    def test_a_head_cannot_place_people_in_other_teams_or_take_people_from_them(self):
        assert self.place(self.mid["cat"], {"committee_team_id": self.pr["id"]}, token=self.ann).status_code == 403
        self.place(self.mid["dev"], {"committee_team_id": self.pr["id"]})
        assert self.place(self.mid["dev"], {"committee_team_id": self.team["id"]}, token=self.ann).status_code == 403

    def test_a_head_cannot_make_heads_or_remove_leaders(self):
        assert self.place(self.mid["cat"], {"committee_team_id": self.team["id"], "team_role": "co_head"}, token=self.ann).status_code == 403
        assert self.place(self.mid["bob"], {"committee_team_id": None}, token=self.ann).status_code == 403

    def test_a_head_cannot_move_the_director(self):
        assert self.place(self.owner_mid, {"title": "Boss"}, token=self.ann).status_code == 403

    def test_a_plain_member_of_the_team_has_no_such_powers(self):
        self.place(self.mid["cat"], {"committee_team_id": self.team["id"]})
        assert self.place(self.mid["dev"], {"committee_team_id": self.team["id"]}, token=self.tok["cat"]).status_code == 403
        assert self.lead(token=self.tok["cat"], description="x").status_code == 403

    def test_switching_the_permission_off_takes_the_powers_away(self):
        self.lead(leaders_manage_team=False)
        assert self.team_out()["leaders_manage_team"] is False
        assert self.lead(token=self.ann, description="x").status_code == 403
        assert self.place(self.mid["cat"], {"committee_team_id": self.team["id"]}, token=self.ann).status_code == 403
        assert self.task(self.ann, committee_team_id=self.team["id"]).status_code == 403

    def test_the_core_team_still_can_when_the_permission_is_off(self):
        self.lead(leaders_manage_team=False)
        assert self.lead(token=self.core, description="ok").status_code == 200

    def test_a_head_can_set_tasks_for_their_own_team(self):
        self.place(self.mid["cat"], {"committee_team_id": self.team["id"]})
        r = self.task(self.ann, committee_team_id=self.team["id"], assignee_member_id=self.mid["cat"])
        assert r.status_code == 201, r.text
        done = client.patch(f"/api/fests/fest-one/tasks/{r.json()['id']}", json={"title": "Call them all", "status": "doing"}, headers=auth(self.bob))
        assert done.status_code == 200 and done.json()["title"] == "Call them all"

    def test_but_not_for_another_team_or_for_people_outside_theirs(self):
        assert self.task(self.ann, committee_team_id=self.pr["id"]).status_code == 403
        assert self.task(self.ann).status_code == 403
        assert self.task(self.ann, committee_team_id=self.team["id"], assignee_member_id=self.mid["dev"]).status_code == 403

    def test_a_head_cannot_move_a_task_to_another_team(self):
        tid = self.task(self.ann, committee_team_id=self.team["id"]).json()["id"]
        r = client.patch(f"/api/fests/fest-one/tasks/{tid}", json={"committee_team_id": self.pr["id"]}, headers=auth(self.ann))
        assert r.status_code == 403

    def test_a_head_cannot_delete_tasks(self):
        tid = self.task(self.ann, committee_team_id=self.team["id"]).json()["id"]
        assert client.delete(f"/api/fests/fest-one/tasks/{tid}", headers=auth(self.ann)).status_code == 403


class TestJoiningIntoATeam(Crew):
    def setup_method(self):
        super().setup_method()
        self.slug = "fest-one"
        user_token("New", "new@test.com")
        self.new_tok = user_token("New2", "new2@test.com")
        verify_student("new@test.com"); verify_student("new2@test.com")

    def invite(self, email="new@test.com", token=None, **extra):
        return client.post(f"/api/fests/{self.slug}/members", json={"email": email, "role": "volunteer", **extra}, headers=auth(token or self.owner))

    def accept(self, invite, email="new@test.com"):
        from test_fixes import login
        return client.post(f"/api/fest-invites/{invite['id']}/accept", headers=auth(login(email)))

    def find(self, email):
        return next(m for m in self.org().json()["members"] if m["user_email"] == email)

    def test_an_invitation_can_name_the_team_and_position(self):
        r = self.invite(committee_team_id=self.team["id"], team_role="head")
        assert r.status_code == 201
        assert r.json()["team_name"] == "Sponsorship" and r.json()["team_role"] == "head"

    def test_accepting_puts_them_in_the_team_at_that_position(self):
        inv = self.invite(committee_team_id=self.team["id"], team_role="head").json()
        assert self.accept(inv).status_code == 200
        m = self.find("new@test.com")
        assert m["committee_team_id"] == self.team["id"] and m["team_role"] == "head" and m["reports_to_id"] == self.owner_mid

    def test_a_new_head_replaces_the_old_one_when_they_accept(self):
        self.lead(head_member_id=self.mid["ann"])
        self.accept(self.invite(committee_team_id=self.team["id"], team_role="head").json())
        assert self.member("ann")["team_role"] == "co_head"

    def test_the_invitation_notice_says_where_they_will_sit(self):
        self.invite(committee_team_id=self.team["id"], team_role="co_head")
        from test_fixes import login
        body = client.get("/api/users/me/account-notices", headers=auth(login("new@test.com"))).json()[0]["body"]
        assert "co-head of Sponsorship" in body

    def test_a_member_invitation_goes_into_the_team_as_a_member(self):
        self.lead(head_member_id=self.mid["ann"])
        self.accept(self.invite(committee_team_id=self.team["id"]).json())
        m = self.find("new@test.com")
        assert m["team_role"] == "member" and m["reports_to_id"] == self.mid["ann"]

    def test_an_invitation_without_a_team_still_works(self):
        self.accept(self.invite().json())
        assert self.find("new@test.com")["committee_team_id"] is None

    def test_a_leader_needs_a_team(self):
        assert self.invite(team_role="head").status_code == 422

    def test_the_team_must_belong_to_this_fest(self):
        assert self.invite(committee_team_id=987654).status_code == 400

    def test_a_team_deleted_before_they_accept_just_leaves_them_without_one(self):
        inv = self.invite(committee_team_id=self.team["id"], team_role="head").json()
        client.delete(f"/api/fests/fest-one/org/teams/{self.team['id']}", headers=auth(self.owner))
        self.accept(inv)
        m = self.find("new@test.com")
        assert m["committee_team_id"] is None and m["team_role"] == "member"

    def test_someone_already_on_the_committee_can_be_placed_by_adding_them_again(self):
        r = client.post("/api/fests/fest-one/members", json={"email": "ann@test.com", "role": "volunteer", "committee_team_id": self.team["id"], "team_role": "head"}, headers=auth(self.owner))
        assert r.status_code == 201 and r.json()["team_role"] == "head" and r.json()["committee_team_id"] == self.team["id"]

    def test_the_invitation_list_shows_the_team(self):
        self.invite(committee_team_id=self.team["id"], team_role="head")
        rows = client.get("/api/fests/fest-one/invites", headers=auth(self.owner)).json()
        assert rows[0]["team_name"] == "Sponsorship" and rows[0]["team_role"] == "head"


class TestOfficeBearers(TestJoiningIntoATeam):
    """Chairperson, Vice Chairperson, Treasurer: titles above the team heads, held by people who lead no team."""

    def test_an_invitation_can_carry_a_title(self):
        r = self.invite(role="core", title="Vice Chairperson")
        assert r.status_code == 201 and r.json()["title"] == "Vice Chairperson"

    def invite(self, email="new@test.com", token=None, **extra):
        body = {"email": email, "role": extra.pop("role", "volunteer"), **extra}
        return client.post(f"/api/fests/{self.slug}/members", json=body, headers=auth(token or self.owner))

    def test_accepting_gives_them_the_title_and_a_place_under_the_director(self):
        self.accept(self.invite(role="core", title="Vice Chairperson").json())
        m = self.find("new@test.com")
        assert m["title"] == "Vice Chairperson" and m["role"] == "core" and m["committee_team_id"] is None
        assert m["reports_to_id"] == self.owner_mid

    def test_a_volunteer_with_a_title_is_not_moved_in_the_chart(self):
        self.accept(self.invite(title="Photographer").json())
        m = self.find("new@test.com")
        assert m["title"] == "Photographer" and m["reports_to_id"] is None

    def test_a_core_member_who_heads_a_team_reports_to_the_head_chain_not_directly(self):
        self.lead(head_member_id=self.core_mid)
        assert self.member_by_id(self.core_mid)["reports_to_id"] == self.owner_mid

    def member_by_id(self, mid):
        return next(m for m in self.org().json()["members"] if m["id"] == mid)

    def test_the_notice_names_the_title(self):
        self.invite(role="core", title="Treasurer")
        from test_fixes import login
        body = client.get("/api/users/me/account-notices", headers=auth(login("new@test.com"))).json()[0]["body"]
        assert "Treasurer" in body

    def test_adding_a_current_member_again_can_change_their_title(self):
        r = client.post("/api/fests/fest-one/members", json={"email": "ann@test.com", "role": "volunteer", "title": "Chairperson"}, headers=auth(self.owner))
        assert r.status_code == 201 and r.json()["title"] == "Chairperson"

    def test_the_director_can_hold_a_title_too(self):
        r = self.place(self.owner_mid, {"title": "Chairperson"})
        assert r.status_code == 200 and r.json()["title"] == "Chairperson"

    def test_a_blank_title_clears_it(self):
        self.place(self.mid["ann"], {"title": "Treasurer"})
        assert self.place(self.mid["ann"], {"title": ""}).json()["title"] is None

    def test_a_long_title_is_refused(self):
        assert self.invite(role="core", title="x" * 81).status_code == 422
