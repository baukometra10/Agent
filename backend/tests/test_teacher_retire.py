from pathlib import Path

from app.config import Settings, get_settings
from app.distillation.engine import reset_distillation_engine
from app.gateway.intelligent_router import IntelligentModelRouter, reset_intelligent_router
from app.gateway.types import ModelResponse, ModelRole
from app.ownership.handoff import OwnershipHandoff, reset_ownership_handoff


def _handoff(tmp_path: Path) -> OwnershipHandoff:
    get_settings.cache_clear()
    reset_ownership_handoff()
    reset_distillation_engine()
    reset_intelligent_router()
    settings = Settings(
        learning_data_root=tmp_path / "learning",
        distillation_data_root=tmp_path / "distill",
        distillation_enabled=True,
        fast_handoff_enabled=True,
        auto_retire_ready_teachers=False,
        prefer_promoted_internal=True,
        promoted_no_escalate=True,
    )
    return OwnershipHandoff(settings=settings)


def test_retire_and_restore_persists(tmp_path: Path):
    h = _handoff(tmp_path)
    assert h.retire_specialty("coding", reason="test")["ok"] is True
    assert h.is_specialty_retired("coding")
    assert h.is_specialty_retired("internal/coding")
    assert "coding" in (h.list_retired()["specialties"] or [])
    assert h.restore_specialty("coding")["ok"] is True
    assert not h.is_specialty_retired("coding")
    get_settings.cache_clear()
    reset_ownership_handoff()


def test_retired_specialty_blocks_escalate(tmp_path: Path):
    h = _handoff(tmp_path)
    h.retire_specialty("coding", reason="test")
    router = IntelligentModelRouter(settings=h.settings)
    resp = ModelResponse(
        role=ModelRole.coding,
        model_id="internal/coding",
        content="x",
        confidence=0.1,
    )
    escalate, _ = router.should_escalate(resp, metadata={"prefer_promoted": True})
    assert escalate is False
    # force_teacher still wins
    escalate_force, _ = router.should_escalate(
        resp, metadata={"force_teacher": True, "prefer_promoted": True}
    )
    assert escalate_force is True
    get_settings.cache_clear()
    reset_ownership_handoff()
    reset_intelligent_router()
