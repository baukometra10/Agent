"""Stripe Checkout for Spixa plans — unlocks entitlements after paid webhook/session."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any
from urllib import error, request

from app.billing.entitlements import (
    PLAN_LABELS,
    PLAN_TOKENS,
    EntitlementStore,
    get_entitlement_store,
)
from app.config import Settings, get_settings

# Fallback unit amounts (cents) when no Stripe Price IDs configured — editable later
PLAN_UNIT_AMOUNT_CENTS = {
    "free": 0,
    "pro": 2900,
    "team": 9900,
    "enterprise": 29900,
}


class StripeCheckout:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.secret = (getattr(self.settings, "stripe_secret_key", "") or "").strip()
        self.webhook_secret = (getattr(self.settings, "stripe_webhook_secret", "") or "").strip()
        self.success_url = (
            getattr(self.settings, "stripe_success_url", "") or ""
        ).strip() or "http://localhost:3000/console?tab=billing&paid=1"
        self.cancel_url = (
            getattr(self.settings, "stripe_cancel_url", "") or ""
        ).strip() or "http://localhost:3000/console?tab=billing&paid=0"

    @property
    def configured(self) -> bool:
        return bool(self.secret.startswith("sk_"))

    def _store(self) -> EntitlementStore:
        return EntitlementStore(settings=self.settings)

    def _api(self, method: str, path: str, form: dict[str, str] | None = None) -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError("stripe_not_configured")
        data = None
        headers = {"Authorization": f"Bearer {self.secret}"}
        if form is not None:
            data = "&".join(
                f"{request.quote(str(k))}={request.quote(str(v))}" for k, v in form.items()
            ).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = request.Request(
            f"https://api.stripe.com/v1/{path.lstrip('/')}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"stripe_http_{exc.code}:{body[:400]}") from exc

    def create_checkout_session(self, *, email: str, plan: str) -> dict[str, Any]:
        plan_n = plan if plan in PLAN_TOKENS else "pro"
        if plan_n == "free":
            unlocked = self._store().confirm_payment(
                email=email, plan="free", provider_ref="free-plan", amount=0
            )
            return {"ok": True, "mode": "free", "user": unlocked.get("user")}

        if not self.configured:
            # Dev fallback: simulated paid unlock (explicit provider_ref)
            unlocked = self._store().confirm_payment(
                email=email,
                plan=plan_n,
                provider_ref=f"dev-stripe-sim-{plan_n}",
                amount=PLAN_UNIT_AMOUNT_CENTS[plan_n] / 100,
            )
            return {
                "ok": True,
                "mode": "dev_simulate",
                "checkout_url": None,
                "user": unlocked.get("user"),
                "note": "STRIPE_SECRET_KEY غير مضبوط — تم التفعيل محلياً للتطوير.",
            }

        price_id = {
            "pro": getattr(self.settings, "stripe_price_pro", "") or "",
            "team": getattr(self.settings, "stripe_price_team", "") or "",
            "enterprise": getattr(self.settings, "stripe_price_enterprise", "") or "",
        }.get(plan_n, "")

        form: dict[str, str] = {
            "mode": "subscription" if price_id else "payment",
            "success_url": f"{self.success_url}&plan={plan_n}&session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": self.cancel_url,
            "customer_email": email,
            "client_reference_id": email,
            "metadata[plan]": plan_n,
            "metadata[email]": email,
            "metadata[product]": "Spixa",
        }
        if price_id:
            form["line_items[0][price]"] = price_id
            form["line_items[0][quantity]"] = "1"
        else:
            label = PLAN_LABELS.get(plan_n, {}).get("en", plan_n)
            form["line_items[0][price_data][currency]"] = "usd"
            form["line_items[0][price_data][product_data][name]"] = f"Spixa {label}"
            form["line_items[0][price_data][unit_amount]"] = str(PLAN_UNIT_AMOUNT_CENTS[plan_n])
            form["line_items[0][quantity]"] = "1"
            form["mode"] = "payment"

        session = self._api("POST", "checkout/sessions", form)
        return {
            "ok": True,
            "mode": "stripe",
            "checkout_url": session.get("url"),
            "session_id": session.get("id"),
        }

    def finalize_session(self, session_id: str) -> dict[str, Any]:
        if not self.configured:
            return {"ok": False, "error": "stripe_not_configured"}
        session = self._api("GET", f"checkout/sessions/{session_id}")
        if session.get("payment_status") not in {"paid", "no_payment_required"}:
            return {"ok": False, "error": "not_paid", "status": session.get("payment_status")}
        meta = session.get("metadata") or {}
        email = meta.get("email") or session.get("customer_email") or session.get("client_reference_id")
        plan = meta.get("plan") or "pro"
        if not email:
            return {"ok": False, "error": "missing_email"}
        amount = None
        if session.get("amount_total") is not None:
            amount = float(session["amount_total"]) / 100.0
        return self._store().confirm_payment(
            email=str(email),
            plan=str(plan),
            provider_ref=str(session.get("id")),
            amount=amount,
        )

    def handle_webhook(self, payload: bytes, sig_header: str) -> dict[str, Any]:
        if self.webhook_secret:
            if not self._verify_signature(payload, sig_header, self.webhook_secret):
                return {"ok": False, "error": "invalid_signature"}
        try:
            event = json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError:
            return {"ok": False, "error": "bad_json"}
        etype = event.get("type")
        obj = (event.get("data") or {}).get("object") or {}
        if etype == "checkout.session.completed":
            email = (obj.get("metadata") or {}).get("email") or obj.get("customer_email")
            plan = (obj.get("metadata") or {}).get("plan") or "pro"
            if not email:
                return {"ok": False, "error": "missing_email"}
            amount = None
            if obj.get("amount_total") is not None:
                amount = float(obj["amount_total"]) / 100.0
            return self._store().confirm_payment(
                email=str(email),
                plan=str(plan),
                provider_ref=str(obj.get("id")),
                amount=amount,
            )
        return {"ok": True, "ignored": etype}

    @staticmethod
    def _verify_signature(payload: bytes, header: str, secret: str) -> bool:
        # Stripe-Signature: t=timestamp,v1=signature
        try:
            parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
            timestamp = parts.get("t", "")
            v1 = parts.get("v1", "")
            signed = f"{timestamp}.".encode("utf-8") + payload
            digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
            return hmac.compare_digest(digest, v1)
        except Exception:
            return False


_stripe: StripeCheckout | None = None


def get_stripe() -> StripeCheckout:
    global _stripe
    if _stripe is None:
        _stripe = StripeCheckout()
    return _stripe
