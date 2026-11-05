import json
from pathlib import Path

from app.autopilot.notify import send_report_webhook
from app.config import Settings, get_settings
from app.gateway.intelligent_router import IntelligentModelRouter, reset_intelligent_router
from app.ownership.handoff import reset_ownership_handoff


def test_router_metrics_persist(tmp_path: Path):
    get_settings.cache_clear()
    reset_intelligent_router()
    settings = Settings(learning_data_root=tmp_path / "learning")
    r1 = IntelligentModelRouter(settings=settings)
    r1.record_internal()
    r1.record_internal()
    path = tmp_path / "learning" / "ownership" / "router_metrics.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["internal_ok"] == 2
    reset_intelligent_router()
    r2 = IntelligentModelRouter(settings=settings)
    assert r2.metrics.internal_ok == 2
    assert r2.metrics.as_dict()["internal_coverage_ratio"] == 1.0
    get_settings.cache_clear()
    reset_intelligent_router()
    reset_ownership_handoff()


def test_webhook_skips_without_url(tmp_path: Path):
    settings = Settings(
        learning_data_root=tmp_path / "learning",
        notification_webhook_url="",
    )
    out = send_report_webhook({"projects_scanned": 1, "urgent": True}, settings=settings)
    assert out["sent"] is False
    assert out["reason"] == "webhook_missing"


def test_webhook_respects_urgent_only(tmp_path: Path):
    settings = Settings(
        learning_data_root=tmp_path / "learning",
        notification_webhook_url="http://127.0.0.1:9/hook",
        notification_webhook_on_urgent_only=True,
    )
    out = send_report_webhook({"projects_scanned": 1, "urgent": False}, settings=settings)
    assert out["reason"] == "skipped_non_urgent"
