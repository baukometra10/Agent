from pathlib import Path

from app.config import Settings, get_settings
from app.ownership.handoff import OwnershipHandoff, reset_ownership_handoff
from app.distillation.engine import reset_distillation_engine


def test_coverage_meter_has_target_and_ratios(tmp_path: Path):
    get_settings.cache_clear()
    reset_ownership_handoff()
    reset_distillation_engine()
    settings = Settings(
        learning_data_root=tmp_path / "learning",
        distillation_data_root=tmp_path / "distill",
        distillation_enabled=True,
        fast_handoff_enabled=True,
    )
    meter = OwnershipHandoff(settings=settings).coverage_meter()
    assert meter["target_internal_coverage"] == 0.85
    assert 0.0 <= meter["internal_coverage_ratio"] <= 1.0
    assert 0.0 <= meter["blended_progress"] <= 1.0
    assert "label_ar" in meter
    assert meter["specialties_total"] == 6
    get_settings.cache_clear()
    reset_ownership_handoff()
    reset_distillation_engine()


def test_report_urgency_detects_security():
    from app.autopilot.engine import AutopilotEngine

    blocks = [
        {
            "project_name": "X",
            "security": ["[critical] secret in .env: rotate"],
            "risks": [],
            "sandbox_review": {"security_count": 1},
        }
    ]
    assert AutopilotEngine._report_is_urgent(blocks) is True
    assert AutopilotEngine._report_is_urgent([{"security": [], "risks": [], "sandbox_review": {}}]) is False
