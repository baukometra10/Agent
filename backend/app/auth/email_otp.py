"""Send identity OTP codes by email (Gmail SMTP / any SMTP)."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Any

from app.config import Settings, get_settings


def send_otp_email(to_email: str, code: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    to = (to_email or "").strip().lower()
    if "@" not in to:
        return {"ok": False, "error": "invalid_email"}

    host = (settings.smtp_host or "").strip()
    from_addr = (settings.notification_email_from or settings.smtp_user or "").strip()
    user = (getattr(settings, "smtp_user", "") or "").strip()
    password = (getattr(settings, "smtp_password", "") or "").strip()
    port = int(getattr(settings, "smtp_port", 587) or 587)

    if not host or not from_addr:
        return {
            "ok": True,
            "mode": "dev_simulate",
            "delivered": False,
            "to": to,
            "note": "SMTP not configured — code returned to client in development only",
        }

    msg = EmailMessage()
    msg["Subject"] = "Spixa — رمز التحقق / verification code"
    msg["From"] = from_addr
    msg["To"] = to
    msg.set_content(
        "Spixa by Suppix AI\n\n"
        f"رمز التحقق الخاص بك: {code}\n"
        f"Your verification code: {code}\n\n"
        "صالح لوقت قصير. لا تشاركه مع أحد.\n"
        "This code expires soon. Do not share it.\n"
    )

    try:
        with smtplib.SMTP(host, port, timeout=25) as smtp:
            smtp.ehlo()
            try:
                smtp.starttls()
                smtp.ehlo()
            except smtplib.SMTPException:
                pass
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
        return {"ok": True, "mode": "smtp", "delivered": True, "to": to}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "smtp_failed", "detail": str(exc)[:300]}
