"""
Which features an account may use. Everything is free for now.

To make a feature part of a paid bundle later, add its name to PAID_FEATURES (comma-separated, in the environment) and
fill in `has_plan` below with the real check. Nothing else needs to change: the API refuses with a clear message and the
website shows the feature as locked.
"""

import os

from fastapi import HTTPException

SHORT_LINKS = "short_links"


def paid_features() -> set:
    return {f.strip() for f in os.getenv("PAID_FEATURES", "").split(",") if f.strip()}


def has_plan(user, feature: str) -> bool:
    """Placeholder until plans exist: only admins hold a paid feature."""
    return getattr(user.role, "value", user.role) == "admin"


def has_feature(user, feature: str) -> bool:
    return feature not in paid_features() or has_plan(user, feature)


def require_feature(user, feature: str) -> None:
    if not has_feature(user, feature):
        raise HTTPException(status_code=402, detail="Custom short links are part of a paid plan.")
