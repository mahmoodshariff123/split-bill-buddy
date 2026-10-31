"""PayPal sandbox client for settling debts.

Each debt ("Ravi owes Ali $24") becomes a PayPal order whose payee is Ali's
PayPal email, so the money goes straight from Ravi to Ali.
Docs: https://developer.paypal.com/docs/api/orders/v2/
"""
import time
import uuid

import httpx

from . import config


class PayPalError(Exception):
    pass


class PayPalClient:
    mode = "sandbox"

    def __init__(self) -> None:
        self._token: str | None = None
        self._expiry = 0.0

    def _access_token(self) -> str:
        if self._token and time.time() < self._expiry - 60:
            return self._token
        r = httpx.post(
            f"{config.PAYPAL_API_BASE}/v1/oauth2/token",
            auth=(config.PAYPAL_CLIENT_ID, config.PAYPAL_CLIENT_SECRET),
            data={"grant_type": "client_credentials"},
            timeout=20,
        )
        if r.status_code != 200:
            raise PayPalError(f"PayPal login failed ({r.status_code}): {r.text[:200]}")
        body = r.json()
        self._token, self._expiry = body["access_token"], time.time() + body.get("expires_in", 3000)
        return self._token

    def _post(self, path: str, json: dict | None = None) -> dict:
        r = httpx.post(
            f"{config.PAYPAL_API_BASE}{path}",
            json=json if json is not None else {},
            headers={
                "Authorization": f"Bearer {self._access_token()}",
                "PayPal-Request-Id": str(uuid.uuid4()),
                "Prefer": "return=representation",
            },
            timeout=30,
        )
        if r.status_code >= 300:
            raise PayPalError(f"PayPal {path} failed ({r.status_code}): {r.text[:300]}")
        return r.json() if r.content else {}

    def create_order(self, *, amount: float, currency: str, payee_email: str, description: str, ref: str) -> str:
        unit = {
            "reference_id": ref,
            "description": description[:127],
            "amount": {"currency_code": currency, "value": f"{amount:.2f}"},
        }
        if payee_email:
            unit["payee"] = {"email_address": payee_email}
        return self._post("/v2/checkout/orders", {"intent": "CAPTURE", "purchase_units": [unit]})["id"]

    def capture(self, order_id: str) -> str:
        order = self._post(f"/v2/checkout/orders/{order_id}/capture")
        cap = order["purchase_units"][0]["payments"]["captures"][0]
        if cap["status"] not in ("COMPLETED", "PENDING"):
            raise PayPalError(f"Capture status is {cap['status']}")
        return cap["id"]


class DemoPayPalClient:
    """Used when no PayPal keys are set, so the app still runs end to end offline."""

    mode = "demo"

    def create_order(self, **_) -> str:
        return f"DEMO-ORDER-{uuid.uuid4().hex[:10].upper()}"

    def capture(self, order_id: str) -> str:
        return f"DEMO-CAPTURE-{uuid.uuid4().hex[:10].upper()}"


def get_client():
    return PayPalClient() if config.paypal_live() else DemoPayPalClient()
