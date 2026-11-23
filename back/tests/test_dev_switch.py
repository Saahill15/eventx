"""The developer role switcher: works for the four demo accounts locally, and cannot be switched on anywhere else."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as database
from app import models
from app.database import Base, get_db
from app.routes import dev_switch, users


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = factory()
    db.add_all([models.College(name="College A", partner_status="partner"), models.College(name="College B", partner_status="partner"),
                models.College(name="Prospect College", partner_status="prospect")])
    db.commit()
    db.close()
    return factory


def make_client(session_factory, monkeypatch, *, flag="1", app_env="development", loopback=True):
    monkeypatch.setenv("APP_ENV", app_env)
    if flag is None:
        monkeypatch.delenv("DEV_ROLE_SWITCHER", raising=False)
    else:
        monkeypatch.setenv("DEV_ROLE_SWITCHER", flag)
    if loopback:
        monkeypatch.setattr(dev_switch, "LOOPBACK", dev_switch.LOOPBACK | {"testclient"})  # TestClient's fake address
    monkeypatch.setattr(database, "SessionLocal", session_factory)

    app = FastAPI()
    app.include_router(dev_switch.router, prefix="/api/dev")
    app.include_router(users.router, prefix="/api/users")

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def switch(client, persona, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.post("/api/dev/switch", json={"persona": persona}, headers=headers)


class TestSwitchIsOffByDefault:
    def test_off_without_the_flag(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.delenv("DEV_ROLE_SWITCHER", raising=False)
        assert dev_switch.enabled() is False

    def test_on_with_the_flag_in_development(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("DEV_ROLE_SWITCHER", "1")
        assert dev_switch.enabled() is True

    def test_production_wins_over_the_flag(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("DEV_ROLE_SWITCHER", "1")
        assert dev_switch.enabled() is False

    @pytest.mark.parametrize("flag", [None, "", "0", "true", "yes"])
    def test_only_the_exact_value_one_switches_it_on(self, session_factory, monkeypatch, flag):
        client = make_client(session_factory, monkeypatch, flag=flag)
        assert client.get("/api/dev/status").status_code == 404
        assert switch(client, "admin").status_code == 404

    def test_endpoints_refuse_in_production_even_if_mounted(self, session_factory, monkeypatch):
        client = make_client(session_factory, monkeypatch, app_env="production")
        assert client.get("/api/dev/status").status_code == 404
        assert switch(client, "admin").status_code == 404

    def test_a_refused_caller_gets_404_even_with_a_malformed_body(self, session_factory, monkeypatch):
        client = make_client(session_factory, monkeypatch, flag=None)
        assert client.post("/api/dev/switch", json={}).status_code == 404  # not a 422 that would show the route exists

    def test_refuses_requests_from_other_machines(self, session_factory, monkeypatch):
        client = make_client(session_factory, monkeypatch, loopback=False)  # TestClient reports "testclient", not 127.0.0.1
        assert client.get("/api/dev/status").status_code == 404
        assert switch(client, "admin").status_code == 404

    def test_nothing_is_created_when_refused(self, session_factory, monkeypatch):
        client = make_client(session_factory, monkeypatch, flag=None)
        switch(client, "admin")
        db = session_factory()
        assert db.query(models.User).count() == 0


class TestPersonas:
    def test_status_lists_the_four_personas(self, session_factory, monkeypatch):
        client = make_client(session_factory, monkeypatch)
        body = client.get("/api/dev/status").json()
        assert [p["key"] for p in body["personas"]] == ["admin", "organizer", "student", "user"]

    def test_unknown_persona_is_rejected(self, session_factory, monkeypatch):
        client = make_client(session_factory, monkeypatch)
        assert switch(client, "root").status_code == 400

    @pytest.mark.parametrize("persona,role", [("admin", "admin"), ("organizer", "organizer"), ("student", "user"), ("user", "user")])
    def test_each_persona_signs_in_with_the_right_role(self, session_factory, monkeypatch, persona, role):
        client = make_client(session_factory, monkeypatch)
        res = switch(client, persona)
        assert res.status_code == 200
        me = client.get("/api/users/me", headers={"Authorization": f"Bearer {res.json()['access_token']}"}).json()
        assert me["role"] == role
        assert me["email"] == f"{persona}@dev.hiveout.test"
        assert me["profile_complete"] is True and me["interests_set"] is True  # no first-run pop-ups

    def test_student_is_verified_and_the_plain_user_is_not(self, session_factory, monkeypatch):
        client = make_client(session_factory, monkeypatch)
        student = client.get("/api/users/me", headers={"Authorization": f"Bearer {switch(client, 'student').json()['access_token']}"}).json()
        plain = client.get("/api/users/me", headers={"Authorization": f"Bearer {switch(client, 'user').json()['access_token']}"}).json()
        assert student["is_student_verified"] is True and student["college_id"] is not None
        assert plain["is_student_verified"] is False

    def test_organiser_can_host_and_is_linked_to_every_college(self, session_factory, monkeypatch):
        client = make_client(session_factory, monkeypatch)
        me = client.get("/api/users/me", headers={"Authorization": f"Bearer {switch(client, 'organizer').json()['access_token']}"}).json()
        assert me["can_host_fests"] is True and me["can_host_city_events"] is True
        assert len(me["college_ids"]) == 2

    def test_demo_accounts_have_no_password(self, session_factory, monkeypatch):
        client = make_client(session_factory, monkeypatch)
        for persona in ("admin", "organizer", "student", "user"):
            switch(client, persona)
        db = session_factory()
        rows = db.query(models.User).all()
        assert len(rows) == 4 and all(u.hashed_password is None for u in rows)

    def test_switching_twice_reuses_the_same_account(self, session_factory, monkeypatch):
        client = make_client(session_factory, monkeypatch)
        switch(client, "student")
        switch(client, "student")
        assert session_factory().query(models.User).count() == 1

    def test_switching_ends_the_previous_sign_in(self, session_factory, monkeypatch):
        client = make_client(session_factory, monkeypatch)
        first = switch(client, "user").json()["access_token"]
        second = switch(client, "admin", token=first).json()["access_token"]
        assert client.get("/api/users/me", headers={"Authorization": f"Bearer {first}"}).status_code == 401
        assert client.get("/api/users/me", headers={"Authorization": f"Bearer {second}"}).status_code == 200

    def test_the_switch_is_recorded_in_the_sign_in_log(self, session_factory, monkeypatch):
        client = make_client(session_factory, monkeypatch)
        switch(client, "admin")
        event = session_factory().query(models.AuthEvent).one()
        assert event.portal == "dev" and event.reason == "dev_switch" and event.success is True


class TestAdminPanelChangesStick:
    """Switching only signs in. It never puts a demo account back to its starting state."""

    def me(self, client, token):
        return client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})

    def test_removing_the_organiser_role_survives_switching_again(self, session_factory, monkeypatch):
        client = make_client(session_factory, monkeypatch)
        switch(client, "organizer")
        db = session_factory()
        user = db.query(models.User).filter(models.User.email == "organizer@dev.hiveout.test").one()
        user.role = models.RoleEnum.user
        user.can_host_fests = False
        user.can_host_city_events = False
        db.query(models.OrganizerCollege).filter(models.OrganizerCollege.user_id == user.id).delete()
        db.commit()

        me = self.me(client, switch(client, "organizer").json()["access_token"]).json()
        assert me["role"] == "user" and me["can_host_fests"] is False and me["can_host_city_events"] is False and me["college_ids"] == []

    def test_adding_a_role_back_also_survives(self, session_factory, monkeypatch):
        client = make_client(session_factory, monkeypatch)
        switch(client, "user")
        db = session_factory()
        user = db.query(models.User).filter(models.User.email == "user@dev.hiveout.test").one()
        user.role = models.RoleEnum.organizer
        user.can_host_fests = True
        db.commit()
        me = self.me(client, switch(client, "user").json()["access_token"]).json()
        assert me["role"] == "organizer" and me["can_host_fests"] is True

    def test_changing_the_role_again_and_again_keeps_the_last_one(self, session_factory, monkeypatch):
        client = make_client(session_factory, monkeypatch)
        switch(client, "organizer")
        for role in (models.RoleEnum.user, models.RoleEnum.organizer, models.RoleEnum.user):
            db = session_factory()
            db.query(models.User).filter(models.User.email == "organizer@dev.hiveout.test").one().role = role
            db.commit()
            assert self.me(client, switch(client, "organizer").json()["access_token"]).json()["role"] == role.value

    def test_student_verification_removed_in_the_admin_panel_stays_removed(self, session_factory, monkeypatch):
        client = make_client(session_factory, monkeypatch)
        switch(client, "student")
        db = session_factory()
        db.query(models.User).filter(models.User.email == "student@dev.hiveout.test").one().student_verified_until = None
        db.commit()
        me = self.me(client, switch(client, "student").json()["access_token"]).json()
        assert me["is_student_verified"] is False

    def test_a_suspended_demo_account_stays_suspended(self, session_factory, monkeypatch):
        client = make_client(session_factory, monkeypatch)
        switch(client, "user")
        db = session_factory()
        db.query(models.User).filter(models.User.email == "user@dev.hiveout.test").one().is_active = False
        db.commit()
        res = switch(client, "user")
        assert res.status_code == 403 and "suspended" in res.json()["detail"]
        assert session_factory().query(models.User).filter(models.User.email == "user@dev.hiveout.test").one().is_active is False

    def test_other_demo_accounts_are_unaffected_by_that_suspension(self, session_factory, monkeypatch):
        client = make_client(session_factory, monkeypatch)
        switch(client, "user")
        db = session_factory()
        db.query(models.User).filter(models.User.email == "user@dev.hiveout.test").one().is_active = False
        db.commit()
        assert switch(client, "admin").status_code == 200


class TestUnusableWhereTheSwitcherIsOff:
    def test_a_demo_account_token_stops_working_when_the_switcher_is_off(self, session_factory, monkeypatch):
        client = make_client(session_factory, monkeypatch)
        token = switch(client, "admin").json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/api/users/me", headers=headers).status_code == 200

        monkeypatch.delenv("DEV_ROLE_SWITCHER")  # e.g. the database was copied somewhere the flag is not set
        assert client.get("/api/users/me", headers=headers).status_code == 403

    def test_it_works_again_when_the_switcher_is_back_on_and_nothing_was_changed(self, session_factory, monkeypatch):
        client = make_client(session_factory, monkeypatch)
        token = switch(client, "admin").json()["access_token"]
        monkeypatch.delenv("DEV_ROLE_SWITCHER")
        assert client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"}).status_code == 403
        monkeypatch.setenv("DEV_ROLE_SWITCHER", "1")
        assert client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
        assert session_factory().query(models.User).one().is_active is True  # the account itself was never modified

    def test_production_refuses_demo_accounts_even_with_the_flag_set(self, session_factory, monkeypatch):
        client = make_client(session_factory, monkeypatch)
        token = switch(client, "admin").json()["access_token"]
        monkeypatch.setenv("APP_ENV", "production")
        assert client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"}).status_code == 403

    def test_ordinary_accounts_are_never_affected(self, session_factory, monkeypatch):
        from app.auth.jwt import create_token
        from app.auth.sessions import start_session
        client = make_client(session_factory, monkeypatch, flag=None)
        db = session_factory()
        user = models.User(name="Real Person", email="real@example.com", role=models.RoleEnum.user, is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        token = start_session(db, user)["access_token"]
        assert client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
