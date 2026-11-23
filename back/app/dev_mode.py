"""Whether the developer role switcher is on, kept free of other imports so any module can ask."""

import os

DEV_DOMAIN = "dev.hiveout.test"  # .test is reserved, so mail to these addresses can never reach a real person


def enabled() -> bool:
    """On only for local development: APP_ENV is not production and DEV_ROLE_SWITCHER is exactly "1"."""
    return os.getenv("APP_ENV", "development") != "production" and os.getenv("DEV_ROLE_SWITCHER") == "1"


def is_dev_account(email) -> bool:
    return bool(email) and str(email).lower().endswith("@" + DEV_DOMAIN)
