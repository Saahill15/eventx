"""Password hashing cost: cheap in tests, always full strength in production."""

import os

from passlib.context import CryptContext

from app.passwords import rounds_for


def test_production_ignores_the_setting_and_always_uses_twelve():
    assert rounds_for({"APP_ENV": "production", "BCRYPT_ROUNDS": "4"}) == 12
    assert rounds_for({"APP_ENV": "production"}) == 12


def test_development_defaults_to_twelve():
    assert rounds_for({}) == 12 and rounds_for({"APP_ENV": "development"}) == 12


def test_development_can_lower_it_but_not_below_four_or_above_fourteen():
    assert rounds_for({"BCRYPT_ROUNDS": "6"}) == 6
    assert rounds_for({"BCRYPT_ROUNDS": "1"}) == 4
    assert rounds_for({"BCRYPT_ROUNDS": "30"}) == 14


def test_a_garbled_setting_falls_back_to_twelve():
    assert rounds_for({"BCRYPT_ROUNDS": "fast"}) == 12


def test_the_test_suite_asks_for_the_cheap_setting():
    assert os.environ["BCRYPT_ROUNDS"] == "4"


def test_a_hash_made_at_one_cost_verifies_at_another():
    old = CryptContext(schemes=["bcrypt"], bcrypt__rounds=12).hash("a-long-enough-password")
    assert CryptContext(schemes=["bcrypt"], bcrypt__rounds=4).verify("a-long-enough-password", old)
