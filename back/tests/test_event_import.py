"""Adding many events to a fest from a CSV file: template, preview, row-by-row problems, all-or-nothing import."""

from test_fixes import user_token  # noqa: F401
from test_full import client, auth, create_college, create_fest, reset_db, TestingSessionLocal  # noqa: F401
from app import models

HEADER = "title,description,date,start_time,end_time,venue,category,price,student_price,registration,seat_limit,approval,students_only,team_event,team_min,team_max"


def csv_file(*rows, header=HEADER, encoding="utf-8"):
    return {"file": ("events.csv", ("\n".join([header, *rows]) + "\n").encode(encoding), "text/csv")}


GOOD = [
    "Battle of Bands,Bands compete live.,2026-12-05,18:00,21:00,Main Stage,Music,0,,yes,20,manual,no,yes,3,6",
    "Robo Wars,Bots fight.,06/12/2026,11 am,3:30 PM,Ground B,Technical,200,150,yes,,auto,yes,no,,",
    "Open Mic,Anyone can perform.,2026-12-05,19:00,20:00,Amphitheatre,,,,no,,,,,,",
]


class Setup:
    def setup_method(self):
        self.admin = user_token("Admin", "admin@test.com", "admin")
        self.college = create_college(self.admin)
        self.owner = user_token("Owner", "owner@test.com", "organizer")
        self.fest = create_fest(self.owner, self.college, slug="techfest")
        db = TestingSessionLocal()
        f = db.query(models.Fest).filter(models.Fest.slug == "techfest").first()
        from datetime import date
        f.start_date, f.end_date = date(2026, 12, 4), date(2026, 12, 6)
        db.commit(); db.close()

    def upload(self, files, dry_run=True, token=None):
        return client.post(f"/api/fests/techfest/events/import?dry_run={'true' if dry_run else 'false'}", files=files, headers=auth(token or self.owner))

    def events(self):
        return client.get("/api/fests/techfest/manage/events", headers=auth(self.owner)).json()


class TestImport(Setup):
    def test_template_has_every_column(self):
        r = client.get("/api/fests/techfest/events/import-template", headers=auth(self.owner))
        assert r.status_code == 200 and r.text.splitlines()[0] == HEADER and len(r.text.splitlines()) == 3

    def test_the_template_itself_imports_cleanly(self):
        template = client.get("/api/fests/techfest/events/import-template", headers=auth(self.owner)).text
        r = self.upload({"file": ("t.csv", template.encode(), "text/csv")}).json()
        assert r["valid"] == 2 and r["file_errors"] == [] and all(not row["errors"] for row in r["rows"])

    def test_preview_saves_nothing(self):
        r = self.upload(csv_file(*GOOD)).json()
        assert r["dry_run"] is True and r["valid"] == 3 and r["created"] == 0
        assert self.events() == []

    def test_import_creates_every_event_with_its_settings(self):
        r = self.upload(csv_file(*GOOD), dry_run=False).json()
        assert r["created"] == 3
        by_title = {e["title"]: e for e in self.events()}
        bands, robo, mic = by_title["Battle of Bands"], by_title["Robo Wars"], by_title["Open Mic"]
        assert bands["is_team_event"] and (bands["team_min"], bands["team_max"], bands["registration_limit"], bands["approval_mode"]) == (3, 6, 20, "manual")
        assert (robo["time"], robo["end_time"], robo["price"], robo["student_price"], robo["students_only"], robo["is_free"]) == ("11:00", "15:30", 200, 150, True, False)
        assert robo["date"].startswith("2026-12-06") and mic["requires_registration"] is False and mic["is_free"] is True

    def test_problems_are_reported_per_row_and_nothing_is_saved(self):
        rows = GOOD[:1] + [
            "No Venue,Something.,2026-12-05,10:00,11:00,,,,,,,,,,,",
            "Too Late,Something.,2026-12-20,10:00,11:00,Hall,,,,,,,,,,",
            "Backwards,Something.,2026-12-05,12:00,11:00,Hall,,,,,,,,,,",
            "Bad Values,Something.,someday,25:00,11:00,Hall,,-5,,maybe,lots,sometimes,,,,",
            "Team No Reg,Something.,2026-12-05,10:00,11:00,Hall,,,,no,,,,yes,2,4",
            "Battle of Bands,Again.,2026-12-05,10:00,11:00,Hall,,,,,,,,,,",
        ]
        r = self.upload(csv_file(*rows), dry_run=False).json()
        assert r["created"] == 0 and r["valid"] == 1 and self.events() == []
        errors = {row["title"]: " | ".join(row["errors"]) for row in r["rows"][1:-1]}
        assert r["rows"][0]["errors"] == [] and "more than once" in r["rows"][-1]["errors"][0]
        assert "venue: required" in errors["No Venue"]
        assert "between 2026-12-04 and 2026-12-06" in errors["Too Late"]
        assert "end time must be after" in errors["Backwards"]
        for bit in ("date:", "start_time:", "price: cannot be negative", "registration: write yes or no", "seat_limit:", "approval: write auto or manual"):
            assert bit in errors["Bad Values"], bit
        assert "team event needs registration" in errors["Team No Reg"]
        assert [row["line"] for row in r["rows"]] == [2, 3, 4, 5, 6, 7, 8]

    def test_existing_titles_are_refused(self):
        self.upload(csv_file(GOOD[0]), dry_run=False)
        r = self.upload(csv_file(GOOD[0])).json()
        assert "already has an event" in r["rows"][0]["errors"][0]

    def test_wrong_columns_are_caught(self):
        r = self.upload(csv_file(GOOD[0], header=HEADER.replace("venue", "place"))).json()
        assert any("Missing columns: venue" in e for e in r["file_errors"]) and any("place" in e for e in r["file_errors"])

    def test_excel_style_files_work(self):
        r = self.upload({"file": ("e.csv", ("﻿" + HEADER + "\r\n" + GOOD[2] + "\r\n").encode("utf-8"), "text/csv")}).json()
        assert r["valid"] == 1
        r = self.upload(csv_file("Café Night,Coffee and music.,2026-12-05,19:00,20:00,Café,,,,,,,,,,", encoding="cp1252")).json()
        assert r["valid"] == 1 and r["rows"][0]["title"] == "Café Night"

    def test_blank_lines_are_skipped_and_empty_files_are_caught(self):
        assert self.upload(csv_file(GOOD[2], ",,,,,,,,,,,,,,,", "")).json()["valid"] == 1
        assert self.upload(csv_file()).json()["file_errors"] == ["The file has no events in it."]

    def test_limits(self):
        big = {"file": ("big.csv", b"x" * (513 * 1024), "text/csv")}
        assert self.upload(big).status_code == 400
        rows = [f"Event {i},Desc.,2026-12-05,10:00,11:00,Hall,,,,,,,,,," for i in range(201)]
        assert "At most 200" in self.upload(csv_file(*rows)).json()["file_errors"][0]

    def test_formula_like_text_is_kept_as_text(self):
        r = self.upload(csv_file('"=HYPERLINK(""x"")",Desc.,2026-12-05,10:00,11:00,Hall,,,,,,,,,,'), dry_run=False).json()
        assert r["created"] == 1 and self.events()[0]["title"] == '=HYPERLINK("x")'

    def test_only_fest_staff_can_import(self):
        stranger = user_token("Stranger", "stranger@test.com", "organizer")
        assert self.upload(csv_file(*GOOD), token=stranger).status_code == 404
        assert client.get("/api/fests/techfest/events/import-template", headers=auth(stranger)).status_code == 404

    def test_frozen_while_in_review(self):
        db = TestingSessionLocal()
        db.query(models.Fest).filter(models.Fest.slug == "techfest").update({"review_status": "in_review"})
        db.commit(); db.close()
        assert self.upload(csv_file(*GOOD)).status_code == 400
