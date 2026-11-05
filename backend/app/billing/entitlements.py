"""Billing + entitlements — unlock features only after payment is confirmed.

Pricing TBD. Tokens mirror product allowance (spend on agent work).
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.auth.email_otp import send_otp_email
from app.auth.sms import normalize_phone, send_sms
from app.config import Settings, get_settings
from app.ops.monitor import get_ops_monitor

# Feature catalog — user-facing vs admin
USER_FEATURES = [
    "chat",
    "projects",
    "proposals",
    "execution",
    "copilot",
    "understanding",
    "analysis",
    "knowledge",
    "roadmap",
    "agents_view",
]

ADMIN_FEATURES = [
    "admin_console",
    "model_training",
    "ownership",
    "fleet",
    "self_maintain",
    "billing_ops",
]

PLAN_TOKENS = {
    "free": 500,
    "pro": 5000,
    "team": 20000,
    "enterprise": 100000,
}

PLAN_FEATURES = {
    "free": ["chat", "projects", "proposals", "understanding", "knowledge"],
    "pro": list(USER_FEATURES),
    "team": list(USER_FEATURES),
    "enterprise": list(USER_FEATURES),
}

# Display prices placeholder (set later) — UI shows note until real checkout
PLAN_LABELS = {
    "free": {"ar": "مجاني", "en": "Free"},
    "pro": {"ar": "احترافي", "en": "Pro"},
    "team": {"ar": "فريق", "en": "Team"},
    "enterprise": {"ar": "مؤسسات", "en": "Enterprise"},
}


class EntitlementStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = Path(self.settings.learning_data_root) / "billing"
        self.root.mkdir(parents=True, exist_ok=True)
        self.users_path = self.root / "users.json"
        self.payments_path = self.root / "payments.jsonl"
        self.usage_path = self.root / "usage.jsonl"

    def _load_users(self) -> dict[str, Any]:
        if not self.users_path.exists():
            return {"users": {}}
        try:
            return json.loads(self.users_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"users": {}}

    def _save_users(self, data: dict[str, Any]) -> None:
        self.users_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def catalog(self) -> dict[str, Any]:
        return {
            "brand": {
                "product": "Spixa",
                "company": "Suppix AI",
                "tagline_ar": "منصة ذكاء اصطناعي لتطوير البرمجيات",
            },
            "plans": {
                name: {
                    "label": PLAN_LABELS[name],
                    "tokens_monthly": PLAN_TOKENS[name],
                    "features": PLAN_FEATURES[name],
                    "price": None,
                    "price_note": "Stripe Checkout" if name != "free" else "مجاني",
                }
                for name in PLAN_TOKENS
            },
            "user_features": USER_FEATURES,
            "admin_features": ADMIN_FEATURES,
            "login_style": "email_and_phone_otp",
            "require_dual_verification": True,
        }

    def _is_admin_identity(self, email_n: str) -> bool:
        admin_email = (getattr(self.settings, "super_admin_email", "") or "").strip().lower()
        return bool(admin_email and email_n == admin_email) or email_n.endswith(
            "@spixa.admin"
        ) or email_n.endswith("@evolve.admin")

    def start_identity_login(self, email: str, phone: str) -> dict[str, Any]:
        """Identity confirmation: email + phone required together; OTP to both."""
        email_n = (email or "").strip().lower()
        phone_n = normalize_phone(phone)
        if "@" not in email_n:
            return {"ok": False, "error": "invalid_email"}
        if not phone_n:
            return {"ok": False, "error": "invalid_phone"}

        email_code = f"{secrets.randbelow(10**6):06d}"
        phone_code = f"{secrets.randbelow(10**6):06d}"
        data = self._load_users()
        pending = data.setdefault("pending", {})
        identity_key = f"identity:{email_n}"
        pending[identity_key] = {
            "channel": "identity",
            "email": email_n,
            "phone": phone_n,
            "email_code": email_code,
            "phone_code": phone_code,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        # also keep channel keys for compatibility
        pending[email_n] = {
            "channel": "email",
            "code": email_code,
            "at": datetime.now(timezone.utc).isoformat(),
            "paired_phone": phone_n,
        }
        pending[phone_n] = {
            "channel": "phone",
            "code": phone_code,
            "at": datetime.now(timezone.utc).isoformat(),
            "paired_email": email_n,
        }
        self._save_users(data)

        mail = send_otp_email(email_n, email_code, settings=self.settings)
        if not mail.get("ok"):
            return {"ok": False, "error": mail.get("error") or "email_failed", "mail": mail}

        sms = send_sms(
            phone_n,
            f"Spixa code: {phone_code} — رمز التحقق من Suppix AI",
            settings=self.settings,
        )
        if not sms.get("ok"):
            return {"ok": False, "error": sms.get("error") or "sms_failed", "sms": sms}

        out: dict[str, Any] = {
            "ok": True,
            "channel": "identity",
            "email": email_n,
            "phone": phone_n,
            "message": "أُرسل رمز إلى البريد ورمز آخر عبر SMS — أدخل الاثنين لتأكيد الهوية.",
            "email_mode": mail.get("mode"),
            "sms_mode": sms.get("mode"),
        }
        # Dev only: expose codes when providers are not live yet
        if mail.get("mode") == "dev_simulate" or not mail.get("delivered"):
            out["dev_email_code"] = email_code
        if sms.get("mode") == "dev_simulate" or not sms.get("delivered"):
            out["dev_phone_code"] = phone_code
        if out.get("dev_email_code") or out.get("dev_phone_code"):
            out["message"] = (
                "وضع التطوير: الرموز ظاهرة هنا حتى تضبط SMTP/Gmail و Twilio على السيرفر."
            )
        return out

    def verify_identity_login(
        self,
        email: str,
        phone: str,
        email_code: str,
        phone_code: str,
    ) -> dict[str, Any]:
        email_n = (email or "").strip().lower()
        phone_n = normalize_phone(phone)
        if "@" not in email_n or not phone_n:
            return {"ok": False, "error": "invalid_identity"}

        data = self._load_users()
        pending = data.get("pending") or {}
        identity_key = f"identity:{email_n}"
        row = pending.get(identity_key)
        if not row:
            get_ops_monitor().record_failed_login(email_n)
            return {"ok": False, "error": "no_pending_identity"}

        email_ok = str(row.get("email_code")) == str(email_code).strip()
        phone_ok = str(row.get("phone_code")) == str(phone_code).strip()
        phone_match = normalize_phone(str(row.get("phone") or "")) == phone_n
        if not (email_ok and phone_ok and phone_match):
            get_ops_monitor().record_failed_login(email_n)
            return {"ok": False, "error": "invalid_codes"}

        pending.pop(identity_key, None)
        pending.pop(email_n, None)
        pending.pop(phone_n, None)
        get_ops_monitor().clear_failed_login(email_n)
        get_ops_monitor().clear_failed_login(phone_n)

        users = data.setdefault("users", {})
        is_admin = self._is_admin_identity(email_n)
        user = users.get(email_n) or self._new_user(email=email_n, is_admin=is_admin)
        user["email"] = email_n
        user["phone"] = phone_n
        user["email_verified"] = True
        user["phone_verified"] = True
        users[email_n] = user
        data["pending"] = pending
        self._save_users(data)
        return self._finalize_auth(user, data)

    def start_login(self, email: str) -> dict[str, Any]:
        email_n = (email or "").strip().lower()
        if "@" not in email_n:
            return {"ok": False, "error": "invalid_email"}
        code = f"{secrets.randbelow(10**6):06d}"
        data = self._load_users()
        pending = data.setdefault("pending", {})
        pending[email_n] = {
            "channel": "email",
            "code": code,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        self._save_users(data)
        return {
            "ok": True,
            "channel": "email",
            "email": email_n,
            "dev_code": code,
            "message": "أدخل رمز البريد للمتابعة (وضع التطوير يعرض الرمز مباشرة).",
        }

    def start_phone_login(self, phone: str) -> dict[str, Any]:
        phone_n = normalize_phone(phone)
        if not phone_n:
            return {"ok": False, "error": "invalid_phone"}
        code = f"{secrets.randbelow(10**6):06d}"
        data = self._load_users()
        pending = data.setdefault("pending", {})
        pending[phone_n] = {
            "channel": "phone",
            "code": code,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        self._save_users(data)
        sms = send_sms(
            phone_n,
            f"Spixa code: {code} — رمز التحقق من Suppix AI",
            settings=self.settings,
        )
        if not sms.get("ok"):
            return {"ok": False, "error": sms.get("error") or "sms_failed", "sms": sms}
        out: dict[str, Any] = {
            "ok": True,
            "channel": "phone",
            "phone": phone_n,
            "message": "أُرسل رمز التحقق عبر SMS.",
            "sms_mode": sms.get("mode"),
        }
        # Dev / no Twilio: expose code so local testing works
        if sms.get("mode") == "dev_simulate" or not sms.get("delivered"):
            out["dev_code"] = code
            out["message"] = "وضع التطوير: الرمز ظاهر أدناه (لم يُضبط مزوّد SMS)."
        return out

    def verify_login(self, email: str, code: str) -> dict[str, Any]:
        email_n = (email or "").strip().lower()
        data = self._load_users()
        pending = data.get("pending") or {}
        row = pending.get(email_n)
        if not row or str(row.get("code")) != str(code).strip():
            get_ops_monitor().record_failed_login(email_n)
            return {"ok": False, "error": "invalid_code"}
        pending.pop(email_n, None)
        get_ops_monitor().clear_failed_login(email_n)
        users = data.setdefault("users", {})
        is_admin = self._is_admin_identity(email_n)
        user = users.get(email_n) or self._new_user(email=email_n, is_admin=is_admin)
        user["email"] = email_n
        user["email_verified"] = True
        users[email_n] = user
        data["pending"] = pending
        self._save_users(data)
        return self._finalize_auth(user, data)

    def verify_phone_login(self, phone: str, code: str, *, email: str | None = None) -> dict[str, Any]:
        phone_n = normalize_phone(phone)
        if not phone_n:
            return {"ok": False, "error": "invalid_phone"}
        data = self._load_users()
        pending = data.get("pending") or {}
        row = pending.get(phone_n)
        if not row or str(row.get("code")) != str(code).strip():
            get_ops_monitor().record_failed_login(phone_n)
            return {"ok": False, "error": "invalid_code"}
        pending.pop(phone_n, None)
        get_ops_monitor().clear_failed_login(phone_n)
        users = data.setdefault("users", {})

        # Link to existing email account when provided (second factor)
        email_n = (email or "").strip().lower()
        user = None
        if email_n and email_n in users:
            user = users[email_n]
        else:
            # find by phone
            for u in users.values():
                if normalize_phone(str(u.get("phone") or "")) == phone_n:
                    user = u
                    break
        if user is None:
            # phone-first signup — synthetic email key until email linked
            key = email_n or f"phone:{phone_n}@spixa.user"
            is_admin = self._is_admin_identity(email_n) if email_n else False
            user = users.get(key) or self._new_user(email=key, is_admin=is_admin)
            if email_n:
                user["email"] = email_n
            else:
                user["email"] = key
                user["phone_only"] = True
        user["phone"] = phone_n
        user["phone_verified"] = True
        users[str(user.get("email")).lower()] = user
        data["pending"] = pending
        self._save_users(data)
        return self._finalize_auth(user, data)

    def _new_user(self, *, email: str, is_admin: bool) -> dict[str, Any]:
        return {
            "email": email,
            "name": email.split("@")[0],
            "phone": "",
            "access": "admin" if is_admin else "user",
            "plan": "enterprise" if is_admin else "free",
            "tokens_remaining": PLAN_TOKENS["enterprise" if is_admin else "free"],
            "tokens_monthly": PLAN_TOKENS["enterprise" if is_admin else "free"],
            "entitlements": list(ADMIN_FEATURES) + list(USER_FEATURES)
            if is_admin
            else list(PLAN_FEATURES["free"]),
            "email_verified": False,
            "phone_verified": False,
            "status": "pending_verification",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def _finalize_auth(self, user: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        status = str(user.get("status") or "active")
        if status in {"suspended", "banned"}:
            get_ops_monitor().raise_alert(
                "suspended_access",
                email=str(user.get("email") or ""),
                title="محاولة دخول من حساب موقّف/محظور",
                detail=f"status={status}",
                severity="high",
            )
            return {"ok": False, "error": "account_blocked", "status": status}

        email_ok = bool(user.get("email_verified"))
        phone_ok = bool(user.get("phone_verified"))
        # Identity gate: email + phone required for everyone (incl. admin)
        if not email_ok or not phone_ok:
            user["status"] = "pending_verification"
            user["session_token"] = ""
            users = data.setdefault("users", {})
            users[str(user.get("email")).lower()] = user
            self._save_users(data)
            return {
                "ok": True,
                "needs_second_factor": True,
                "need_email": not email_ok,
                "need_phone": not phone_ok,
                "user": self._public(user),
                "message": "تأكيد الهوية يتطلب البريد ورقم الهاتف معاً.",
            }

        user["status"] = "active"
        user["session_token"] = secrets.token_urlsafe(24)
        user["last_login"] = datetime.now(timezone.utc).isoformat()
        users = data.setdefault("users", {})
        users[str(user.get("email")).lower()] = user
        self._save_users(data)
        get_ops_monitor().record_event(
            "login_ok",
            email=str(user.get("email") or ""),
            detail="identity_email_phone",
        )
        return {"ok": True, "needs_second_factor": False, "user": self._public(user)}

    def list_users(self) -> list[dict[str, Any]]:
        users = self._load_users().get("users") or {}
        rows = [self._public(u) for u in users.values()]
        rows.sort(key=lambda r: str(r.get("last_login") or r.get("created_at") or ""), reverse=True)
        return rows

    def set_user_status(self, email: str, status: str, *, reason: str = "") -> dict[str, Any]:
        email_n = (email or "").strip().lower()
        if status not in {"active", "suspended", "banned", "pending_verification"}:
            return {"ok": False, "error": "invalid_status"}
        data = self._load_users()
        user = (data.get("users") or {}).get(email_n)
        if not user:
            return {"ok": False, "error": "user_not_found"}
        user["status"] = status
        user["status_reason"] = reason
        user["status_at"] = datetime.now(timezone.utc).isoformat()
        if status in {"suspended", "banned"}:
            user["session_token"] = ""
            get_ops_monitor().raise_alert(
                "admin_action",
                email=email_n,
                title=f"إجراء مسؤول: {status}",
                detail=reason or "—",
                severity="medium",
            )
        data["users"][email_n] = user
        self._save_users(data)
        return {"ok": True, "user": self._public(user)}

    def get_user(self, email: str) -> dict[str, Any] | None:
        users = self._load_users().get("users") or {}
        row = users.get((email or "").strip().lower())
        return self._public(row) if row else None

    def confirm_payment(
        self,
        *,
        email: str,
        plan: str,
        provider_ref: str,
        amount: float | None = None,
    ) -> dict[str, Any]:
        """Unlock plan features only after payment confirmation."""
        plan_n = plan if plan in PLAN_TOKENS else "pro"
        email_n = (email or "").strip().lower()
        data = self._load_users()
        users = data.setdefault("users", {})
        user = users.get(email_n)
        if not user:
            return {"ok": False, "error": "user_not_found"}
        payment = {
            "id": str(uuid4()),
            "email": email_n,
            "plan": plan_n,
            "provider_ref": provider_ref,
            "amount": amount,
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
            "status": "confirmed",
        }
        with self.payments_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payment, ensure_ascii=False) + "\n")
        user["plan"] = plan_n
        user["tokens_monthly"] = PLAN_TOKENS[plan_n]
        user["tokens_remaining"] = PLAN_TOKENS[plan_n]
        feats = set(user.get("entitlements") or [])
        feats.update(PLAN_FEATURES[plan_n])
        if user.get("access") == "admin":
            feats.update(ADMIN_FEATURES)
        user["entitlements"] = sorted(feats)
        user["last_payment_id"] = payment["id"]
        users[email_n] = user
        self._save_users(data)
        return {"ok": True, "payment": payment, "user": self._public(user)}

    def spend_tokens(
        self,
        email: str,
        amount: int = 1,
        *,
        reason: str = "agent_task",
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        email_n = (email or "").strip().lower()
        data = self._load_users()
        user = (data.get("users") or {}).get(email_n)
        if not user:
            return {"ok": False, "error": "user_not_found"}
        if str(user.get("status") or "active") in {"suspended", "banned"}:
            get_ops_monitor().raise_alert(
                "suspended_access",
                email=email_n,
                title="محاولة استخدام من حساب موقّف",
                detail=reason,
                severity="high",
            )
            return {"ok": False, "error": "account_blocked", "status": user.get("status")}
        rem = int(user.get("tokens_remaining") or 0)
        monthly = int(user.get("tokens_monthly") or 0)
        if user.get("access") != "admin":
            if rem < amount:
                return {"ok": False, "error": "insufficient_tokens", "tokens_remaining": rem}
            user["tokens_remaining"] = rem - amount
            rem = user["tokens_remaining"]
            data["users"][email_n] = user
            self._save_users(data)
        used = max(0, monthly - rem) if monthly else amount
        event = {
            "id": str(uuid4()),
            "email": email_n,
            "amount": amount,
            "reason": reason,
            "meta": meta or {},
            "tokens_remaining": rem,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        with self.usage_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        if user.get("access") != "admin":
            get_ops_monitor().check_token_burn(email_n, amount, reason=reason)
        return {
            "ok": True,
            "tokens_remaining": rem,
            "tokens_used_period": used,
            "event": event,
            "admin": user.get("access") == "admin",
        }

    def usage_report(self, email: str, *, limit: int = 100) -> dict[str, Any]:
        email_n = (email or "").strip().lower()
        user = self.get_user(email_n)
        events: list[dict[str, Any]] = []
        total_spent = 0
        if self.usage_path.exists():
            for line in self.usage_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if str(row.get("email") or "").lower() != email_n:
                    continue
                events.append(row)
                total_spent += int(row.get("amount") or 0)
        events = events[-limit:]
        events.reverse()
        monthly = int((user or {}).get("tokens_monthly") or 0)
        remaining = int((user or {}).get("tokens_remaining") or 0)
        by_day: dict[str, int] = {}
        by_reason: dict[str, int] = {}
        for row in events:
            day = str(row.get("at") or "")[:10] or "unknown"
            by_day[day] = by_day.get(day, 0) + int(row.get("amount") or 0)
            reason = str(row.get("reason") or "task")
            by_reason[reason] = by_reason.get(reason, 0) + int(row.get("amount") or 0)
        daily = [
            {"day": d, "amount": by_day[d]}
            for d in sorted(by_day.keys(), reverse=True)[:14]
        ]
        return {
            "email": email_n,
            "plan": (user or {}).get("plan"),
            "tokens_monthly": monthly,
            "tokens_remaining": remaining,
            "tokens_used": max(0, monthly - remaining) if monthly else total_spent,
            "tokens_spent_logged": total_spent,
            "usage_percent": round(((monthly - remaining) / monthly) * 100, 1) if monthly else 0,
            "daily": daily,
            "by_reason": [
                {"reason": k, "amount": v}
                for k, v in sorted(by_reason.items(), key=lambda x: -x[1])
            ],
            "events": events,
        }

    @staticmethod
    def _public(user: dict[str, Any]) -> dict[str, Any]:
        monthly = int(user.get("tokens_monthly") or 0)
        remaining = int(user.get("tokens_remaining") or 0)
        return {
            "email": user.get("email"),
            "name": user.get("name"),
            "phone": user.get("phone") or "",
            "access": user.get("access"),
            "plan": user.get("plan"),
            "status": user.get("status") or "active",
            "email_verified": bool(user.get("email_verified")),
            "phone_verified": bool(user.get("phone_verified")),
            "tokens_remaining": remaining,
            "tokens_monthly": monthly,
            "tokens_used": max(0, monthly - remaining),
            "entitlements": user.get("entitlements") or [],
            "session_token": user.get("session_token"),
            "last_login": user.get("last_login"),
            "created_at": user.get("created_at"),
            "role_label": "مسؤول أعلى" if user.get("access") == "admin" else "عضو",
            "product": "Spixa",
            "company": "Suppix AI",
        }


_store: EntitlementStore | None = None


def get_entitlement_store() -> EntitlementStore:
    global _store
    if _store is None:
        _store = EntitlementStore()
    return _store
