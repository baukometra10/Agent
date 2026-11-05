"""Promote specialty adapters after held-out eval gates (fast eval model)."""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.distillation.grow import grow_all_specialties
from app.eval.harness import EvalHarness, get_eval_harness
from app.gateway.intelligent_router import IntelligentModelRouter
from app.gateway.router import ModelGateway
from app.training.lora import LoRATrainer, get_lora_trainer

DEFAULT_SPECIALTIES = (
    "coding",
    "reasoning",
    "critic",
    "vision",
    "project_intelligence",
    "embeddings",
)


async def promote_specialties(
    specialties: list[str] | None = None,
    *,
    grow_first: bool = True,
    settings: Settings | None = None,
    trainer: LoRATrainer | None = None,
    harness: EvalHarness | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    specialties = specialties or list(DEFAULT_SPECIALTIES)
    grow = None
    if grow_first:
        from app.distillation.engine import DistillationEngine

        engine = DistillationEngine(settings=settings)
        grow = grow_all_specialties(settings=settings, engine=engine, include_workspaces=True)

    trainer = trainer or LoRATrainer(settings=settings)
    if harness is None:
        gateway = ModelGateway(settings=settings, router=IntelligentModelRouter(settings=settings))
        harness = EvalHarness(settings=settings, gateway=gateway)

    results: dict[str, Any] = {}
    promoted = 0
    candidate_ready = 0
    factory_proposals: list[dict[str, Any]] = []

    from app.factory.orchestrator import ModelFactory

    factory = ModelFactory(settings=settings)

    for specialty in specialties:
        job = await trainer.train_specialty(
            specialty,
            run_eval=True,
            force_placeholder=False,
            harness=harness,
        )
        if not job.get("ok"):
            job = await trainer.train_specialty(
                specialty,
                run_eval=True,
                force_placeholder=True,
                harness=harness,
            )
        results[specialty] = job
        inner = job.get("job") or {}
        if inner.get("promoted"):
            promoted += 1
        if inner.get("candidate_ready") or inner.get("eval_gates_passed"):
            candidate_ready += 1
            eval_report = job.get("eval")
            if not isinstance(eval_report, dict) or "gates" not in eval_report:
                eval_report = harness.latest(specialty) or eval_report
            proposed = factory.propose_release(
                specialty=specialty,
                eval_report=eval_report if isinstance(eval_report, dict) else None,
                source="promote_all",
            )
            if proposed:
                factory_proposals.append(proposed)

    return {
        "ok": True,
        "promoted_count": promoted,
        "candidate_ready_count": candidate_ready,
        "factory_proposals": factory_proposals,
        "require_human_approval": bool(settings.factory_require_human_approval),
        "note": (
            "Eval pass creates factory release proposals when "
            "FACTORY_REQUIRE_HUMAN_APPROVAL=true; approve via /system/factory/releases/{id}/approve."
        ),
        "total": len(specialties),
        "eval_model": settings.internal_eval_model_name or settings.internal_model_name,
        "grow": {
            "ran": bool(grow_first),
            "summary": {
                k: (v.get("accepted") if isinstance(v, dict) else None)
                for k, v in (grow or {}).items()
                if k in ("coding", "reasoning", "critic", "vision", "project_intelligence")
            }
            if grow
            else None,
        },
        "results": results,
        "adapters": trainer.list_adapters(),
    }
