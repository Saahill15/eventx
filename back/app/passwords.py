"""How slow password hashing is. Slow on purpose: it is what makes stolen password hashes expensive to crack."""

import os
from typing import Mapping

STANDARD_ROUNDS = 12


def rounds_for(environ: Mapping[str, str]) -> int:
    """
    12 is the standard cost. The automated tests sign up and log in hundreds of accounts, so they set BCRYPT_ROUNDS to a cheap
    value (see tests/conftest.py). Production ignores the setting and always uses 12. Hashes made at any cost still verify at any other.
    """
    if environ.get("APP_ENV", "development") == "production":
        return STANDARD_ROUNDS
    try:
        wanted = int(environ.get("BCRYPT_ROUNDS", STANDARD_ROUNDS))
    except ValueError:
        return STANDARD_ROUNDS
    return max(4, min(wanted, 14))


BCRYPT_ROUNDS = rounds_for(os.environ)
