"""
Check the ID token Google's sign-in button gives the browser. Needs GOOGLE_CLIENT_ID; without it Google sign-in is
simply switched off. Google's public keys are fetched from Google and kept for as long as Google says they are valid.
"""

import json
import os
import re
import time
import urllib.request

from jose import JWTError, jwt

CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
_cache = {"keys": [], "expires": 0.0}


class GoogleNotConfigured(Exception):
    """GOOGLE_CLIENT_ID is not set."""


class GoogleTokenInvalid(Exception):
    """The token is not a valid Google sign-in for this site."""


def client_id() -> str:
    return os.getenv("GOOGLE_CLIENT_ID", "").strip()


def _fetch_keys() -> list:
    with urllib.request.urlopen(CERTS_URL, timeout=5) as res:
        body = json.loads(res.read())
        match = re.search(r"max-age=(\d+)", res.headers.get("Cache-Control", ""))
    _cache["keys"] = body.get("keys", [])
    _cache["expires"] = time.time() + (int(match.group(1)) if match else 3600)
    return _cache["keys"]


def _key_for(kid: str) -> dict:
    keys = _cache["keys"] if time.time() < _cache["expires"] else _fetch_keys()
    key = next((k for k in keys if k.get("kid") == kid), None)
    if key is None:  # Google rotated its keys since we last looked
        key = next((k for k in _fetch_keys() if k.get("kid") == kid), None)
    if key is None:
        raise GoogleTokenInvalid("unknown signing key")
    return key


def verify(credential: str) -> dict:
    """The token's claims (sub, email, given_name, ...) if it is genuine, meant for this site, and the email is verified."""
    cid = client_id()
    if not cid:
        raise GoogleNotConfigured()
    try:
        header = jwt.get_unverified_header(credential)
        claims = jwt.decode(credential, _key_for(header.get("kid", "")), algorithms=["RS256"], audience=cid, options={"verify_at_hash": False})
    except (JWTError, OSError, ValueError, KeyError) as exc:
        raise GoogleTokenInvalid(str(exc)) from exc
    if claims.get("iss") not in ISSUERS:
        raise GoogleTokenInvalid("wrong issuer")
    if not claims.get("sub") or not claims.get("email") or claims.get("email_verified") not in (True, "true"):
        raise GoogleTokenInvalid("Google has not verified this email")
    return claims
