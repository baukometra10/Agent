"""Notify owner with autopilot reports (email / webhook when configured, else local queue)."""

from __future__ import annotations

import json
import smtplib
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings


def queue_report(report: dict[str, Any], settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    root = Path(settings.learning_data_root) / "autopilot" / "reports"
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    path = root / f"report-{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (root / "latest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return {"queued_path": str(path), "latest": str(root / "latest.json")}


def render_email_body(report: dict[str, Any]) -> str:
    lines = [
        "تقرير مساعد الطيار",
        "=" * 48,
        f"الوقت: {report.get('generated_at')}",
        f"المشاريع المفحوصة: {report.get('projects_scanned')}",
        "",
        "ملاحظة هامة: لم تُلمس الملفات الأصلية. العمل تم على نسخ تجريبية فقط.",
        "",
    ]
    for block in report.get("projects") or []:
        lines.append(f"## {block.get('project_name')}")
        lines.append(f"Sandbox: {block.get('sandbox_path')}")
        lines.append(f"لماذا: {block.get('why')}")
        lines.append("تحسينات مقترحة:")
        for i in block.get("improvements") or []:
            lines.append(f"  - {i}")
        lines.append("مخاطر:")
        for r in block.get("risks") or []:
            lines.append(f"  - {r}")
        lines.append("أمن:")
        for s in block.get("security") or []:
            lines.append(f"  - {s}")
        lines.append("إصلاحات مقترحة (بانتظار موافقتك):")
        for f in block.get("proposed_fixes") or []:
            lines.append(f"  - {f}")
        lines.append("")
    lines.append("الخطوة التالية: راجع المقترحات في Spixa ووافق قبل أي تنفيذ على الأصول.")
    return "\n".join(lines)


def send_report_webhook(
    report: dict[str, Any],
    *,
    settings: Settings | None = None,
    urgent: bool = False,
) -> dict[str, Any]:
    """POST JSON (Slack-compatible text) to NOTIFICATION_WEBHOOK_URL."""
    settings = settings or get_settings()
    url = (settings.notification_webhook_url or "").strip()
    urgent = bool(urgent or report.get("urgent"))
    if not url:
        return {"sent": False, "reason": "webhook_missing", "urgent": urgent}
    if settings.notification_webhook_on_urgent_only and not urgent:
        return {"sent": False, "reason": "skipped_non_urgent", "urgent": urgent}

    summary = (
        f"{'🚨 عاجل · ' if urgent else ''}"
        f"مساعد الطيار — {report.get('projects_scanned', 0)} مشاريع · "
        f"{report.get('generated_at', '')}"
    )
    projects = report.get("projects") or []
    lines = [summary, "لم تُلمس الأصول — نسخ sandbox فقط."]
    for block in projects[:5]:
        name = block.get("project_name") or "?"
        sec = block.get("security") or []
        why = block.get("why") or ""
        lines.append(f"• {name}: {why}")
        for s in sec[:3]:
            lines.append(f"  ⚠ {s}")
    text = "\n".join(lines)
    payload = {
        "text": text,
        "urgent": urgent,
        "source": "evolve_copilot",
        "report": {
            "generated_at": report.get("generated_at"),
            "run_id": report.get("run_id"),
            "projects_scanned": report.get("projects_scanned"),
            "urgent": urgent,
        },
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:  # noqa: S310 — user-configured webhook
            return {
                "sent": True,
                "status": getattr(resp, "status", 200),
                "urgent": urgent,
            }
    except urllib.error.URLError as exc:
        return {"sent": False, "error": str(exc), "urgent": urgent}
    except Exception as exc:  # noqa: BLE001
        return {"sent": False, "error": str(exc), "urgent": urgent}


def send_report_email(
    report: dict[str, Any],
    *,
    to_email: str,
    settings: Settings | None = None,
    urgent: bool = False,
) -> dict[str, Any]:
    settings = settings or get_settings()
    queued = queue_report(report, settings)
    body = render_email_body(report)
    from_addr = (settings.notification_email_from or "").strip()
    host = (settings.smtp_host or "").strip()
    urgent = bool(urgent or report.get("urgent"))
    webhook = send_report_webhook(report, settings=settings, urgent=urgent)
    if not from_addr or not host or not to_email:
        return {
            "sent": False,
            "reason": "smtp_or_recipient_missing",
            "urgent": urgent,
            "body_preview": body[:500],
            "webhook": webhook,
            **queued,
        }

    msg = EmailMessage()
    prefix = "[مساعد الطيار · عاجل]" if urgent else "[مساعد الطيار]"
    msg["Subject"] = f"{prefix} تقرير — {report.get('projects_scanned', 0)} مشاريع"
    msg["From"] = from_addr
    msg["To"] = to_email
    if urgent:
        msg["X-Priority"] = "1"
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, int(settings.smtp_port)) as smtp:
            smtp.send_message(msg)
        return {"sent": True, "webhook": webhook, **queued}
    except Exception as exc:  # noqa: BLE001
        return {"sent": False, "error": str(exc), "webhook": webhook, **queued}
