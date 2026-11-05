from pathlib import Path
import pytest

from app.config import Settings
from app.distillation.engine import DistillationEngine, reset_distillation_engine
from app.distillation.project_intel import seed_from_workspace
from app.eval.harness import EvalHarness
from app.eval.suite import score_answer, suite_for
from app.gateway.intelligent_router import IntelligentModelRouter, reset_intelligent_router
from app.gateway.router import ModelGateway, reset_model_gateway
from app.training.lora import LoRATrainer


@pytest.fixture(autouse=True)
def _reset():
    reset_model_gateway()
    reset_intelligent_router()
    reset_distillation_engine()
    yield
    reset_model_gateway()
    reset_intelligent_router()
    reset_distillation_engine()


def test_score_answer_keywords():
    case = suite_for("project_intelligence")[0]
    assert score_answer(case, "API backend frontend layers and routes") > 0.5
    assert score_answer(case, "[simulated:fast] empty") < 0.3


@pytest.mark.asyncio
async def test_eval_compare_persists(tmp_path: Path):
    settings = Settings(
        openai_api_key="",
        prefer_internal=True,
        model_cache_enabled=False,
        distillation_enabled=False,
        eval_data_root=tmp_path / "eval",
        internal_model_base_url="",
    )
    gateway = ModelGateway(settings=settings, router=IntelligentModelRouter(settings=settings))
    harness = EvalHarness(settings=settings, gateway=gateway)
    report = await harness.compare("project_intelligence", persist=True)
    assert "student_score" in report
    assert "teacher_score" in report
    assert report["promote"] is False  # stubs cannot promote
    assert (tmp_path / "eval" / "latest-project_intelligence.json").exists()


def test_seed_project_intel(tmp_path: Path):
    repo = tmp_path / "ws" / "repo"
    repo.mkdir(parents=True)
    (repo / "main.py").write_text("def health():\n    return {'ok': True}\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    settings = Settings(distillation_enabled=True, distillation_data_root=tmp_path / "distill")
    engine = DistillationEngine(settings=settings)
    result = seed_from_workspace(tmp_path / "ws", settings=settings, engine=engine)
    assert result["accepted"] >= 1
    assert engine.stats()["examples_by_specialty"]["project_intelligence"] >= 1


@pytest.mark.asyncio
async def test_lora_train_needs_examples(tmp_path: Path):
    settings = Settings(
        distillation_data_root=tmp_path / "distill",
        training_artifacts_root=tmp_path / "train",
        eval_data_root=tmp_path / "eval",
        lora_min_examples=3,
        openai_api_key="",
        model_cache_enabled=False,
    )
    trainer = LoRATrainer(settings=settings)
    result = await trainer.train_specialty("project_intelligence", run_eval=False)
    assert result["ok"] is False

    # seed 3 examples
    engine = DistillationEngine(settings=settings)
    for i in range(3):
        engine.ingest_teacher_output(
            role="project_intelligence",
            prompt=f"q{i} explain architecture layers api backend frontend",
            system=None,
            teacher_model="teacher",
            teacher_output=f"fact inference evidence workspace isolation layers api backend frontend {i}",
            metadata={"specialty": "project_intelligence", "tools_ok": True, "distill": True},
        )
    result = await trainer.train_specialty(
        "project_intelligence",
        run_eval=False,
        force_placeholder=False,
    )
    assert result["ok"] is True
    assert result["job"]["status"] == "placeholder_ready_for_gpu"
    assert result["job"]["promoted"] is False

    gateway = ModelGateway(settings=settings, router=IntelligentModelRouter(settings=settings))
    harness = EvalHarness(settings=settings, gateway=gateway)
    report = await harness.compare("project_intelligence", persist=True)
    assert report["promote"] is False
