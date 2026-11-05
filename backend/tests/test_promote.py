from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.config import Settings
from app.distillation.engine import DistillationEngine, reset_distillation_engine
from app.eval.harness import EvalHarness
from app.gateway.intelligent_router import IntelligentModelRouter, reset_intelligent_router
from app.gateway.router import ModelGateway, reset_model_gateway
from app.training.lora import LoRATrainer
from app.training.promote import promote_specialties


@pytest.fixture(autouse=True)
def _reset():
    reset_model_gateway()
    reset_intelligent_router()
    reset_distillation_engine()
    yield
    reset_model_gateway()
    reset_intelligent_router()
    reset_distillation_engine()


@pytest.mark.asyncio
async def test_promote_specialties_offline(tmp_path: Path):
    settings = Settings(
        distillation_data_root=tmp_path / "d",
        training_artifacts_root=tmp_path / "t",
        eval_data_root=tmp_path / "e",
        learning_data_root=tmp_path / "learning",
        workspaces_root=tmp_path / "ws",
        lora_min_examples=1,
        internal_model_base_url="",
        openai_api_key="",
        model_cache_enabled=False,
        prefer_internal=True,
        factory_require_human_approval=True,
    )
    (tmp_path / "ws").mkdir()
    gateway = ModelGateway(settings=settings, router=IntelligentModelRouter(settings=settings))
    harness = EvalHarness(settings=settings, gateway=gateway)
    trainer = LoRATrainer(settings=settings)

    # Seed coding so train has examples
    from app.distillation.coding import seed_coding_curriculum

    seed_coding_curriculum(settings=settings, engine=DistillationEngine(settings=settings))

    async def fake_compare(specialty, persist=True, skip_teacher=None):
        return {
            "specialty": specialty,
            "student_score": 0.9,
            "teacher_score": 0.0,
            "promote": True,
            "gates": {"parity_vs_teacher": True, "min_absolute": True, "not_stub": True},
            "skip_teacher": True,
        }

    with patch.object(harness, "compare", new=AsyncMock(side_effect=fake_compare)):
        report = await promote_specialties(
            ["coding"],
            grow_first=False,
            settings=settings,
            trainer=trainer,
            harness=harness,
        )
    assert report["promoted_count"] == 0  # human gate: not auto-shipped
    assert report["candidate_ready_count"] == 1
    assert report["require_human_approval"] is True
    assert report["results"]["coding"]["job"]["promoted"] is False
    assert report["results"]["coding"]["job"]["candidate_ready"] is True
    assert report["results"]["coding"]["job"]["status"] == "pending_factory_approval"
    assert report["factory_proposals"]
    assert report["factory_proposals"][0].get("ok") is True
