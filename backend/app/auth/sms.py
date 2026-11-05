"""SMS delivery for Spixa phone verification (Twilio or generic HTTP gateway)."""

from __future__ import annotations

import json
import re
from base64 import b64encode
from typing import Any
from urllib import error, parse, request

from app.config import Settings, get_settings


def normalize_phone(raw: str) -> str | None:
    s = re.sub(r"[^\d+]", "", (raw or "").strip())
    if s.startswith("00"):
        s = "+" + s[2:]
    digits = re.sub(r"\D", "", s)
    if len(digits) < 8 or len(digits) > 15:
        return None
    if s.startswith("+"):
        return "+" + digits
    # assume international without + if long enough
    return "+" + digits


def send_sms(phone: str, body: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    to = normalize_phone(phone)
    if not to:
        return {"ok": False, "error": "invalid_phone"}

    sid = (getattr(settings, "twilio_account_sid", "") or "").strip()
    token = (getattr(settings, "twilio_auth_token", "") or "").strip()
    from_num = (getattr(settings, "twilio_from_number", "") or "").strip()
    if sid and token and from_num:
        return _twilio_send(sid, token, from_num, to, body)

    gateway = (getattr(settings, "sms_gateway_url", "") or "").strip()
    if gateway:
        return _gateway_send(gateway, to, body, settings)

    # Dev: no provider — caller should surface code in API response
    return {"ok": True, "mode": "dev_simulate", "to": to, "delivered": False}


def _twilio_send(sid: str, token: str, from_num: str, to: str, body: str) -> dict[str, Any]:
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    data = parse.urlencode({"To": to, "From": from_num, "Body": body}).encode("utf-8")
    auth = b64encode(f"{sid}:{token}".encode("utf-8")).decode("ascii")
    req = request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return {
            "ok": True,
            "mode": "twilio",
            "to": to,
            "delivered": True,
            "sid": payload.get("sid"),
        }
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        return {"ok": False, "error": f"twilio_{exc.code}", "detail": detail}


def _gateway_send(url: str, to: str, body: str, settings: Settings) -> dict[str, Any]:
    api_key = (getattr(settings, "sms_gateway_api_key", "") or "").strip()
    payload = json.dumps({"to": to, "message": body, "text": body}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        return {"ok": True, "mode": "gateway", "to": to, "delivered": True, "response": raw[:200]}
    except error.HTTPError as exc:
        return {"ok": False, "error": f"gateway_{exc.code}"}
