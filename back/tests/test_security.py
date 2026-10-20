"""Security regression tests: JWT secret, seeded accounts, CORS."""

import importlib

import pytest
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main, models
from app.auth import jwt as auth_jwt
from app.database import Base

SEED_ENV_VARS = [
    "ADMIN_EMAIL", "ADMIN_PASSWORD",
    "ORGANIZER_MOOD_INDIGO_EMAIL", "ORGANIZER_MOOD_INDIGO_PASSWORD",
    "ORGANIZER_MALHAR_EMAIL", "ORGANIZER_MALHAR_PASSWORD",
    "ORGANIZER_KALEIDOSCOPE_EMAIL", "ORGANIZER_KALEIDOSCOPE_PASSWORD",
]


@pytest.fixture
def seed_db(monkeypatch):
    """Run seed() against a throwaway in-memory database with no seed credentials in the environment."""
    for var in SEED_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr(main, "SessionLocal", session_factory)
    yield session_factory


class TestJwtSecret:
    def test_missing_secret_refuses_to_load(self, monkeypatch):
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
        with pytest.raises(RuntimeError):
            importlib.reload(auth_jwt)
        monkeypatch.undo()
        importlib.reload(auth_jwt)

    def test_short_secret_refuses_to_load(self, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "changethis")
        with pytest.raises(RuntimeError):
            importlib.reload(auth_jwt)
        monkeypatch.undo()
        importlib.reload(auth_jwt)

    def test_token_signed_with_old_default_is_rejected(self):
        forged = jose_jwt.encode({"sub": "1", "role": "admin"}, "changethis", algorithm="HS256")
        assert auth_jwt.decode_token(forged) is None


class TestSeededAccounts:
    def test_no_accounts_created_without_credentials(self, seed_db):
        main.seed()
        db = seed_db()
        assert db.query(models.User).count() == 0
        db.close()

    def test_fests_are_created_without_owners(self, seed_db):
        main.seed()
        db = seed_db()
        assert db.query(models.Fest).count() == 3
        assert db.query(models.FestMember).count() == 0
        db.close()

    def test_old_default_logins_do_not_work(self, seed_db):
        main.seed()
        db = seed_db()
        for email in ("admin@eventx.com", "organizer@moodindigo.com", "organizer@malhar.com", "organizer@kaleidoscope.com"):
            assert db.query(models.User).filter(models.User.email == email).first() is None
        db.close()

    def test_weak_admin_password_is_rejected(self, seed_db, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAIL", "owner@example.com")
        monkeypatch.setenv("ADMIN_PASSWORD", "short")
        main.seed()
        db = seed_db()
        assert db.query(models.User).filter(models.User.role == "admin").count() == 0
        db.close()

    def test_admin_created_from_environment(self, seed_db, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAIL", "owner@example.com")
        monkeypatch.setenv("ADMIN_PASSWORD", "a-long-enough-password")
        main.seed()
        db = seed_db()
        admin = db.query(models.User).filter(models.User.role == "admin").one()
        assert admin.email == "owner@example.com"
        assert admin.hashed_password != "a-long-enough-password"
        db.close()

    def test_organizer_created_from_environment_and_owns_fest(self, seed_db, monkeypatch):
        monkeypatch.setenv("ORGANIZER_MALHAR_EMAIL", "malhar@example.com")
        monkeypatch.setenv("ORGANIZER_MALHAR_PASSWORD", "another-long-password")
        main.seed()
        db = seed_db()
        member = db.query(models.FestMember).one()
        assert db.query(models.User).filter(models.User.id == member.user_id).one().email == "malhar@example.com"
        db.close()


class TestCors:
    client = TestClient(main.app)

    def _preflight(self, origin):
        return self.client.options(
            "/api/auth/login",
            headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
        )

    def test_wildcard_is_not_allowed(self):
        assert "*" not in main.ALLOWED_ORIGINS

    def test_unlisted_origin_gets_no_cors_header(self):
        r = self._preflight("https://evil.example.com")
        assert "access-control-allow-origin" not in r.headers

    def test_listed_origin_is_allowed(self):
        r = self._preflight(main.ALLOWED_ORIGINS[0])
        assert r.headers.get("access-control-allow-origin") == main.ALLOWED_ORIGINS[0]
