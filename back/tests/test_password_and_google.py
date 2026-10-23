"""Password reset by link, Google sign-in, and finishing a profile made without the sign-up form."""

import time
from datetime import datetime, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk, jwt

from app import models, notify
from app.auth import google
from app.routes import auth as auth_routes
from test_fixes import user_token, user_id  # noqa: F401
from test_full import client, auth, login, reset_db, signup, TestingSessionLocal  # noqa: F401


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    auth_routes.reset_login_throttle()
    monkeypatch.setenv("APP_ENV", "development")
    sent = []
    monkeypatch.setattr(auth_routes, "send_password_reset", lambda email, link: sent.append((email, link)))
    return sent


def forgot(email):
    return client.post("/api/auth/password/forgot", json={"email": email})


def token_from(link):
    return link.split("token=")[1]


class TestPasswordReset:
    def setup_method(self):
        signup("Asha Rao", "asha@test.com")

    def test_the_answer_is_the_same_for_unknown_emails(self, fresh):
        known, unknown = forgot("asha@test.com"), forgot("nobody@test.com")
        assert known.status_code == unknown.status_code == 200
        assert known.json()["message"].replace("asha@test.com", "X") == unknown.json()["message"].replace("nobody@test.com", "X")
        assert len(fresh) == 1 and fresh[0][0] == "asha@test.com"

    def test_the_link_sets_a_new_password_and_works_once(self, fresh):
        old_session = login("asha@test.com")
        link = forgot("asha@test.com").json()["dev_link"]
        assert link == fresh[0][1] and "/reset-password?token=" in link
        token = token_from(link)
        assert client.get("/api/auth/password/reset/check", params={"token": token}).json() == {"valid": True}
        r = client.post("/api/auth/password/reset", json={"token": token, "new_password": "brand-new-pass"})
        assert r.status_code == 200 and r.json()["admin"] is False
        assert client.post("/api/auth/login", json={"email": "asha@test.com", "password": "password123"}).status_code == 401
        assert client.post("/api/auth/login", json={"email": "asha@test.com", "password": "brand-new-pass"}).status_code == 200
        assert client.get("/api/users/me", headers=auth(old_session)).status_code == 401   # signed out everywhere
        assert client.post("/api/auth/password/reset", json={"token": token, "new_password": "another-pass-1"}).status_code == 400
        assert client.get("/api/auth/password/reset/check", params={"token": token}).json() == {"valid": False}

    def test_only_the_newest_link_works(self):
        first = token_from(forgot("asha@test.com").json()["dev_link"])
        second = token_from(forgot("asha@test.com").json()["dev_link"])
        assert client.post("/api/auth/password/reset", json={"token": first, "new_password": "brand-new-pass"}).status_code == 400
        assert client.post("/api/auth/password/reset", json={"token": second, "new_password": "brand-new-pass"}).status_code == 200

    def test_links_expire(self):
        token = token_from(forgot("asha@test.com").json()["dev_link"])
        db = TestingSessionLocal()
        db.query(models.PasswordReset).update({"expires_at": datetime.utcnow() - timedelta(minutes=1)})
        db.commit(); db.close()
        assert client.post("/api/auth/password/reset", json={"token": token, "new_password": "brand-new-pass"}).status_code == 400

    def test_tokens_are_stored_only_as_hashes(self):
        token = token_from(forgot("asha@test.com").json()["dev_link"])
        db = TestingSessionLocal()
        stored = [r.token_hash for r in db.query(models.PasswordReset).all()]
        db.close()
        assert token not in stored and all(len(h) == 64 for h in stored)

    def test_requests_are_limited(self):
        codes = [forgot("asha@test.com").status_code for _ in range(4)]
        assert codes == [200, 200, 200, 429]

    def test_the_link_is_only_handed_back_in_development(self, monkeypatch):
        monkeypatch.delenv("APP_ENV")
        assert forgot("asha@test.com").json()["dev_link"] is None
        monkeypatch.setenv("APP_ENV", "production")
        auth_routes.reset_login_throttle()
        assert forgot("asha@test.com").json()["dev_link"] is None

    def test_a_reset_clears_failed_sign_in_attempts(self):
        for _ in range(10):
            client.post("/api/auth/login", json={"email": "asha@test.com", "password": "wrong-one"})
        assert client.post("/api/auth/login", json={"email": "asha@test.com", "password": "password123"}).status_code == 429
        token = token_from(forgot("asha@test.com").json()["dev_link"])
        client.post("/api/auth/password/reset", json={"token": token, "new_password": "brand-new-pass"})
        assert client.post("/api/auth/login", json={"email": "asha@test.com", "password": "brand-new-pass"}).status_code == 200

    def test_short_passwords_are_refused(self):
        token = token_from(forgot("asha@test.com").json()["dev_link"])
        assert client.post("/api/auth/password/reset", json={"token": token, "new_password": "short"}).status_code == 422

    def test_suspended_accounts_get_no_link(self, fresh):
        db = TestingSessionLocal()
        db.query(models.User).filter(models.User.email == "asha@test.com").update({"is_active": False})
        db.commit(); db.close()
        assert forgot("asha@test.com").json()["dev_link"] is None and fresh == []


# ─── Google ───────────────────────────────────────────────────────────────────

CLIENT_ID = "test-client.apps.googleusercontent.com"
_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_pem = _private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
_public = jwk.construct(_private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode(), "RS256").to_dict()
_public.update({"kid": "test-key", "use": "sig", "alg": "RS256"})


def google_token(sub="g-123", email="gina@gmail.com", verified=True, aud=CLIENT_ID, iss="https://accounts.google.com", exp_in=600, **extra):
    now = int(time.time())
    claims = {"sub": sub, "email": email, "email_verified": verified, "aud": aud, "iss": iss, "iat": now, "exp": now + exp_in,
              "given_name": "Gina", "family_name": "Lopez", **extra}
    return jwt.encode(claims, _pem, algorithm="RS256", headers={"kid": "test-key"})


@pytest.fixture
def google_on(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(google, "_fetch_keys", lambda: [_public])
    google._cache.update({"keys": [], "expires": 0.0})


def google_login(token):
    return client.post("/api/auth/google", json={"credential": token})


class TestGoogleTokenChecks:
    def test_switched_off_without_a_client_id(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        r = google_login(google_token())
        assert r.status_code == 503 and "not set up" in r.json()["detail"]

    def test_a_genuine_token_is_accepted(self, google_on):
        assert google_login(google_token()).status_code == 200

    @pytest.mark.parametrize("bad", [
        {"aud": "someone-elses-app"}, {"iss": "https://evil.example"}, {"verified": False}, {"exp_in": -60},
    ])
    def test_tokens_for_other_sites_or_unverified_emails_are_refused(self, google_on, bad):
        assert google_login(google_token(**bad)).status_code == 401

    def test_a_token_signed_with_another_key_is_refused(self, google_on):
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = other.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
        forged = jwt.encode({"sub": "x", "email": "x@gmail.com", "email_verified": True, "aud": CLIENT_ID, "iss": "accounts.google.com", "exp": int(time.time()) + 600}, pem, algorithm="RS256", headers={"kid": "test-key"})
        assert google_login(forged).status_code == 401


class TestGoogleAccounts:
    def test_a_new_person_gets_an_account_that_must_be_finished(self, google_on):
        r = google_login(google_token())
        assert r.status_code == 200 and r.json()["profile_complete"] is False
        tok = r.json()["access_token"]
        me = client.get("/api/users/me", headers=auth(tok)).json()
        assert (me["first_name"], me["last_name"], me["email"], me["has_password"], me["google_linked"]) == ("Gina", "Lopez", "gina@gmail.com", False, True)
        assert client.post("/api/users/me/complete-profile", json={"date_of_birth": "2001-05-05", "accept_terms": False}, headers=auth(tok)).status_code == 422
        done = client.post("/api/users/me/complete-profile", json={"date_of_birth": "2001-05-05", "accept_terms": True}, headers=auth(tok)).json()
        assert done["profile_complete"] is True and done["date_of_birth"] == "2001-05-05"
        assert google_login(google_token()).json()["profile_complete"] is True   # the same Google account signs in again

    def test_signing_in_again_finds_the_same_account(self, google_on):
        a = client.get("/api/users/me", headers=auth(google_login(google_token()).json()["access_token"])).json()
        b = client.get("/api/users/me", headers=auth(google_login(google_token(email="GINA@gmail.com")).json()["access_token"])).json()
        assert a["id"] == b["id"]

    def test_linking_an_existing_account_turns_off_its_old_password(self, google_on):
        signup("Gina Lopez", "gina@gmail.com")   # someone registered this address with a password first
        squatter = login("gina@gmail.com")
        r = google_login(google_token())
        assert r.status_code == 200 and "password was turned off" in r.json()["notice"]
        assert client.get("/api/users/me", headers=auth(squatter)).status_code == 401
        assert client.post("/api/auth/login", json={"email": "gina@gmail.com", "password": "password123"}).status_code == 401
        assert google_login(google_token()).json()["notice"] is None   # only the first time

    def test_another_google_account_cannot_take_over(self, google_on):
        google_login(google_token(sub="g-1"))
        r = google_login(google_token(sub="g-2"))
        assert r.status_code == 409

    def test_admins_cannot_use_google(self, google_on):
        user_token("Admin", "gina@gmail.com", "admin")
        r = google_login(google_token())
        assert r.status_code == 403 and "admin" in r.json()["detail"].lower()

    def test_suspended_accounts_cannot_use_google(self, google_on):
        google_login(google_token())
        db = TestingSessionLocal()
        db.query(models.User).filter(models.User.email == "gina@gmail.com").update({"is_active": False})
        db.commit(); db.close()
        assert google_login(google_token()).status_code == 403

    def test_a_google_only_account_can_set_a_password_by_reset(self, google_on):
        google_login(google_token())
        token = token_from(forgot("gina@gmail.com").json()["dev_link"])
        client.post("/api/auth/password/reset", json={"token": token, "new_password": "brand-new-pass"})
        assert client.post("/api/auth/login", json={"email": "gina@gmail.com", "password": "brand-new-pass"}).status_code == 200

    def test_sign_up_form_accounts_are_complete(self):
        tok = signup("Asha Rao", "asha@test.com")["access_token"]
        assert client.get("/api/users/me", headers=auth(tok)).json()["profile_complete"] is True
