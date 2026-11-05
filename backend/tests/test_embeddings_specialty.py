from pathlib import Path

from app.config import Settings, get_settings
from app.distillation.embeddings import seed_embeddings_curriculum
from app.distillation.engine import DistillationEngine, reset_distillation_engine
from app.eval.suite import suite_for
from app.ownership.handoff import OwnershipHandoff, reset_ownership_handoff


def test_embeddings_seed_and_suite(tmp_path: Path):
    get_settings.cache_clear()
    reset_distillation_engine()
    reset_ownership_handoff()
    settings = Settings(
        learning_data_root=tmp_path / "learning",
        distillation_data_root=tmp_path / "distill",
        distillation_enabled=True,
        auto_retire_ready_teachers=False,
    )
    engine = DistillationEngine(settings=settings)
    out = seed_embeddings_curriculum(settings=settings, engine=engine)
    assert out["accepted"] >= 3
    assert len(suite_for("embeddings")) >= 3
    meter = OwnershipHandoff(settings=settings).coverage_meter()
    assert meter["specialties_total"] == 6
    get_settings.cache_clear()
    reset_distillation_engine()
    reset_ownership_handoff()


def test_cost_per_task_in_metrics(tmp_path: Path):
    from app.gateway.intelligent_router import IntelligentModelRouter, reset_intelligent_router

    get_settings.cache_clear()
    reset_intelligent_router()
    settings = Settings(learning_data_root=tmp_path / "learning")
    router = IntelligentModelRouter(settings=settings)
    router.record_internal(tokens_in=1000, tokens_out=500)
    router.record_teacher(escalated=True, tokens_in=1000, tokens_out=500)
    m = router.metrics.as_dict()
    assert m["successful_tasks"] == 2
    assert m["estimated_cost_usd"] > 0
    assert m["cost_per_successful_task_usd"] > 0
    get_settings.cache_clear()
    reset_intelligent_router()
