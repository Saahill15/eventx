"""
Full integration test suite for EventX backend.
Uses an isolated in-memory SQLite DB — does NOT touch eventx.db.

Run with:
    cd back
    python -m pytest tests/test_full.py -v
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app import models

# ─── In-memory test DB ────────────────────────────────────────────────────────
# StaticPool keeps a single connection alive so all sessions share the same
# in-memory SQLite DB (required — each new connection would be a blank DB).

TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True, scope="function")
def reset_db():
    """Drop and recreate all tables before each test function."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


client = TestClient(app, raise_server_exceptions=True)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def signup_payload(name, email, password="password123", **extra):
    first, _, last = name.strip().partition(" ")
    return {"first_name": first or "X", "last_name": last.strip() or "User", "email": email, "password": password,
            "date_of_birth": "2000-01-01", "accept_terms": True, **extra}

def signup(name, email, password="password123"):
    r = client.post("/api/auth/signup", json=signup_payload(name, email, password))
    assert r.status_code == 200, r.text
    return r.json()

def login(email, password="password123"):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    if r.status_code == 403 and "admin" in r.json()["detail"]:   # admins have their own sign-in
        r = client.post("/api/auth/admin/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]

def auth(token):
    return {"Authorization": f"Bearer {token}"}

def make_admin(email):
    """Directly set a user's role to admin in the DB."""
    db = TestingSessionLocal()
    user = db.query(models.User).filter(models.User.email == email).first()
    user.role = models.RoleEnum.admin
    db.commit()
    db.close()

def make_organizer(email):
    db = TestingSessionLocal()
    user = db.query(models.User).filter(models.User.email == email).first()
    user.role = models.RoleEnum.organizer
    db.commit()
    db.close()

def create_college(token):
    r = client.post("/api/colleges/", json={"name": "IIT Bombay", "area": "Powai", "partner_status": "partner"}, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()["id"]

def create_fest(token, college_id, slug="techfest-2026"):
    """Start a fest the way an organiser does, then (as an admin would) approve it and put it live."""
    me = client.get("/api/users/me", headers=auth(token)).json()
    db = TestingSessionLocal()
    if me["role"] == "organizer" and not db.query(models.OrganizerCollege).filter_by(user_id=me["id"], college_id=college_id).first():
        db.add(models.OrganizerCollege(user_id=me["id"], college_id=college_id))
        db.commit()
    db.close()
    r = client.post("/api/fests/", json={
        "slug": slug, "name": "TechFest 2026",
        "tagline": "Asia's largest science fest",
        "college_id": college_id,
    }, headers=auth(token))
    assert r.status_code == 201, r.text
    fest = r.json()
    db = TestingSessionLocal()
    row = db.query(models.Fest).filter(models.Fest.slug == slug).first()
    row.review_status = "approved"
    row.status = models.FestStatusEnum.live
    db.commit()
    db.close()
    fest["status"] = "live"
    return fest

def create_fest_event(token, fest_id, college_id, **kwargs):
    payload = {
        "event_type": "fest",
        "title": kwargs.get("title", "Workshop"),
        "date": "2026-12-01T10:00:00",
        "fest_id": fest_id,
        "college_id": college_id,
        "requires_registration": kwargs.get("requires_registration", False),
        "is_paid": kwargs.get("is_paid", False),
        "price": kwargs.get("price", 0.0),
        "is_free": kwargs.get("is_free", True),
        "approval_mode": kwargs.get("approval_mode", "auto"),
        "registration_limit": kwargs.get("registration_limit", None),
        "category": "Technical",
        "location": kwargs.get("location", "Main Hall"),
        "time": kwargs.get("time", "10:00"),
        "end_time": kwargs.get("end_time", "12:00"),
        "description": kwargs.get("description", "A test event."),
    }
    r = client.post("/api/events/", json=payload, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()

def approve_event(admin_token, event_id):
    r = client.post(f"/api/admin/events/{event_id}/approve", headers=auth(admin_token))
    assert r.status_code == 200, r.text

def get_entry_pass(token, slug):
    r = client.post(f"/api/fests/{slug}/entry-pass", headers=auth(token))
    return r


# ─── AUTH TESTS ───────────────────────────────────────────────────────────────

class TestAuth:
    def test_signup_and_login(self):
        signup("Alice", "alice@test.com")
        token = login("alice@test.com")
        assert token

    def test_duplicate_email_rejected(self):
        signup("Alice", "alice@test.com")
        r = client.post("/api/auth/signup", json=signup_payload("Alice2", "alice@test.com"))
        assert r.status_code == 400

    def test_wrong_password_rejected(self):
        signup("Alice", "alice@test.com")
        r = client.post("/api/auth/login", json={"email": "alice@test.com", "password": "wrongpass"})
        assert r.status_code == 401


# ─── FEST SETUP TESTS ────────────────────────────────────────────────────────

class TestFests:
    def setup_method(self):
        signup("Admin", "admin@test.com")
        make_admin("admin@test.com")
        admin_token = login("admin@test.com")

        signup("Organizer", "org@test.com")
        make_organizer("org@test.com")
        self.token = login("org@test.com")
        self.college_id = create_college(admin_token)

    def test_create_and_fetch_fest(self):
        fest = create_fest(self.token, self.college_id)
        assert fest["slug"] == "techfest-2026"
        assert fest["status"] == "live"

        r = client.get("/api/fests/techfest-2026")
        assert r.status_code == 200
        assert r.json()["name"] == "TechFest 2026"

    def test_duplicate_slug_rejected(self):
        create_fest(self.token, self.college_id)
        r = client.post("/api/fests/", json={
            "slug": "techfest-2026", "name": "Another", "college_id": self.college_id
        }, headers=auth(self.token))
        assert r.status_code == 400

    def test_non_organizer_cannot_create_fest(self):
        signup("Regular", "reg@test.com")
        token = login("reg@test.com")
        r = client.post("/api/fests/", json={
            "slug": "my-fest", "name": "My Fest", "college_id": self.college_id
        }, headers=auth(token))
        assert r.status_code == 403


# ─── EVENT CREATION TESTS ────────────────────────────────────────────────────

class TestEventCreation:
    def setup_method(self):
        signup("Admin", "admin@test.com")
        make_admin("admin@test.com")
        admin_token = login("admin@test.com")

        signup("Organizer", "org@test.com")
        make_organizer("org@test.com")
        self.token = login("org@test.com")
        self.college_id = create_college(admin_token)
        self.fest = create_fest(self.token, self.college_id)
        self.fest_id = self.fest["id"]

    def test_create_fest_event_no_registration(self):
        e = create_fest_event(self.token, self.fest_id, self.college_id, title="Keynote")
        assert e["requires_registration"] == False
        assert e["event_type"] == "fest"

    def test_create_fest_event_free_auto(self):
        e = create_fest_event(self.token, self.fest_id, self.college_id,
                              requires_registration=True, approval_mode="auto")
        assert e["requires_registration"] == True
        assert e["approval_mode"] == "auto"

    def test_create_fest_event_paid(self):
        e = create_fest_event(self.token, self.fest_id, self.college_id,
                              requires_registration=True, is_paid=True, price=199, is_free=False)
        assert e["is_paid"] == True
        assert e["price"] == 199

    def test_paid_event_zero_price_rejected(self):
        r = client.post("/api/events/", json={
            "event_type": "fest", "title": "Bad Event",
            "date": "2026-12-01T10:00:00",
            "fest_id": self.fest_id, "college_id": self.college_id,
            "requires_registration": True, "is_paid": True, "price": 0.0,
        }, headers=auth(self.token))
        assert r.status_code == 422

    def test_city_event_with_fest_id_rejected(self):
        r = client.post("/api/events/", json={
            "event_type": "city", "title": "City Show",
            "date": "2026-12-01T10:00:00", "fest_id": self.fest_id,
        }, headers=auth(self.token))
        assert r.status_code == 422

    def test_fest_event_without_fest_id_rejected(self):
        r = client.post("/api/events/", json={
            "event_type": "fest", "title": "No Fest",
            "date": "2026-12-01T10:00:00",
        }, headers=auth(self.token))
        assert r.status_code == 422

    def test_city_event_isolated_from_fest(self):
        # admin@test.com was already created in setup_method
        admin_token = login("admin@test.com")

        e = client.post("/api/events/", json={
            "event_type": "city", "title": "City Concert",
            "date": "2026-12-01T10:00:00", "category": "Music",
        }, headers=auth(self.token)).json()

        client.post(f"/api/admin/events/{e['id']}/approve", headers=auth(admin_token))

        city_events = client.get("/api/events/city").json()
        ids = [ev["id"] for ev in city_events]
        assert e["id"] in ids


# ─── FESTPASS TESTS ──────────────────────────────────────────────────────────

class TestFestPass:
    def setup_method(self):
        signup("Admin", "admin@test.com")
        make_admin("admin@test.com")
        admin_token = login("admin@test.com")

        signup("Organizer", "org@test.com")
        make_organizer("org@test.com")
        self.org_token = login("org@test.com")
        self.college_id = create_college(admin_token)
        self.fest = create_fest(self.org_token, self.college_id)
        self.slug = self.fest["slug"]

        signup("User A", "usera@test.com")
        self.user_token = login("usera@test.com")

    def test_claim_entry_pass(self):
        r = get_entry_pass(self.user_token, self.slug)
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "approved"
        assert data["checked_in"] == False
        assert data["qr_code"]

    def test_claim_pass_idempotent(self):
        r1 = get_entry_pass(self.user_token, self.slug)
        r2 = get_entry_pass(self.user_token, self.slug)
        assert r1.json()["id"] == r2.json()["id"]

    def test_get_my_pass(self):
        get_entry_pass(self.user_token, self.slug)
        r = client.get(f"/api/fests/{self.slug}/my-pass", headers=auth(self.user_token))
        assert r.status_code == 200
        assert r.json()["status"] == "approved"

    def test_no_pass_returns_404(self):
        r = client.get(f"/api/fests/{self.slug}/my-pass", headers=auth(self.user_token))
        assert r.status_code == 404

    def test_pass_on_draft_fest_rejected(self):
        # Reuse existing college + organizer; just create a second fest in draft status
        client.post("/api/fests/", json={
            "slug": "draft-fest", "name": "Draft Fest",
            "college_id": self.college_id, "status": "draft"
        }, headers=auth(self.org_token))
        r = get_entry_pass(self.user_token, "draft-fest")
        assert r.status_code == 400

    def test_unauthenticated_cannot_get_pass(self):
        r = client.post(f"/api/fests/{self.slug}/entry-pass")
        assert r.status_code == 401


# ─── GATE SCAN TESTS ─────────────────────────────────────────────────────────

class TestGateScan:
    def setup_method(self):
        signup("Admin", "admin@test.com")
        make_admin("admin@test.com")
        admin_token = login("admin@test.com")

        signup("Organizer", "org@test.com")
        make_organizer("org@test.com")
        self.org_token = login("org@test.com")
        college_id = create_college(admin_token)
        self.fest = create_fest(self.org_token, college_id)
        self.slug = self.fest["slug"]

        signup("User A", "usera@test.com")
        self.user_token = login("usera@test.com")
        self.pass_id = get_entry_pass(self.user_token, self.slug).json()["id"]

    def test_gate_scan_success(self):
        r = client.post(f"/api/fests/{self.slug}/gate-scan/{self.pass_id}", headers=auth(self.org_token))
        assert r.status_code == 200
        assert r.json()["checked_in"] == True

    def test_double_scan_rejected(self):
        client.post(f"/api/fests/{self.slug}/gate-scan/{self.pass_id}", headers=auth(self.org_token))
        r = client.post(f"/api/fests/{self.slug}/gate-scan/{self.pass_id}", headers=auth(self.org_token))
        assert r.status_code == 400
        assert "already used" in r.json()["detail"]

    def test_regular_user_cannot_gate_scan(self):
        r = client.post(f"/api/fests/{self.slug}/gate-scan/{self.pass_id}", headers=auth(self.user_token))
        assert r.status_code == 403

    def test_blocked_pass_rejected(self):
        db = TestingSessionLocal()
        fp = db.query(models.FestPass).filter(models.FestPass.id == self.pass_id).first()
        fp.status = models.FestPassStatusEnum.blocked
        db.commit()
        db.close()
        r = client.post(f"/api/fests/{self.slug}/gate-scan/{self.pass_id}", headers=auth(self.org_token))
        assert r.status_code == 400
        assert "blocked" in r.json()["detail"]


# ─── EVENT REGISTRATION TESTS ────────────────────────────────────────────────

class TestEventRegistration:
    def setup_method(self):
        signup("Organizer", "org@test.com")
        make_organizer("org@test.com")
        self.org_token = login("org@test.com")

        signup("Admin", "admin@test.com")
        make_admin("admin@test.com")
        self.admin_token = login("admin@test.com")

        college_id = create_college(self.admin_token)
        self.fest = create_fest(self.org_token, college_id)
        self.slug = self.fest["slug"]
        self.fest_id = self.fest["id"]

        signup("User A", "usera@test.com")
        self.user_token = login("usera@test.com")

        # Create events
        self.free_auto = create_fest_event(
            self.org_token, self.fest_id, college_id,
            title="Free Auto", requires_registration=True, approval_mode="auto"
        )
        approve_event(self.admin_token, self.free_auto["id"])

        self.free_manual = create_fest_event(
            self.org_token, self.fest_id, college_id,
            title="Free Manual", requires_registration=True, approval_mode="manual"
        )
        approve_event(self.admin_token, self.free_manual["id"])

        self.paid_event = create_fest_event(
            self.org_token, self.fest_id, college_id,
            title="Paid Event", requires_registration=True,
            is_paid=True, price=199, is_free=False, approval_mode="auto"
        )
        approve_event(self.admin_token, self.paid_event["id"])

        self.limited_event = create_fest_event(
            self.org_token, self.fest_id, college_id,
            title="Limited", requires_registration=True,
            approval_mode="auto", registration_limit=1
        )
        approve_event(self.admin_token, self.limited_event["id"])

        self.no_reg_event = create_fest_event(
            self.org_token, self.fest_id, college_id,
            title="Walk-in", requires_registration=False
        )
        approve_event(self.admin_token, self.no_reg_event["id"])

        # Give user A an entry pass
        get_entry_pass(self.user_token, self.slug)

    def test_register_free_auto(self):
        r = client.post(f"/api/fest-events/{self.free_auto['id']}/register", headers=auth(self.user_token))
        assert r.status_code == 201
        data = r.json()
        assert data["approval_status"] == "approved"
        assert data["payment_status"] == "unpaid"

    def test_register_free_manual(self):
        r = client.post(f"/api/fest-events/{self.free_manual['id']}/register", headers=auth(self.user_token))
        assert r.status_code == 201
        assert r.json()["approval_status"] == "pending"

    def test_register_paid_event(self):
        r = client.post(f"/api/fest-events/{self.paid_event['id']}/register", headers=auth(self.user_token))
        assert r.status_code == 201
        data = r.json()
        assert data["approval_status"] == "approved"
        assert data["payment_status"] == "paid"

    def test_register_idempotent(self):
        r1 = client.post(f"/api/fest-events/{self.free_auto['id']}/register", headers=auth(self.user_token))
        r2 = client.post(f"/api/fest-events/{self.free_auto['id']}/register", headers=auth(self.user_token))
        assert r1.json()["id"] == r2.json()["id"]

    def test_register_without_pass_rejected(self):
        signup("User B", "userb@test.com")
        token_b = login("userb@test.com")
        r = client.post(f"/api/fest-events/{self.free_auto['id']}/register", headers=auth(token_b))
        assert r.status_code == 400
        assert "entry pass" in r.json()["detail"]

    def test_register_no_reg_event_rejected(self):
        r = client.post(f"/api/fest-events/{self.no_reg_event['id']}/register", headers=auth(self.user_token))
        assert r.status_code == 400
        assert "does not require registration" in r.json()["detail"]

    def test_register_city_event_rejected(self):
        city_event = client.post("/api/events/", json={
            "event_type": "city", "title": "City Show",
            "date": "2026-12-01T10:00:00",
        }, headers=auth(self.org_token)).json()
        approve_event(self.admin_token, city_event["id"])
        r = client.post(f"/api/fest-events/{city_event['id']}/register", headers=auth(self.user_token))
        assert r.status_code == 400
        assert "fest events" in r.json()["detail"]

    def test_my_registrations(self):
        client.post(f"/api/fest-events/{self.free_auto['id']}/register", headers=auth(self.user_token))
        client.post(f"/api/fest-events/{self.paid_event['id']}/register", headers=auth(self.user_token))
        r = client.get("/api/fest-events/my-registrations", headers=auth(self.user_token))
        assert r.status_code == 200
        assert len(r.json()) == 2


# ─── CAPACITY TESTS ──────────────────────────────────────────────────────────

class TestCapacity:
    def setup_method(self):
        signup("Organizer", "org@test.com")
        make_organizer("org@test.com")
        self.org_token = login("org@test.com")

        signup("Admin", "admin@test.com")
        make_admin("admin@test.com")
        self.admin_token = login("admin@test.com")

        college_id = create_college(self.admin_token)
        self.fest = create_fest(self.org_token, college_id)
        self.slug = self.fest["slug"]

        self.event = create_fest_event(
            self.org_token, self.fest["id"], college_id,
            title="Limited Seats", requires_registration=True,
            approval_mode="auto", registration_limit=2
        )
        approve_event(self.admin_token, self.event["id"])

        for name, email in [("UA", "ua@test.com"), ("UB", "ub@test.com"), ("UC", "uc@test.com")]:
            signup(name, email)
            get_entry_pass(login(email), self.slug)

    def test_capacity_enforced(self):
        client.post(f"/api/fest-events/{self.event['id']}/register", headers=auth(login("ua@test.com")))
        client.post(f"/api/fest-events/{self.event['id']}/register", headers=auth(login("ub@test.com")))
        r = client.post(f"/api/fest-events/{self.event['id']}/register", headers=auth(login("uc@test.com")))
        assert r.status_code == 400
        assert "full" in r.json()["detail"]


# ─── EVENT EDIT PROTECTION TESTS ─────────────────────────────────────────────

class TestEventEditProtection:
    def setup_method(self):
        signup("Organizer", "org@test.com")
        make_organizer("org@test.com")
        self.org_token = login("org@test.com")

        signup("Admin", "admin@test.com")
        make_admin("admin@test.com")
        self.admin_token = login("admin@test.com")

        college_id = create_college(self.admin_token)
        self.fest = create_fest(self.org_token, college_id)

        self.event = create_fest_event(
            self.org_token, self.fest["id"], college_id,
            title="Protected", requires_registration=True,
            registration_limit=10, approval_mode="auto"
        )
        approve_event(self.admin_token, self.event["id"])

        signup("User", "u@test.com")
        get_entry_pass(login("u@test.com"), self.fest["slug"])
        client.post(f"/api/fest-events/{self.event['id']}/register", headers=auth(login("u@test.com")))

    def test_description_always_editable(self):
        r = client.patch(f"/api/events/{self.event['id']}",
                         json={"description": "Updated desc"},
                         headers=auth(self.org_token))
        assert r.status_code == 200
        assert r.json()["description"] == "Updated desc"

    def test_increase_limit_allowed(self):
        r = client.patch(f"/api/events/{self.event['id']}",
                         json={"registration_limit": 20},
                         headers=auth(self.org_token))
        assert r.status_code == 200
        assert r.json()["registration_limit"] == 20

    def test_requires_registration_locked(self):
        r = client.patch(f"/api/events/{self.event['id']}",
                         json={"requires_registration": False},
                         headers=auth(self.org_token))
        assert r.status_code == 400
        assert "locked" in r.json()["detail"]

    def test_is_paid_locked(self):
        r = client.patch(f"/api/events/{self.event['id']}",
                         json={"is_paid": True},
                         headers=auth(self.org_token))
        assert r.status_code == 400

    def test_decrease_limit_below_count_locked(self):
        r = client.patch(f"/api/events/{self.event['id']}",
                         json={"registration_limit": 0},
                         headers=auth(self.org_token))
        # a zero limit is rejected outright (it would also be below the current count)
        assert r.status_code == 422
