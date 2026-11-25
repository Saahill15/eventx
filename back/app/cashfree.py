"""
The Cashfree payment gateway (orders, payments, refunds, webhook signatures).

Keys come from the environment: CASHFREE_ENV (sandbox or production), CASHFREE_APP_ID, CASHFREE_SECRET_KEY. With no keys set the
gateway is "off" and the rest of the app keeps its old behaviour (paid events are confirmed at once and no money moves).
Everything the app needs from the gateway is on one small class so tests can stand in a fake for it.
"""

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

API_VERSION = "2023-08-01"
BASE = {"sandbox": "https://sandbox.cashfree.com/pg", "production": "https://api.cashfree.com/pg"}


class GatewayError(Exception):
    """The gateway refused or could not be reached. The message is safe to show."""


class Cashfree:
    def __init__(self, env: str, app_id: str, secret: str):
        self.env = "production" if env == "production" else "sandbox"
        self.app_id, self.secret = app_id, secret

    # ── plumbing ──
    def _headers(self) -> Dict[str, str]:
        return {"x-client-id": self.app_id, "x-client-secret": self.secret, "x-api-version": API_VERSION, "Content-Type": "application/json", "Accept": "application/json"}

    def _call(self, method: str, path: str, body: Optional[dict] = None) -> Any:
        try:
            r = httpx.request(method, BASE[self.env] + path, json=body, headers=self._headers(), timeout=20)
        except httpx.HTTPError:
            raise GatewayError("The payment service could not be reached. Please try again in a moment.")
        if r.status_code >= 400:
            try:
                message = r.json().get("message") or ""
            except ValueError:
                message = ""
            raise GatewayError(f"The payment service refused that: {message}"[:300] if message else "The payment service refused that request.")
        return r.json()

    # ── orders ──
    def create_order(self, order_id: str, amount: float, customer_id: str, name: str, email: str, phone: str, return_url: str, notify_url: Optional[str], note: str, minutes: int = 20) -> dict:
        expires = (datetime.now(timezone.utc) + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
        meta = {"return_url": return_url}
        if notify_url:
            meta["notify_url"] = notify_url
        return self._call("POST", "/orders", {
            "order_id": order_id, "order_amount": round(amount, 2), "order_currency": "INR", "order_note": note[:200], "order_expiry_time": expires,
            "customer_details": {"customer_id": customer_id, "customer_name": name[:100], "customer_email": email, "customer_phone": phone}, "order_meta": meta,
        })

    def get_order(self, order_id: str) -> dict:
        return self._call("GET", f"/orders/{order_id}")

    def get_payments(self, order_id: str) -> List[dict]:
        data = self._call("GET", f"/orders/{order_id}/payments")
        return data if isinstance(data, list) else []

    # ── refunds ──
    def create_refund(self, order_id: str, refund_id: str, amount: float, note: str) -> dict:
        return self._call("POST", f"/orders/{order_id}/refunds", {"refund_amount": round(amount, 2), "refund_id": refund_id, "refund_note": note[:100], "refund_speed": "STANDARD"})

    def get_refund(self, order_id: str, refund_id: str) -> dict:
        return self._call("GET", f"/orders/{order_id}/refunds/{refund_id}")

    # ── webhooks ──
    def verify_webhook(self, raw_body: bytes, signature: str, timestamp: str) -> bool:
        expected = base64.b64encode(hmac.new(self.secret.encode(), (timestamp or "").encode() + raw_body, hashlib.sha256).digest()).decode()
        return hmac.compare_digest(expected, signature or "")


_override: Any = None   # tests put a fake here, or False to switch the gateway off whatever the environment says


def client() -> Optional[Cashfree]:
    """The gateway, or None when no keys are set."""
    if _override is not None:
        return _override or None
    app_id, secret = os.getenv("CASHFREE_APP_ID", "").strip(), os.getenv("CASHFREE_SECRET_KEY", "").strip()
    if not app_id or not secret:
        return None
    return Cashfree(os.getenv("CASHFREE_ENV", "sandbox").strip().lower(), app_id, secret)
