from pathlib import Path

import pytest

from app.config import Settings
from app.distillation.coding import seed_coding_curriculum
from app.distillation.critic import seed_critic_curriculum
from app.distillation.engine import DistillationEngine, reset_distillation_engine
from app.distillation.grow import grow_all_specialties
from app.distillation.reasoning import seed_reasoning_curriculum
from app.distillation.vision import seed_vision_curriculum
from app.gateway.intelligent_router import reset_intelligent_router
from app.gateway.router import reset_model_gateway
from app.learning.loop import ContinualLearningLoop


@pytest.fixture(autouse=True)
def _reset():
    reset_model_gateway()
    reset_intelligent_router()
    reset_distillation_engine()
    yield
    reset_model_gateway()
    reset_intelligent_router()
    reset_distillation_engine()


def test_seed_coding_curriculum(tmp_path: Path):
    settings = Settings(distillation_enabled=True, distillation_data_root=tmp_path / "d")
    engine = DistillationEngine(settings=settings)
    result = seed_coding_curriculum(settings=settings, engine=engine)
    assert result["accepted"] >= 3
    assert engine.stats()["examples_by_specialty"]["coding"] >= 3


def test_seed_reasoning_and_critic(tmp_path: Path):
    settings = Settings(distillation_enabled=True, distillation_data_root=tmp_path / "d")
    engine = DistillationEngine(settings=settings)
    r = seed_reasoning_curriculum(settings=settings, engine=engine)
    c = seed_critic_curriculum(settings=settings, engine=engine)
    v = seed_vision_curriculum(settings=settings, engine=engine)
    assert r["accepted"] >= 3
    assert c["accepted"] >= 3
    assert v["accepted"] >= 3
    stats = engine.stats()["examples_by_specialty"]
    assert stats["reasoning"] >= 3
    assert stats["critic"] >= 3
    assert stats["vision"] >= 3


def test_grow_all_specialties(tmp_path: Path):
    settings = Settings(
        distillation_enabled=True,
        distillation_data_root=tmp_path / "d",
        workspaces_root=tmp_path / "ws",
    )
    (tmp_path / "ws").mkdir()
    engine = DistillationEngine(settings=settings)
    grown = grow_all_specialties(settings=settings, engine=engine, include_workspaces=False)
    assert grown["coding"]["accepted"] >= 3
    assert grown["reasoning"]["accepted"] >= 3
    assert grown["critic"]["accepted"] >= 3
    assert grown["vision"]["accepted"] >= 3


@pytest.mark.asyncio
async def test_learning_cycle_seed_only(tmp_path: Path):
    ws = tmp_path / "workspaces" / "demo"
    repo = ws / "repo"
    repo.mkdir(parents=True)
    (repo / "main.py").write_text("def ping():\n    return 'ok'\n", encoding="utf-8")
    settings = Settings(
        workspaces_root=tmp_path / "workspaces",
        distillation_data_root=tmp_path / "distill",
        training_artifacts_root=tmp_path / "train",
        eval_data_root=tmp_path / "eval",
        learning_data_root=tmp_path / "learning",
        openai_api_key="",
        model_cache_enabled=False,
        internal_model_base_url="",
        lora_min_examples=1,
    )
    loop = ContinualLearningLoop(settings=settings)
    # seed only — full train/eval covered elsewhere; keeps unit tests offline/fast
    report = await loop.run_cycle(specialties=["coding"], seed=True, train=False)
    assert report["seed"]["coding"]["accepted"] >= 1
    assert "coding" in report["eval"]
    assert Path(report["path"]).exists()
