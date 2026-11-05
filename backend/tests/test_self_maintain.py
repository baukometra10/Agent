from pathlib import Path

import pytest

from app.config import Settings, get_settings
from app.distillation.engine import reset_distillation_engine
from app.gateway.intelligent_router import reset_intelligent_router
from app.maintain.engine import SelfMaintenanceEngine
from app.ownership.handoff import reset_ownership_handoff


@pytest.mark.asyncio
async def test_self_maintenance_run(tmp_path: Path):
    get_settings.cache_clear()
    reset_ownership_handoff()
    reset_distillation_engine()
    reset_intelligent_router()
    settings = Settings(
        learning_data_root=tmp_path / "learning",
        distillation_data_root=tmp_path / "distill",
        distillation_enabled=True,
        auto_retire_ready_teachers=False,
    )
    engine = SelfMaintenanceEngine(settings=settings)
    out = await engine.run(climb_if_low=True)
    assert out["ok"] is True
    assert Path(out["path"]).exists()
    status = engine.status()
    assert "doctrine" in status
    get_settings.cache_clear()
    reset_ownership_handoff()
    reset_distillation_engine()
    reset_intelligent_router()
