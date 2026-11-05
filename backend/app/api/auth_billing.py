"""Auth (email continue) + billing entitlements + Stripe checkout."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.billing import get_entitlement_store
from app.billing.stripe_checkout import get_stripe
from app.ops.monitor import get_ops_monitor

router = APIRouter(prefix="/system", tags=["auth-billing"])


class LoginStartBody(BaseModel):
    email: str = Field(min_length=3)


class LoginVerifyBody(BaseModel):
    email: str = Field(min_length=3)
    code: str = Field(min_length=4, max_length=12)


class IdentityStartBody(BaseModel):
    email: str = Field(min_length=3)
    phone: str = Field(min_length=8, max_length=24)


class IdentityVerifyBody(BaseModel):
    email: str = Field(min_length=3)
    phone: str = Field(min_length=8, max_length=24)
    email_code: str = Field(min_length=4, max_length=12)
    phone_code: str = Field(min_length=4, max_length=12)


class PhoneStartBody(BaseModel):
    phone: str = Field(min_length=8, max_length=24)


class PhoneVerifyBody(BaseModel):
    phone: str = Field(min_length=8, max_length=24)
    code: str = Field(min_length=4, max_length=12)
    email: str | None = None


class AdminStatusBody(BaseModel):
    email: str
    status: str
    reason: str = ""


class AbuseScanBody(BaseModel):
    email: str = ""
    text: str = ""


class ConfirmPaymentBody(BaseModel):
    email: str
    plan: str = "pro"
    provider_ref: str = Field(min_length=3)
    amount: float | None = None


class CheckoutBody(BaseModel):
    email: str
    plan: str = "pro"


class FinalizeBody(BaseModel):
    session_id: str = Field(min_length=3)


class SpendBody(BaseModel):
    email: str
    amount: int = Field(default=1, ge=1, le=1000)
    reason: str = "agent_task"


@router.get("/billing/catalog")
async def billing_catalog():
    catalog = get_entitlement_store().catalog()
    stripe = get_stripe()
    catalog["payments"] = {
        "provider": "stripe" if stripe.configured else "dev_simulate",
        "stripe_configured": stripe.configured,
    }
    return catalog


@router.post("/billing/checkout")
async def billing_checkout(body: CheckoutBody):
    """Start Stripe Checkout (or unlock in dev when Stripe is not configured)."""
    try:
        return get_stripe().create_checkout_session(email=body.email, plan=body.plan)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/billing/finalize")
async def billing_finalize(body: FinalizeBody):
    result = get_stripe().finalize_session(body.session_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/billing/webhook/stripe")
async def billing_stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="Stripe-Signature"),
):
    payload = await request.body()
    result = get_stripe().handle_webhook(payload, stripe_signature)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/auth/identity/start")
async def auth_identity_start(body: IdentityStartBody):
    """Start identity confirmation — email + phone OTPs together."""
    result = get_entitlement_store().start_identity_login(body.email, body.phone)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/auth/identity/verify")
async def auth_identity_verify(body: IdentityVerifyBody):
    """Verify both email and phone codes to activate the session."""
    result = get_entitlement_store().verify_identity_login(
        body.email,
        body.phone,
        body.email_code,
        body.phone_code,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=401, detail=result)
    return result


@router.post("/auth/login/start")
async def auth_login_start(body: LoginStartBody):
    result = get_entitlement_store().start_login(body.email)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/auth/login/verify")
async def auth_login_verify(body: LoginVerifyBody):
    result = get_entitlement_store().verify_login(body.email, body.code)
    if not result.get("ok"):
        raise HTTPException(status_code=401, detail=result)
    return result


@router.post("/auth/phone/start")
async def auth_phone_start(body: PhoneStartBody):
    result = get_entitlement_store().start_phone_login(body.phone)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/auth/phone/verify")
async def auth_phone_verify(body: PhoneVerifyBody):
    result = get_entitlement_store().verify_phone_login(
        body.phone, body.code, email=body.email
    )
    if not result.get("ok"):
        raise HTTPException(status_code=401, detail=result)
    return result


@router.get("/auth/me")
async def auth_me(email: str):
    user = get_entitlement_store().get_user(email)
    if not user:
        raise HTTPException(status_code=404, detail="not_found")
    return {"user": user}


@router.get("/admin/users")
async def admin_list_users():
    return {"users": get_entitlement_store().list_users()}


@router.post("/admin/users/status")
async def admin_set_status(body: AdminStatusBody):
    result = get_entitlement_store().set_user_status(
        body.email, body.status, reason=body.reason
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.get("/admin/alerts")
async def admin_alerts(unacked_only: bool = False, limit: int = 100):
    return {
        "alerts": get_ops_monitor().list_alerts(
            limit=min(limit, 300), unacked_only=unacked_only
        )
    }


@router.post("/admin/alerts/{alert_id}/ack")
async def admin_ack_alert(alert_id: str):
    result = get_ops_monitor().ack_alert(alert_id)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result)
    return result


@router.post("/admin/abuse/scan")
async def admin_abuse_scan(body: AbuseScanBody):
    """Scan user message for abuse signals (called from IDE/agent paths)."""
    alert = get_ops_monitor().check_message_content(body.email, body.text)
    return {"ok": True, "alert": alert}


@router.post("/billing/confirm-payment")
async def billing_confirm(body: ConfirmPaymentBody):
    """Only unlocks features after payment confirmation."""
    result = get_entitlement_store().confirm_payment(
        email=body.email,
        plan=body.plan,
        provider_ref=body.provider_ref,
        amount=body.amount,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/billing/spend")
async def billing_spend(body: SpendBody):
    result = get_entitlement_store().spend_tokens(
        body.email, body.amount, reason=body.reason or "agent_task"
    )
    if not result.get("ok"):
        raise HTTPException(status_code=402, detail=result)
    return result


@router.get("/billing/usage")
async def billing_usage(email: str, limit: int = 100):
    return get_entitlement_store().usage_report(email, limit=min(limit, 500))
