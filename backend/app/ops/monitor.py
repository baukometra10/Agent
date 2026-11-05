"""Admin ops monitor — track users, detect abuse, alert super-admin immediately."""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings

ABUSE_RULES = {
    "failed_login_burst": {"threshold": 5, "window_hint": "recent", "severity": "high"},
    "token_burn_burst": {"threshold": 40, "window_hint": "hour", "severity": "medium"},
    "suspended_access": {"threshold": 1, "severity": "high"},
    "banned_content": {"threshold": 1, "severity": "critical"},
    "rate_limit": {"threshold": 1, "severity": "medium"},
}

BANNED_HINTS = (
    "crypto miner",
    "ransomware",
    "credit card dump",
    "carding",
    "malware kit",
    "ddos tool",
)


class OpsMonitor:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = Path(self.settings.learning_data_root) / "ops"
        self.root.mkdir(parents=True, exist_ok=True)
        self.alerts_path = self.root / "alerts.jsonl"
        self.events_path = self.root / "events.jsonl"
        self.fail_path = self.root / "failed_logins.json"

    def _append(self, path: Path, row: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    def _load_fails(self) -> dict[str, Any]:
        if not self.fail_path.exists():
            return {}
        try:
            return json.loads(self.fail_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_fails(self, data: dict[str, Any]) -> None:
        self.fail_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def record_event(self, kind: str, *, email: str = "", detail: str = "", meta: dict | None = None) -> None:
        self._append(
            self.events_path,
            {
                "id": str(uuid4()),
                "kind": kind,
                "email": (email or "").lower(),
                "detail": detail,
                "meta": meta or {},
                "at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def record_failed_login(self, identity: str) -> dict[str, Any] | None:
        key = (identity or "").strip().lower()
        data = self._load_fails()
        row = data.get(key) or {"count": 0, "at": None}
        row["count"] = int(row.get("count") or 0) + 1
        row["at"] = datetime.now(timezone.utc).isoformat()
        data[key] = row
        self._save_fails(data)
        self.record_event("failed_login", email=key, detail=f"count={row['count']}")
        if row["count"] >= ABUSE_RULES["failed_login_burst"]["threshold"]:
            return self.raise_alert(
                "failed_login_burst",
                email=key,
                title="محاولات دخول فاشلة متكررة",
                detail=f"{row['count']} محاولات فاشلة للهوية {key}",
                severity="high",
            )
        return None

    def clear_failed_login(self, identity: str) -> None:
        key = (identity or "").strip().lower()
        data = self._load_fails()
        if key in data:
            data.pop(key, None)
            self._save_fails(data)

    def check_token_burn(self, email: str, amount: int, *, reason: str = "") -> dict[str, Any] | None:
        email_n = (email or "").lower()
        self.record_event("token_spend", email=email_n, detail=reason, meta={"amount": amount})
        # simple burst: sum last events for this email in file tail
        recent = 0
        if self.events_path.exists():
            lines = self.events_path.read_text(encoding="utf-8").splitlines()[-200:]
            for line in lines:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("kind") != "token_spend":
                    continue
                if str(row.get("email") or "").lower() != email_n:
                    continue
                recent += int((row.get("meta") or {}).get("amount") or 0)
        if recent >= ABUSE_RULES["token_burn_burst"]["threshold"]:
            return self.raise_alert(
                "token_burn_burst",
                email=email_n,
                title="استهلاك توكنز مرتفع بشكل غير طبيعي",
                detail=f"{recent} توكن مؤخراً · السبب الأخير: {reason or '—'}",
                severity="medium",
            )
        return None

    def check_message_content(self, email: str, text: str) -> dict[str, Any] | None:
        low = (text or "").lower()
        hit = next((h for h in BANNED_HINTS if h in low), None)
        if not hit:
            return None
        return self.raise_alert(
            "banned_content",
            email=(email or "").lower(),
            title="محتوى محظور / إساءة استخدام محتملة",
            detail=f"مطابقة: {hit}",
            severity="critical",
            meta={"hint": hit},
        )

    def raise_alert(
        self,
        kind: str,
        *,
        email: str = "",
        title: str,
        detail: str = "",
        severity: str = "medium",
        meta: dict | None = None,
    ) -> dict[str, Any]:
        alert = {
            "id": str(uuid4()),
            "kind": kind,
            "email": (email or "").lower(),
            "title": title,
            "detail": detail,
            "severity": severity,
            "meta": meta or {},
            "acked": False,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        self._append(self.alerts_path, alert)
        notify = self.notify_admin(alert)
        alert["notify"] = notify
        return alert

    def notify_admin(self, alert: dict[str, Any]) -> dict[str, Any]:
        """Immediate push to configured webhook (Slack/etc)."""
        url = (self.settings.notification_webhook_url or "").strip()
        text = (
            f"🚨 Spixa Admin Alert [{alert.get('severity')}]\n"
            f"{alert.get('title')}\n"
            f"المستخدم: {alert.get('email') or '—'}\n"
            f"{alert.get('detail')}\n"
            f"id={alert.get('id')}"
        )
        # always persist a notify copy
        inbox = self.root / "admin_inbox.jsonl"
        self._append(inbox, {"at": alert.get("at"), "text": text, "alert_id": alert.get("id")})
        if not url:
            return {"sent": False, "reason": "webhook_missing", "queued": True}
        payload = json.dumps({"text": text, "alert": alert, "product": "Spixa"}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:  # noqa: S310
                return {"sent": True, "status": resp.status, "queued": True}
        except Exception as exc:  # noqa: BLE001
            return {"sent": False, "error": str(exc), "queued": True}

    def list_alerts(self, *, limit: int = 100, unacked_only: bool = False) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self.alerts_path.exists():
            return rows
        for line in self.alerts_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if unacked_only and row.get("acked"):
                continue
            rows.append(row)
        rows = rows[-limit:]
        rows.reverse()
        return rows

    def ack_alert(self, alert_id: str) -> dict[str, Any]:
        if not self.alerts_path.exists():
            return {"ok": False, "error": "not_found"}
        lines = self.alerts_path.read_text(encoding="utf-8").splitlines()
        found = False
        out: list[str] = []
        for line in lines:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                out.append(line)
                continue
            if str(row.get("id")) == alert_id:
                row["acked"] = True
                row["acked_at"] = datetime.now(timezone.utc).isoformat()
                found = True
            out.append(json.dumps(row, ensure_ascii=False))
        self.alerts_path.write_text("\n".join(out) + ("\n" if out else ""), encoding="utf-8")
        return {"ok": found}


_monitor: OpsMonitor | None = None


def get_ops_monitor() -> OpsMonitor:
    global _monitor
    if _monitor is None:
        _monitor = OpsMonitor()
    return _monitor
