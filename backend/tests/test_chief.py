from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.chief.orchestra import ChiefOrchestra, reset_chief_orchestra
from app.agents.chief.types import WorkerStatus, infer_specialty
from app.config import Settings
from app.distillation.engine import reset_distillation_engine
from app.gateway.intelligent_router import IntelligentModelRouter, reset_intelligent_router
from app.gateway.router import ModelGateway, reset_model_gateway
from app.gateway.types import ModelResponse as MR
from app.gateway.types import ModelRole


@pytest.fixture(autouse=True)
def _reset():
    reset_chief_orchestra()
    reset_model_gateway()
    reset_intelligent_router()
    reset_distillation_engine()
    yield
    reset_chief_orchestra()
    reset_model_gateway()
    reset_intelligent_router()
    reset_distillation_engine()


def test_infer_specialty():
    assert infer_specialty("BackendDeveloper", "implement") == "coding"
    assert infer_specialty("IndependentCritic", "security") == "critic"
    assert infer_specialty(None, "analyze") == "project_intelligence"


@pytest.mark.asyncio
async def test_chief_assigns_idle_worker(tmp_path: Path):
    settings = Settings(
        chief_enabled=True,
        chief_min_workers=3,
        chief_max_workers=8,
        distillation_data_root=tmp_path / "d",
        training_artifacts_root=tmp_path / "t",
        internal_model_base_url="",
        openai_api_key="",
        model_cache_enabled=False,
        model_gateway_force_simulate=False,
        prefer_internal=True,
    )
    gateway = ModelGateway(settings=settings, router=IntelligentModelRouter(settings=settings))
    chief = ChiefOrchestra(settings=settings, gateway=gateway)

    async def fake_complete(role, prompt, **kwargs):
        return MR(
            role=role,
            model_id="internal/coding",
            content="worker-ok: refactor safely",
            simulated=False,
            route_tier="internal",
        )

    with patch.object(gateway, "complete", new=AsyncMock(side_effect=fake_complete)):
        result = await chief.assign("Improve error handling", agent_role="BackendDeveloper", intent="implement")
    assert result["ok"] is True
    assert result["spawned_worker"] is False
    assert result["task"]["status"] == "done"
    assert "worker-ok" in (result["task"]["result_summary"] or "")


@pytest.mark.asyncio
async def test_chief_spawns_when_all_busy(tmp_path: Path):
    settings = Settings(
        chief_enabled=True,
        chief_min_workers=3,
        chief_max_workers=6,
        distillation_data_root=tmp_path / "d",
        training_artifacts_root=tmp_path / "t",
        lora_min_examples=3,
        internal_model_base_url="",
        openai_api_key="",
        model_cache_enabled=False,
        prefer_internal=True,
        model_gateway_force_simulate=False,
    )
    gateway = ModelGateway(settings=settings, router=IntelligentModelRouter(settings=settings))
    chief = ChiefOrchestra(settings=settings, gateway=gateway)

    # Saturate all bootstrap workers
    for w in chief.workers.values():
        w.status = WorkerStatus.busy

    async def fake_complete(role, prompt, **kwargs):
        return MR(
            role=role or ModelRole.coding,
            model_id="internal/coding",
            content="spawned-worker-done",
            simulated=False,
            route_tier="internal",
        )

    with (
        patch.object(gateway, "complete", new=AsyncMock(side_effect=fake_complete)),
        patch(
            "app.agents.chief.orchestra.fast_train_specialty",
            new=AsyncMock(return_value={"dataset_count": 5, "train_ok": True, "mode": "fast_spawn"}),
        ),
    ):
        result = await chief.assign("Write a clamp helper", agent_role="Coder", specialty="coding")

    assert result["ok"] is True
    assert result["spawned_worker"] is True
    assert len(chief.workers) == 5  # 4 bootstrap + 1 spawn
    assert result["worker"]["trained"] is True
