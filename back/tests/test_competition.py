"""The competition between colleges: points, CL meets, the name auction, event results, penalties, awards and the leaderboard."""

from datetime import datetime, timedelta

from test_fixes import user_token  # noqa: F401
from test_full import client, auth, reset_db, TestingSessionLocal  # noqa: F401
from test_contingents import Visiting
from test_organiser import event_payload
from app import models

SLUG = "fest-one"


def when(days=1):
    return (datetime.now() + timedelta(days=days)).replace(microsecond=0).isoformat()


class Arena(Visiting):
    """A live fest taking visiting colleges, with three approved contingents from three colleges."""

    def setup_method(self):
        super().setup_method()
        self.settings(allow_multiple_per_college=True)
        self.cl3 = user_token("Leader Three", "cl3@test.com")
        self.tok = {"A": self.cl, "B": self.cl2, "C": self.cl3}
        self.ids = {}
        for key, college in (("A", "IIT Delhi"), ("B", "NIT Surat"), ("C", "BITS Pilani")):
            self.ids[key] = self.approved(self.tok[key], college)

    def approved(self, token, college):
        r = self.register(token, college)
        assert r.status_code == 201, r.text
        cid = r.json()["id"]
        assert self.go("POST", f"/{cid}/approve").status_code == 200
        return cid

    # ── shorthands ──
    def c(self, method, path, token=None, **kw):
        return client.request(method, f"/api/fests/{SLUG}/competition{path}", headers=auth(token or self.owner), **kw)

    def m(self, method, path, token=None, **kw):
        return client.request(method, f"/api/fests/{SLUG}/cl-meets{path}", headers=auth(token or self.owner), **kw)

    def a(self, method, path, token=None, **kw):
        return client.request(method, f"/api/fests/{SLUG}/auctions{path}", headers=auth(token or self.owner), **kw)

    def board(self, token=None):
        r = self.c("GET", "/leaderboard", token)
        assert r.status_code == 200, r.text
        return r.json()

    def balance(self, key):
        return next(r["balance"] for r in self.board()["contingents"] if r["contingent_id"] == self.ids[key])

    def rank(self, key):
        return next(r["rank"] for r in self.board()["contingents"] if r["contingent_id"] == self.ids[key])

    def adjust(self, key, points, reason="Correction"):
        r = self.c("POST", "/adjustments", json={"contingent_id": self.ids[key], "points": points, "reason": reason})
        assert r.status_code == 201, r.text

    def meet(self, title="CL meet 1"):
        r = self.m("POST", "", json={"title": title, "starts_at": when(3), "location": "Hall 2"})
        assert r.status_code == 201, r.text
        return r.json()

    def task(self, meet_id, title="Quiz", **extra):
        r = self.m("POST", f"/{meet_id}/tasks", json={"title": title, **extra})
        assert r.status_code == 201, r.text
        return r.json()

    def award_task(self, meet_id, task_id, awards, token=None):
        return self.m("PUT", f"/{meet_id}/tasks/{task_id}/result", token, json={"awards": [{"contingent_id": self.ids[k], "points": p} for k, p in awards]})

    def auction(self, names=(("Phoenix", "PHX"), ("Titans", "TTN")), open_it=True, **extra):
        r = self.a("POST", "", json={"title": "Name auction", **extra})
        assert r.status_code == 201, r.text
        aid = r.json()["id"]
        for name, code in names:
            assert self.a("POST", f"/{aid}/names", json={"name": name, "code": code}).status_code == 201
        if open_it:
            assert self.a("POST", f"/{aid}/open").status_code == 200
        return self.a("GET", "").json()[-1]

    def bid(self, auction, name_index, key, amount, token=None, staff=False):
        nid = auction["names"][name_index]["id"]
        body = {"amount": amount}
        if staff:
            body["contingent_id"] = self.ids[key]
        return client.put(f"/api/fests/{SLUG}/auctions/{auction['id']}/names/{nid}/bid", json=body, headers=auth(token or self.tok[key]))

    def scored_event(self, scheme=None, **extra):
        fest = client.get(f"/api/fests/{SLUG}/manage", headers=auth(self.owner)).json()
        r = client.post("/api/events/", json=event_payload(fest["id"], points_scheme=scheme or {"1": 100, "2": 60, "3": 30}, **extra), headers=auth(self.owner))
        assert r.status_code == 200, r.text
        return r.json()

    def results(self, event_id, placed, token=None):
        body = {"results": [{"contingent_id": self.ids[k], "place": p} for k, p in placed]}
        return self.c("PUT", f"/events/{event_id}/results", token, json=body)


# ─── settings and balances ───────────────────────────────────────────────────

class TestSettingsAndBalances(Arena):
    def test_every_contingent_starts_with_the_default_points(self):
        assert [r["balance"] for r in self.board()["contingents"]] == [500, 500, 500]

    def test_the_committee_can_change_the_starting_points(self):
        r = self.c("PUT", "/settings", json={"starting_points": 800})
        assert r.status_code == 200 and r.json()["starting_points"] == 800
        assert self.balance("A") == 800

    def test_defaults(self):
        s = self.c("GET", "/settings").json()
        assert s["starting_points"] == 500 and s["ranking_basis"] == "total" and s["public_leaderboard"] is False and s["default_placing_points"] == [100, 60, 30]

    def test_only_the_committee_can_see_or_change_them(self):
        assert self.c("GET", "/settings", self.cl).status_code == 403
        assert self.c("PUT", "/settings", self.cl, json={"starting_points": 1}).status_code == 403
        assert self.c("PUT", "/settings", self.admin, json={"starting_points": 600}).status_code == 200

    def test_bad_settings_are_refused(self):
        assert self.c("PUT", "/settings", json={"starting_points": -5}).status_code == 422
        assert self.c("PUT", "/settings", json={"ranking_basis": "vibes"}).status_code == 422
        assert self.c("PUT", "/settings", json={"default_placing_points": [1] * 11}).status_code == 422

    def test_only_approved_contingents_take_part(self):
        pending = self.register(self.stranger, "IIT Madras").json()["id"]
        ids = [r["contingent_id"] for r in self.board()["contingents"]]
        assert pending not in ids
        assert self.c("POST", "/adjustments", json={"contingent_id": pending, "points": 5, "reason": "Nope"}).status_code == 400

    def test_the_committee_can_adjust_points_with_a_reason(self):
        self.adjust("A", 40, "Helped set up")
        self.adjust("A", -10, "Late")
        assert self.balance("A") == 530
        ledger = self.c("GET", f"/ledger?contingent_id={self.ids['A']}").json()
        assert [(e["points"], e["kind"]) for e in ledger] == [(-10, "adjustment"), (40, "adjustment")]

    def test_an_adjustment_needs_points_and_a_reason(self):
        assert self.c("POST", "/adjustments", json={"contingent_id": self.ids["A"], "points": 0, "reason": "none"}).status_code == 422
        assert self.c("POST", "/adjustments", json={"contingent_id": self.ids["A"], "points": 5, "reason": "x"}).status_code == 422

    def test_only_the_committee_can_adjust(self):
        assert self.c("POST", "/adjustments", self.cl, json={"contingent_id": self.ids["A"], "points": 999, "reason": "Cheating"}).status_code == 403
        assert self.balance("A") == 500


class TestStandings(Arena):
    def test_ranked_by_balance_best_first(self):
        self.adjust("B", 100); self.adjust("C", 50)
        rows = self.board()["contingents"]
        assert [r["contingent_id"] for r in rows] == [self.ids["B"], self.ids["C"], self.ids["A"]]
        assert [r["rank"] for r in rows] == [1, 2, 3]

    def test_equal_scores_share_a_rank_and_the_next_skips(self):
        self.adjust("A", 100); self.adjust("B", 100)
        assert [self.rank(k) for k in "ABC"] == [1, 1, 3]

    def test_the_breakdown_says_where_points_came_from(self):
        self.adjust("A", 25)
        row = next(r for r in self.board()["contingents"] if r["contingent_id"] == self.ids["A"])
        assert row["breakdown"]["adjustments"] == 25 and row["starting_points"] == 500

    def test_ranking_can_count_only_what_events_earned(self):
        self.c("PUT", "/settings", json={"ranking_basis": "events"})
        self.adjust("A", 300)  # a meet bonus does not count toward an events-only ranking
        e = self.scored_event()
        self.results(e["id"], [("B", 1), ("C", 2)])
        assert [self.rank(k) for k in "ABC"] == [3, 1, 2]
        assert self.balance("A") == 800  # the points themselves are still all there

    def test_colleges_add_up_all_their_contingents(self):
        a2 = self.approved(self.stranger, "IIT Delhi")  # a second contingent of the same college
        self.ids["A2"] = a2
        self.adjust("A", 50); self.adjust("A2", 50)
        colleges = self.board()["colleges"]
        top = colleges[0]
        assert top["college_name"] == "IIT Delhi" and top["contingents"] == 2 and top["score"] == 1100 and top["rank"] == 1
        assert [c["rank"] for c in colleges] == [1, 2, 2]  # the other two tie on 500


# ─── CL meets ────────────────────────────────────────────────────────────────

class TestClMeets(Arena):
    def test_the_committee_schedules_a_meet_with_tasks(self):
        m = self.meet()
        t = self.task(m["id"], "Treasure hunt", description="Find the clues", placing_points=[200, 100, 50])
        assert t["placing_points"] == [200, 100, 50]
        got = self.m("GET", "").json()
        assert got[0]["title"] == "CL meet 1" and got[0]["tasks"][0]["title"] == "Treasure hunt"

    def test_there_can_be_more_than_one_meet(self):
        self.meet("CL meet 1"); self.meet("CL meet 2")
        assert [m["title"] for m in self.m("GET", "").json()] == ["CL meet 1", "CL meet 2"]

    def test_winning_a_task_adds_points(self):
        m = self.meet(); t = self.task(m["id"])
        r = self.award_task(m["id"], t["id"], [("A", 200), ("B", 100)])
        assert r.status_code == 200 and [x["points"] for x in r.json()["results"]] == [200, 100]
        assert self.balance("A") == 700 and self.balance("B") == 600 and self.balance("C") == 500

    def test_sending_a_result_again_replaces_it(self):
        m = self.meet(); t = self.task(m["id"])
        self.award_task(m["id"], t["id"], [("A", 200)])
        self.award_task(m["id"], t["id"], [("B", 200)])
        assert self.balance("A") == 500 and self.balance("B") == 700

    def test_a_task_can_cost_points_too(self):
        m = self.meet(); t = self.task(m["id"], "Forfeit")
        self.award_task(m["id"], t["id"], [("A", -50)])
        assert self.balance("A") == 450

    def test_a_contingent_can_only_appear_once_in_a_result(self):
        m = self.meet(); t = self.task(m["id"])
        assert self.award_task(m["id"], t["id"], [("A", 10), ("A", 20)]).status_code == 400

    def test_only_approved_contingents_can_be_awarded(self):
        m = self.meet(); t = self.task(m["id"])
        pending = self.register(self.stranger, "IIT Madras").json()["id"]
        r = self.m("PUT", f"/{m['id']}/tasks/{t['id']}/result", json={"awards": [{"contingent_id": pending, "points": 5}]})
        assert r.status_code == 400

    def test_deleting_a_task_takes_its_points_back(self):
        m = self.meet(); t = self.task(m["id"])
        self.award_task(m["id"], t["id"], [("A", 200)])
        assert self.m("DELETE", f"/{m['id']}/tasks/{t['id']}").status_code == 204
        assert self.balance("A") == 500

    def test_deleting_a_meet_takes_all_its_points_back(self):
        m = self.meet(); t = self.task(m["id"]); t2 = self.task(m["id"], "Second")
        self.award_task(m["id"], t["id"], [("A", 200)]); self.award_task(m["id"], t2["id"], [("A", 50)])
        assert self.m("DELETE", f"/{m['id']}").status_code == 204
        assert self.balance("A") == 500 and self.m("GET", "").json() == []

    def test_attendance_is_recorded_and_replaced(self):
        m = self.meet()
        r = self.m("PUT", f"/{m['id']}/attendance", json={"contingent_ids": [self.ids["A"], self.ids["B"]]})
        assert r.status_code == 200 and r.json()["attended"] == sorted([self.ids["A"], self.ids["B"]])
        r = self.m("PUT", f"/{m['id']}/attendance", json={"contingent_ids": [self.ids["C"]]})
        assert r.json()["attended"] == [self.ids["C"]]

    def test_a_meet_and_task_can_be_edited(self):
        m = self.meet(); t = self.task(m["id"])
        assert self.m("PATCH", f"/{m['id']}", json={"title": "Final CL meet", "location": "Main hall"}).json()["title"] == "Final CL meet"
        assert self.m("PATCH", f"/{m['id']}/tasks/{t['id']}", json={"title": "Quiz night", "placing_points": [100]}).json()["placing_points"] == [100]

    def test_only_the_committee_runs_meets(self):
        for token in (self.cl, self.student, self.stranger):
            assert self.m("GET", "", token).status_code == 403
            assert self.m("POST", "", token, json={"title": "x", "starts_at": when()}).status_code == 403
        m = self.meet(); t = self.task(m["id"])
        assert self.award_task(m["id"], t["id"], [("A", 999)], token=self.cl).status_code == 403
        assert self.balance("A") == 500

    def test_a_meet_of_another_fest_is_not_reachable(self):
        m = self.meet()
        self.start("fest-two")
        assert client.delete(f"/api/fests/fest-two/cl-meets/{m['id']}", headers=auth(self.owner)).status_code == 404


# ─── the name auction ────────────────────────────────────────────────────────

class TestNameAuction(Arena):
    def test_the_founders_example(self):
        """500 points, 200 won at the meet, then 600 bid for a name: 100 left."""
        m = self.meet(); t = self.task(m["id"])
        self.award_task(m["id"], t["id"], [("A", 200)])
        assert self.balance("A") == 700
        au = self.auction()
        assert self.bid(au, 0, "A", 600).status_code == 200
        done = self.a("POST", f"/{au['id']}/close").json()
        assert done["status"] == "closed" and done["names"][0]["winner_contingent_id"] == self.ids["A"] and done["names"][0]["winning_bid"] == 600
        assert self.balance("A") == 100

    def test_the_winner_gets_the_name_and_the_code(self):
        au = self.auction()
        self.bid(au, 0, "A", 300)
        self.a("POST", f"/{au['id']}/close")
        mine = self.go("GET", f"/{self.ids['A']}").json()
        assert mine["name"] == "Phoenix" and mine["code"] == "PHX"

    def test_only_the_winning_bid_is_paid(self):
        au = self.auction()
        self.bid(au, 0, "A", 300); self.bid(au, 0, "B", 450); self.bid(au, 0, "C", 100)
        self.a("POST", f"/{au['id']}/close")
        assert (self.balance("A"), self.balance("B"), self.balance("C")) == (500, 50, 500)

    def test_bids_on_several_names_cost_nothing_until_one_wins(self):
        au = self.auction()
        self.bid(au, 0, "A", 400); self.bid(au, 1, "A", 400)
        assert self.balance("A") == 500

    def test_a_contingent_wins_at_most_one_name(self):
        au = self.auction()
        self.bid(au, 0, "A", 450); self.bid(au, 1, "A", 400); self.bid(au, 1, "B", 200)
        done = self.a("POST", f"/{au['id']}/close").json()
        by_name = {n["name"]: (n["winner_contingent_id"], n["winning_bid"]) for n in done["names"]}
        assert by_name["Phoenix"] == (self.ids["A"], 450) and by_name["Titans"] == (self.ids["B"], 200)
        assert self.balance("A") == 50 and self.balance("B") == 300

    def test_the_biggest_bid_overall_is_settled_first(self):
        au = self.auction()
        self.bid(au, 0, "A", 300); self.bid(au, 1, "A", 480)
        done = self.a("POST", f"/{au['id']}/close").json()
        assert {n["name"]: n["winner_contingent_id"] for n in done["names"]} == {"Phoenix": None, "Titans": self.ids["A"]}

    def test_a_tie_goes_to_whoever_bid_first(self):
        au = self.auction()
        self.bid(au, 0, "B", 250); self.bid(au, 0, "A", 250)
        done = self.a("POST", f"/{au['id']}/close").json()
        assert done["names"][0]["winner_contingent_id"] == self.ids["B"]

    def test_a_name_nobody_bid_on_stays_unsold(self):
        au = self.auction()
        self.bid(au, 0, "A", 100)
        done = self.a("POST", f"/{au['id']}/close").json()
        assert done["names"][1]["winner_contingent_id"] is None

    def test_the_smallest_bid_and_the_balance_are_enforced(self):
        au = self.auction(min_bid=50)
        assert self.bid(au, 0, "A", 49).status_code == 400
        assert self.bid(au, 0, "A", 501).status_code == 400
        assert self.bid(au, 0, "A", 500).status_code == 200

    def test_a_leader_can_only_raise_a_bid_or_withdraw_it(self):
        au = self.auction()
        self.bid(au, 0, "A", 200)
        assert self.bid(au, 0, "A", 150).status_code == 400
        assert self.bid(au, 0, "A", 260).status_code == 200
        nid = au["names"][0]["id"]
        assert client.delete(f"/api/fests/{SLUG}/auctions/{au['id']}/names/{nid}/bid", headers=auth(self.cl)).status_code == 200
        assert self.a("GET", "").json()[0]["names"][0]["bids"] == []

    def test_the_committee_can_bid_for_a_contingent_at_the_meet_and_change_it_freely(self):
        au = self.auction()
        assert self.bid(au, 0, "A", 300, token=self.owner, staff=True).status_code == 200
        assert self.bid(au, 0, "A", 100, token=self.owner, staff=True).status_code == 200
        assert self.a("GET", "").json()[0]["names"][0]["bids"][0]["amount"] == 100

    def test_a_leader_cannot_bid_for_someone_else(self):
        au = self.auction()
        r = client.put(f"/api/fests/{SLUG}/auctions/{au['id']}/names/{au['names'][0]['id']}/bid", json={"amount": 10, "contingent_id": self.ids["B"]}, headers=auth(self.cl))
        assert r.status_code == 403

    def test_strangers_cannot_bid(self):
        au = self.auction()
        assert client.put(f"/api/fests/{SLUG}/auctions/{au['id']}/names/{au['names'][0]['id']}/bid", json={"amount": 10}, headers=auth(self.student)).status_code == 403

    def test_no_bidding_before_it_opens_or_after_it_closes(self):
        au = self.auction(open_it=False)
        assert self.bid(au, 0, "A", 10).status_code == 400
        self.a("POST", f"/{au['id']}/open")
        self.a("POST", f"/{au['id']}/close")
        assert self.bid(au, 0, "A", 10).status_code == 400

    def test_a_disqualified_contingent_cannot_bid(self):
        self.c("POST", "/penalties", json={"contingent_id": self.ids["A"], "disqualified": True, "reason": "Cheating"})
        au = self.auction()
        assert self.bid(au, 0, "A", 10).status_code == 400

    def test_a_bid_it_can_no_longer_afford_is_ignored_at_the_close(self):
        au = self.auction()
        self.bid(au, 0, "A", 450); self.bid(au, 0, "B", 200)
        self.c("POST", "/penalties", json={"contingent_id": self.ids["A"], "points": 200, "reason": "Late"})
        done = self.a("POST", f"/{au['id']}/close").json()
        assert done["names"][0]["winner_contingent_id"] == self.ids["B"]

    def test_reopening_undoes_the_close(self):
        au = self.auction()
        self.bid(au, 0, "A", 300)
        self.a("POST", f"/{au['id']}/close")
        assert self.balance("A") == 200
        r = self.a("POST", f"/{au['id']}/reopen").json()
        assert r["status"] == "open" and r["names"][0]["winner_contingent_id"] is None
        assert self.balance("A") == 500 and self.go("GET", f"/{self.ids['A']}").json()["name"] is None

    def test_a_name_already_worn_by_another_contingent_blocks_the_close(self):
        self.go("PATCH", f"/{self.ids['B']}/assign", json={"name": "Phoenix"})
        au = self.auction()
        self.bid(au, 0, "A", 300)
        r = self.a("POST", f"/{au['id']}/close")
        assert r.status_code == 400 and "Phoenix" in r.json()["detail"]
        assert self.balance("A") == 500

    def test_leaders_see_only_their_own_bids_when_it_is_sealed(self):
        au = self.auction()
        self.bid(au, 0, "A", 300); self.bid(au, 0, "B", 450)
        mine = self.c("GET", "/mine", self.cl).json()["auctions"][0]["names"][0]
        assert mine["my_bid"] == 300 and mine["top_bid"] is None

    def test_leaders_see_the_top_bid_when_the_auction_shows_it(self):
        au = self.auction(show_highest_bid=True)
        self.bid(au, 0, "A", 300); self.bid(au, 0, "B", 450)
        assert self.c("GET", "/mine", self.cl).json()["auctions"][0]["names"][0]["top_bid"] == 450

    def test_draft_auctions_are_hidden_from_leaders(self):
        self.auction(open_it=False)
        assert self.c("GET", "/mine", self.cl).json()["auctions"] == []

    def test_an_auction_needs_a_name_to_open_and_cannot_repeat_one(self):
        r = self.a("POST", "", json={"title": "Empty"}).json()
        assert self.a("POST", f"/{r['id']}/open").status_code == 400
        self.a("POST", f"/{r['id']}/names", json={"name": "Phoenix", "code": "PHX"})
        assert self.a("POST", f"/{r['id']}/names", json={"name": "phoenix"}).status_code == 400
        assert self.a("POST", f"/{r['id']}/names", json={"name": "Other", "code": "phx"}).status_code == 400

    def test_a_closed_auction_cannot_be_deleted_until_reopened(self):
        au = self.auction()
        self.bid(au, 0, "A", 300); self.a("POST", f"/{au['id']}/close")
        assert self.a("DELETE", f"/{au['id']}").status_code == 400
        self.a("POST", f"/{au['id']}/reopen")
        assert self.a("DELETE", f"/{au['id']}").status_code == 204

    def test_only_the_committee_runs_an_auction(self):
        assert self.a("POST", "", self.cl, json={"title": "x"}).status_code == 403
        au = self.auction()
        assert self.a("POST", f"/{au['id']}/close", self.cl).status_code == 403
        assert self.a("GET", "", self.cl).status_code == 403


# ─── event results, rules and penalties ──────────────────────────────────────

class TestEventResults(Arena):
    def test_placing_in_an_event_adds_that_places_points(self):
        e = self.scored_event()
        r = self.results(e["id"], [("A", 1), ("B", 2), ("C", 3)])
        assert r.status_code == 200 and [x["points"] for x in r.json()["results"]] == [100, 60, 30]
        assert (self.balance("A"), self.balance("B"), self.balance("C")) == (600, 560, 530)

    def test_correcting_a_result_replaces_the_points(self):
        e = self.scored_event()
        self.results(e["id"], [("A", 1), ("B", 2)])
        self.results(e["id"], [("B", 1), ("A", 2)])
        assert (self.balance("A"), self.balance("B")) == (560, 600)

    def test_a_place_with_no_points_earns_nothing(self):
        e = self.scored_event({"1": 100})
        self.results(e["id"], [("A", 1), ("B", 2)])
        assert self.balance("B") == 500

    def test_ties_share_a_place(self):
        e = self.scored_event()
        self.results(e["id"], [("A", 1), ("B", 1)])
        assert self.balance("A") == 600 and self.balance("B") == 600

    def test_an_unscored_event_cannot_take_results(self):
        fest = client.get(f"/api/fests/{SLUG}/manage", headers=auth(self.owner)).json()
        e = client.post("/api/events/", json=event_payload(fest["id"]), headers=auth(self.owner)).json()
        assert self.results(e["id"], [("A", 1)]).status_code == 400

    def test_a_contingent_appears_once_and_must_be_taking_part(self):
        e = self.scored_event()
        assert self.results(e["id"], [("A", 1), ("A", 2)]).status_code == 400
        pending = self.register(self.stranger, "IIT Madras").json()["id"]
        assert self.c("PUT", f"/events/{e['id']}/results", json={"results": [{"contingent_id": pending, "place": 1}]}).status_code == 400

    def test_an_event_of_another_fest_is_not_reachable(self):
        self.start("fest-two")
        assert client.put("/api/fests/fest-two/competition/events/1/results", json={"results": []}, headers=auth(self.owner)).status_code in (400, 404)

    def test_only_the_committee_records_results(self):
        e = self.scored_event()
        assert self.results(e["id"], [("A", 1)], token=self.cl).status_code == 403
        assert self.balance("A") == 500

    def test_the_scored_events_are_listed_with_their_results(self):
        e = self.scored_event(title="Battle of Bands")
        self.results(e["id"], [("A", 1)])
        listed = self.c("GET", "/events").json()
        assert listed[0]["title"] == "Battle of Bands" and listed[0]["results"][0]["place"] == 1

    def test_the_points_for_an_event_can_be_set_and_cleared(self):
        e = self.scored_event()
        assert e["points_scheme"] == {"1": 100, "2": 60, "3": 30}
        r = client.patch(f"/api/events/{e['id']}", json={"points_scheme": {"1": 150}}, headers=auth(self.owner))
        assert r.status_code == 200 and r.json()["points_scheme"] == {"1": 150}

    def test_bad_points_are_refused(self):
        fest = client.get(f"/api/fests/{SLUG}/manage", headers=auth(self.owner)).json()
        for bad in ({}, {"0": 10}, {"1": -5}, {"1": 99999}, {"x": 1}):
            assert client.post("/api/events/", json=event_payload(fest["id"], points_scheme=bad), headers=auth(self.owner)).status_code == 422


class TestRulesAndPenalties(Arena):
    def rule(self, **extra):
        r = self.c("POST", "/rules", json={"title": "Late arrival", "penalty_points": 20, **extra})
        assert r.status_code == 201, r.text
        return r.json()

    def test_a_rule_says_what_breaking_it_costs(self):
        r = self.rule(description="Be there on time", disqualifies=False)
        assert r["penalty_points"] == 20 and r["disqualifies"] is False
        assert [x["title"] for x in self.c("GET", "/rules").json()] == ["Late arrival"]

    def test_a_rule_can_belong_to_one_event(self):
        e = self.scored_event(title="Quiz")
        assert self.rule(event_id=e["id"])["event_title"] == "Quiz"

    def test_applying_a_rule_takes_its_points_and_gives_its_reason(self):
        rule = self.rule()
        r = self.c("POST", "/penalties", json={"contingent_id": self.ids["A"], "rule_id": rule["id"]})
        assert r.status_code == 201 and r.json()["points"] == 20 and r.json()["reason"] == "Late arrival" and r.json()["disqualified"] is False
        assert self.balance("A") == 480

    def test_the_committee_can_override_what_the_rule_says(self):
        rule = self.rule()
        self.c("POST", "/penalties", json={"contingent_id": self.ids["A"], "rule_id": rule["id"], "points": 5, "reason": "Only a few minutes late"})
        assert self.balance("A") == 495

    def test_a_penalty_needs_a_reason_and_an_effect(self):
        assert self.c("POST", "/penalties", json={"contingent_id": self.ids["A"], "points": 5}).status_code == 400
        assert self.c("POST", "/penalties", json={"contingent_id": self.ids["A"], "reason": "Hmm"}).status_code == 400

    def test_disqualification_from_an_event_removes_its_points_and_lifting_restores_them(self):
        e = self.scored_event()
        self.results(e["id"], [("A", 1), ("B", 2)])
        assert self.balance("A") == 600
        p = self.c("POST", "/penalties", json={"contingent_id": self.ids["A"], "event_id": e["id"], "disqualified": True, "reason": "Used a banned tool"}).json()
        assert self.balance("A") == 500 and self.balance("B") == 560
        res = self.c("GET", "/events").json()[0]["results"]
        assert next(x for x in res if x["contingent_id"] == self.ids["A"])["disqualified"] is True
        assert self.c("DELETE", f"/penalties/{p['id']}").json()["revoked"] is True
        assert self.balance("A") == 600

    def test_an_event_disqualification_does_not_touch_other_events(self):
        e1 = self.scored_event(title="One"); e2 = self.scored_event(title="Two")
        self.results(e1["id"], [("A", 1)]); self.results(e2["id"], [("A", 1)])
        self.c("POST", "/penalties", json={"contingent_id": self.ids["A"], "event_id": e1["id"], "disqualified": True, "reason": "Rule"})
        assert self.balance("A") == 600

    def test_points_off_and_disqualification_can_come_together(self):
        e = self.scored_event()
        self.results(e["id"], [("A", 1)])
        self.c("POST", "/penalties", json={"contingent_id": self.ids["A"], "event_id": e["id"], "points": 25, "disqualified": True, "reason": "Rule"})
        assert self.balance("A") == 475

    def test_disqualification_from_the_whole_competition_leaves_the_rankings(self):
        e = self.scored_event()
        self.results(e["id"], [("A", 1), ("B", 2)])
        self.c("POST", "/penalties", json={"contingent_id": self.ids["A"], "disqualified": True, "reason": "Serious breach"})
        rows = self.board()["contingents"]
        a = next(r for r in rows if r["contingent_id"] == self.ids["A"])
        assert a["disqualified"] is True and a["rank"] is None and rows[-1]["contingent_id"] == self.ids["A"]
        assert self.rank("B") == 1
        assert all(c["college_name"] != "IIT Delhi" for c in self.board()["colleges"])
        assert self.balance("A") == 500  # its event points no longer count

    def test_lifting_a_penalty_gives_the_points_back(self):
        p = self.c("POST", "/penalties", json={"contingent_id": self.ids["A"], "points": 80, "reason": "Late"}).json()
        assert self.balance("A") == 420
        self.c("DELETE", f"/penalties/{p['id']}")
        assert self.balance("A") == 500

    def test_a_penalty_can_only_be_lifted_once(self):
        p = self.c("POST", "/penalties", json={"contingent_id": self.ids["A"], "points": 10, "reason": "Late"}).json()
        self.c("DELETE", f"/penalties/{p['id']}")
        assert self.c("DELETE", f"/penalties/{p['id']}").status_code == 400

    def test_deleting_a_rule_keeps_the_penalties_already_given(self):
        rule = self.rule()
        self.c("POST", "/penalties", json={"contingent_id": self.ids["A"], "rule_id": rule["id"]})
        assert self.c("DELETE", f"/rules/{rule['id']}").status_code == 204
        assert self.balance("A") == 480
        assert self.c("GET", "/penalties").json()[0]["rule_id"] is None

    def test_a_rule_can_be_changed(self):
        rule = self.rule()
        r = self.c("PATCH", f"/rules/{rule['id']}", json={"penalty_points": 50, "disqualifies": True})
        assert r.json()["penalty_points"] == 50 and r.json()["disqualifies"] is True

    def test_only_the_committee_manages_rules_and_penalties(self):
        assert self.c("POST", "/rules", self.cl, json={"title": "x"}).status_code == 403
        assert self.c("POST", "/penalties", self.cl, json={"contingent_id": self.ids["B"], "points": 5, "reason": "Spite"}).status_code == 403
        assert self.c("GET", "/penalties", self.cl).status_code == 403

    def test_a_leader_sees_their_own_penalties_only(self):
        self.c("POST", "/penalties", json={"contingent_id": self.ids["A"], "points": 10, "reason": "Late"})
        self.c("POST", "/penalties", json={"contingent_id": self.ids["B"], "points": 10, "reason": "Also late"})
        assert [p["reason"] for p in self.c("GET", "/mine", self.cl).json()["penalties"]] == ["Late"]


# ─── awards and the leaderboard ──────────────────────────────────────────────

class TestAwards(Arena):
    def test_the_usual_awards_are_worked_out_from_the_standings(self):
        self.adjust("B", 200); self.adjust("C", 100)
        self.c("POST", "/awards/usual")
        awards = {a["title"]: [w["name"] for w in a["winners"]] for a in self.c("GET", "/awards").json()}
        assert awards["Best College"] == ["NIT Surat"] and awards["Runner-up College"] == ["BITS Pilani"] and awards["Third Place College"] == ["IIT Delhi"]

    def test_the_usual_awards_are_not_added_twice(self):
        self.c("POST", "/awards/usual"); self.c("POST", "/awards/usual")
        assert len(self.c("GET", "/awards").json()) == 3

    def test_a_college_with_several_contingents_competes_on_their_total(self):
        self.ids["A2"] = self.approved(self.stranger, "IIT Delhi")
        self.adjust("A", 30); self.adjust("A2", 30); self.adjust("B", 100)
        self.c("POST", "/awards", json={"title": "Best College", "basis": "college", "rank": 1})
        assert [w["name"] for w in self.c("GET", "/awards").json()[0]["winners"]] == ["IIT Delhi"]

    def test_an_award_by_contingent_names_the_contingent(self):
        self.adjust("C", 90)
        self.c("POST", "/awards", json={"title": "Best Contingent", "basis": "contingent", "rank": 1})
        w = self.c("GET", "/awards").json()[0]["winners"][0]
        assert w["contingent_id"] == self.ids["C"] and w["college_name"] == "BITS Pilani"

    def test_ties_give_the_award_to_everyone_tied(self):
        self.adjust("A", 50); self.adjust("B", 50)
        self.c("POST", "/awards", json={"title": "Best Contingent", "basis": "contingent", "rank": 1})
        assert len(self.c("GET", "/awards").json()[0]["winners"]) == 2

    def test_an_event_award_goes_to_that_events_winner(self):
        e = self.scored_event(title="Battle of Bands")
        self.results(e["id"], [("B", 1), ("A", 2)])
        self.c("POST", "/awards", json={"title": "Best Band", "basis": "event", "event_id": e["id"], "rank": 1})
        a = self.c("GET", "/awards").json()[0]
        assert a["event_title"] == "Battle of Bands" and a["winners"][0]["contingent_id"] == self.ids["B"]

    def test_a_disqualified_event_winner_does_not_take_the_event_award(self):
        e = self.scored_event()
        self.results(e["id"], [("B", 1), ("A", 2)])
        self.c("POST", "/awards", json={"title": "Best", "basis": "event", "event_id": e["id"], "rank": 1})
        self.c("POST", "/penalties", json={"contingent_id": self.ids["B"], "event_id": e["id"], "disqualified": True, "reason": "Rule"})
        assert self.c("GET", "/awards").json()[0]["winners"] == []

    def test_a_custom_award_is_given_by_hand(self):
        r = self.c("POST", "/awards", json={"title": "Spirit of the Fest", "basis": "custom", "winner_contingent_id": self.ids["C"]})
        assert r.status_code == 201 and r.json()["winners"][0]["contingent_id"] == self.ids["C"]
        r = self.c("PATCH", f"/awards/{r.json()['id']}", json={"winner_contingent_id": self.ids["A"]})
        assert r.json()["winners"][0]["contingent_id"] == self.ids["A"]

    def test_an_event_award_needs_an_event(self):
        assert self.c("POST", "/awards", json={"title": "x", "basis": "event"}).status_code == 422

    def test_awards_can_be_removed(self):
        a = self.c("POST", "/awards", json={"title": "x", "basis": "college"}).json()
        assert self.c("DELETE", f"/awards/{a['id']}").status_code == 204
        assert self.c("GET", "/awards").json() == []

    def test_only_the_committee_manages_awards(self):
        assert self.c("POST", "/awards", self.cl, json={"title": "x", "basis": "college"}).status_code == 403
        assert self.c("GET", "/awards", self.cl).status_code == 403


class TestLeaderboardVisibility(Arena):
    def test_hidden_until_the_committee_makes_it_public(self):
        assert self.c("GET", "/leaderboard", self.cl).status_code == 403
        assert self.c("GET", "/leaderboard", self.student).status_code == 403
        assert client.get(f"/api/fests/{SLUG}/competition/leaderboard").status_code == 403

    def test_the_committee_always_sees_it(self):
        assert self.c("GET", "/leaderboard").status_code == 200 and self.c("GET", "/leaderboard", self.admin).status_code == 200

    def test_once_public_everyone_sees_it_without_signing_in(self):
        self.c("PUT", "/settings", json={"public_leaderboard": True})
        self.c("POST", "/awards/usual")
        r = client.get(f"/api/fests/{SLUG}/competition/leaderboard")
        assert r.status_code == 200 and len(r.json()["contingents"]) == 3 and len(r.json()["awards"]) == 3

    def test_the_public_board_carries_no_private_details(self):
        self.c("PUT", "/settings", json={"public_leaderboard": True})
        row = client.get(f"/api/fests/{SLUG}/competition/leaderboard").json()["contingents"][0]
        assert set(row) == {"contingent_id", "name", "code", "college_name", "rank", "score", "balance", "starting_points", "breakdown", "disqualified"}

    def test_a_fest_that_is_not_live_has_no_public_board(self):
        client.patch(f"/api/fests/{SLUG}/status", json={"status": "draft"}, headers=auth(self.owner))
        self.c("PUT", "/settings", json={"public_leaderboard": True})
        assert client.get(f"/api/fests/{SLUG}/competition/leaderboard").status_code == 404


class TestMyCompetition(Arena):
    def test_a_leader_sees_their_balance_and_where_it_came_from(self):
        m = self.meet(); t = self.task(m["id"], "Quiz")
        self.award_task(m["id"], t["id"], [("A", 200)])
        me = self.c("GET", "/mine", self.cl).json()
        assert me["balance"] == 700 and me["starting_points"] == 500 and me["breakdown"]["meet_tasks"] == 200 and me["college_name"] == "IIT Delhi"
        assert me["ledger"][0]["points"] == 200 and "Quiz" in me["ledger"][0]["reason"]

    def test_a_leader_sees_the_meets_with_only_their_own_results(self):
        m = self.meet(); t = self.task(m["id"])
        self.award_task(m["id"], t["id"], [("A", 200), ("B", 100)])
        mine = self.c("GET", "/mine", self.cl).json()["meets"][0]["tasks"][0]["results"]
        assert [(r["contingent_id"], r["points"]) for r in mine] == [(self.ids["A"], 200)]

    def test_a_leader_sees_where_they_placed(self):
        e = self.scored_event(title="Quiz")
        self.results(e["id"], [("A", 2)])
        ev = self.c("GET", "/mine", self.cl).json()["events"][0]
        assert ev["contingent_label"] == "Quiz" and ev["place"] == 2 and ev["points"] == 60

    def test_the_rank_is_shown_only_once_the_board_is_public(self):
        self.adjust("A", 100)
        assert self.c("GET", "/mine", self.cl).json()["rank"] is None
        self.c("PUT", "/settings", json={"public_leaderboard": True})
        assert self.c("GET", "/mine", self.cl).json()["rank"] == 1

    def test_someone_not_leading_a_contingent_gets_nothing(self):
        assert self.c("GET", "/mine", self.student).json() is None

    def test_an_assistant_sees_the_same_as_their_leader(self):
        assert self.go("POST", f"/{self.ids['A']}/assistants", json={"email": "acl@test.com"}).status_code == 201
        assert self.c("GET", "/mine", self.acl).json()["contingent_id"] == self.ids["A"]

    def test_a_leader_does_not_get_anyone_elses_data(self):
        self.adjust("B", 77)
        me = self.c("GET", "/mine", self.cl).json()
        assert me["balance"] == 500 and all(e["contingent_id"] == self.ids["A"] for e in me["ledger"])

    def test_anonymous_callers_are_refused(self):
        assert client.get(f"/api/fests/{SLUG}/competition/mine").status_code == 401


class TestNothingIsFixed(Arena):
    """The usual setup is only a starting point: every number can be changed, and the committee's own values are what count."""

    def test_the_defaults_are_only_suggestions_and_can_all_be_changed(self):
        s = self.c("PUT", "/settings", json={"starting_points": 1000, "default_placing_points": [50, 25], "default_task_points": [10, 5, 1]}).json()
        assert s["starting_points"] == 1000 and s["default_placing_points"] == [50, 25] and s["default_task_points"] == [10, 5, 1]
        assert self.balance("A") == 1000

    def test_a_fest_can_start_with_zero_points(self):
        self.c("PUT", "/settings", json={"starting_points": 0})
        assert self.balance("A") == 0

    def test_the_usual_rules_are_added_once_and_all_editable(self):
        first = self.c("POST", "/rules/usual").json()
        again = self.c("POST", "/rules/usual").json()
        assert len(first) == 5 and len(again) == 5
        late = next(r for r in first if r["title"] == "Late arrival")
        assert late["penalty_points"] == 20
        r = self.c("PATCH", f"/rules/{late['id']}", json={"penalty_points": 5, "title": "Late by 10+ minutes"}).json()
        assert r["penalty_points"] == 5 and r["title"] == "Late by 10+ minutes"
        assert self.c("DELETE", f"/rules/{late['id']}").status_code == 204
        assert len(self.c("GET", "/rules").json()) == 4

    def test_the_usual_rules_do_not_replace_ones_the_fest_wrote_itself(self):
        self.c("POST", "/rules", json={"title": "Late arrival", "penalty_points": 99})
        rules = self.c("POST", "/rules/usual").json()
        assert [r["penalty_points"] for r in rules if r["title"] == "Late arrival"] == [99]

    def test_the_usual_rules_include_disqualifying_ones(self):
        rules = self.c("POST", "/rules/usual").json()
        assert any(r["disqualifies"] for r in rules) and any(r["penalty_points"] and not r["disqualifies"] for r in rules)

    def test_only_the_committee_can_add_them(self):
        assert self.c("POST", "/rules/usual", self.cl).status_code == 403

    def test_each_fest_has_its_own_settings(self):
        self.c("PUT", "/settings", json={"starting_points": 777})
        self.start("fest-two")
        other = client.get("/api/fests/fest-two/competition/settings", headers=auth(self.owner)).json()
        assert other["starting_points"] == 500
