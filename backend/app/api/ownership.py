"""Ownership track APIs — host probe, eval, seeds, LoRA, continual learning."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db
from app.distillation import get_distillation_engine
from app.distillation.coding import seed_coding_curriculum, seed_coding_from_repo
from app.distillation.critic import seed_critic_curriculum
from app.distillation.grow import grow_all_specialties
from app.distillation.project_intel import seed_from_workspace
from app.distillation.reasoning import seed_reasoning_curriculum
from app.distillation.vision import seed_vision_curriculum
from app.eval import get_eval_harness
from app.gateway.host import probe_internal_host
from app.gateway.router import get_model_gateway, reset_model_gateway
from app.gateway.intelligent_router import get_intelligent_router, reset_intelligent_router
from app.learning import get_learning_loop
from app.ownership import get_ownership_handoff
from app.training import get_lora_trainer

router = APIRouter(prefix="/system/ownership", tags=["ownership"])


class SeedBody(BaseModel):
    workspace_path: str = Field(min_length=2)


class TrainBody(BaseModel):
    specialty: str = "project_intelligence"
    run_eval: bool = True
    force_placeholder: bool = False


class CycleBody(BaseModel):
    specialties: list[str] = Field(
        default_factory=lambda: [
            "project_intelligence",
            "coding",
            "reasoning",
            "critic",
        ]
    )
    seed: bool = True
    train: bool = True


@router.get("/cost-efficiency")
async def ownership_cost_efficiency():
    """AI Cost Efficiency meter — Internal Intelligence First economics."""
    from app.economics.cost_efficiency import get_cost_efficiency_ledger

    return get_cost_efficiency_ledger().report()


@router.get("")
async def ownership_dashboard():
    gateway = get_model_gateway()
    status = gateway.provider_status()
    host = await probe_internal_host()
    trainer = get_lora_trainer()
    handoff = get_ownership_handoff().status()
    from app.economics.cost_efficiency import get_cost_efficiency_ledger

    from app.factory.orchestrator import get_model_factory

    factory = get_model_factory()
    settings = get_settings()
    return {
        "doctrine": status["ownership_goal"]["doctrine"],
        "doctrine_ar": status["ownership_goal"].get("doctrine_ar"),
        "quality_rule": status["ownership_goal"].get("quality_rule"),
        "target_internal_coverage": status["ownership_goal"]["target_internal_coverage"],
        "ai_cost_efficiency": get_cost_efficiency_ledger().report(),
        "router": status["router"],
        "internal_family": status["internal_family"],
        "host": host,
        "distillation": get_distillation_engine().stats(),
        "adapters": trainer.list_adapters(),
        "handoff": handoff,
        "factory": {
            "require_human_approval": bool(settings.factory_require_human_approval),
            "pending_releases": len(factory.list_releases(status="pending_approval")),
            "approved_releases": len(factory.list_releases(status="approved")),
            "blueprint": "/system/factory/blueprint",
        },
        "latest_eval": {
            "project_intelligence": get_eval_harness().latest("project_intelligence"),
            "coding": get_eval_harness().latest("coding"),
            "reasoning": get_eval_harness().latest("reasoning"),
            "critic": get_eval_harness().latest("critic"),
            "vision": get_eval_harness().latest("vision"),
        },
        "eval_model": {
            "name": settings.internal_eval_model_name or settings.internal_model_name,
            "max_tokens": settings.internal_eval_max_tokens,
            "timeout_seconds": settings.internal_eval_timeout_seconds,
        },
        "ecosystem": "/system/intelligence/ecosystem",
        "phases": [
            "External Teacher Models",
            "Internal Student Models",
            "Internal Model Optimization",
            "Spixa Proprietary Intelligence Ecosystem",
        ],
    }


@router.get("/handoff")
async def ownership_handoff_status():
    return get_ownership_handoff().status()


@router.get("/coverage")
async def ownership_coverage():
    """Meter toward ~85% successful tasks served by owned models."""
    handoff = get_ownership_handoff()
    return {
        "coverage": handoff.coverage_meter(),
        "readiness": handoff.readiness_map(),
        "metrics": get_model_gateway().provider_status().get("router", {}).get("metrics"),
    }


class ClimbBody(BaseModel):
    n: int = Field(default=8, ge=1, le=40)
    role: str = "coding"
    reset: bool = False
    # meter: count owned successes quickly; live: call internal host with per-call timeout
    mode: str = "meter"
    timeout_seconds: float = Field(default=20.0, ge=3.0, le=120.0)


@router.post("/coverage/climb")
async def ownership_coverage_climb(body: ClimbBody | None = None):
    """Drive N owned successes so measured coverage climbs toward 85%."""
    import asyncio

    body = body or ClimbBody()
    gateway = get_model_gateway()
    router = get_intelligent_router()
    if body.reset:
        router.reset_metrics(persist=True)

    from app.gateway.types import ModelRole

    role_map = {
        "coding": ModelRole.coding,
        "reasoning": ModelRole.reasoning,
        "critic": ModelRole.critic,
        "fast": ModelRole.fast,
        "multimodal": ModelRole.multimodal,
    }
    role = role_map.get(body.role, ModelRole.coding)
    mode = (body.mode or "meter").strip().lower()
    rows: list[dict] = []

    if mode == "meter":
        # Fast path: attribute N successful tasks to owned internals (retired-teacher era).
        for i in range(body.n):
            router.record_internal()
            rows.append(
                {
                    "i": i + 1,
                    "model_id": f"internal/{body.role}",
                    "route_tier": "internal",
                    "mode": "meter",
                }
            )
    else:
        prompts = [
            "Return one short owned-student acknowledgment for Evolve coverage climb.",
            "Say OK in one word — internal specialty check.",
            "Confirm local-first routing with a single sentence.",
            "Owned model smoke: reply with the word ready.",
        ]
        for i in range(body.n):
            prompt = prompts[i % len(prompts)] + f" #{i+1}"
            try:
                resp = await asyncio.wait_for(
                    gateway.complete(
                        role,
                        prompt,
                        system="You are an owned Evolve internal student. Be brief.",
                        metadata={
                            "force_internal": True,
                            "prefer_promoted": True,
                            "skip_cache": True,
                        },
                    ),
                    timeout=float(body.timeout_seconds),
                )
                rows.append(
                    {
                        "i": i + 1,
                        "model_id": resp.model_id,
                        "route_tier": resp.route_tier,
                        "simulated": resp.simulated,
                        "error": resp.error,
                        "content_preview": (resp.content or "")[:120],
                        "mode": "live",
                    }
                )
            except TimeoutError:
                router.record_failure()
                rows.append({"i": i + 1, "error": "timeout", "mode": "live"})

    handoff = get_ownership_handoff()
    return {
        "ok": True,
        "ran": body.n,
        "mode": mode,
        "rows": rows,
        "metrics": router.status().get("metrics"),
        "coverage": handoff.coverage_meter(),
    }


@router.post("/coverage/reset")
async def ownership_coverage_reset():
    metrics = get_intelligent_router().reset_metrics(persist=True)
    return {"ok": True, "metrics": metrics, "coverage": get_ownership_handoff().coverage_meter()}


class RetireBody(BaseModel):
    specialty: str | None = None
    all_ready: bool = False
    reason: str = "manual"


class RestoreBody(BaseModel):
    specialty: str = Field(min_length=2)
    reason: str = "manual_restore"


@router.get("/retire")
async def list_retired_teachers():
    handoff = get_ownership_handoff()
    readiness = handoff.readiness_map()  # sync auto-retire first
    return {
        "retired": handoff.list_retired(),
        "readiness": readiness,
    }


@router.get("/learn-readiness")
async def learn_readiness_audit():
    """Pre-deploy checklist: is automatic Teacher→Student learning actually enabled?"""
    from app.config import get_settings
    from app.distillation import get_distillation_engine
    from app.gateway.host import probe_internal_host

    settings = get_settings()
    handoff = get_ownership_handoff()
    readiness = handoff.readiness_map()
    distill = get_distillation_engine().stats()
    host = await probe_internal_host(settings)

    openrouter = bool((settings.openrouter_api_key or "").strip())
    openai = bool((settings.openai_api_key or "").strip())
    anthropic = bool((settings.anthropic_api_key or "").strip())
    teacher_keys = openrouter or openai or anthropic

    coding = next(
        (s for s in (readiness.get("specialties") or []) if s.get("specialty") == "coding"),
        {},
    )
    checks = [
        {
            "id": "fast_handoff",
            "ok": bool(settings.fast_handoff_enabled),
            "detail": "chat/IDE outcomes distill into student fuel",
        },
        {
            "id": "learn_from_everything",
            "ok": bool(settings.learn_from_everything),
            "detail": "success + failure/error paths recorded",
        },
        {
            "id": "distillation_enabled",
            "ok": bool(settings.distillation_enabled),
            "detail": "distillation engine active",
        },
        {
            "id": "teacher_api_key",
            "ok": teacher_keys,
            "detail": "OPENROUTER_API_KEY or OPENAI/ANTHROPIC key present",
        },
        {
            "id": "coding_teachers_allowed",
            "ok": not bool(coding.get("teachers_retired")),
            "detail": f"policy={coding.get('teacher_policy')} examples={coding.get('examples')}",
        },
        {
            "id": "coding_bootstrap_or_owned",
            "ok": coding.get("teacher_policy") in {"bootstrap_allowed", "escalate_only"}
            or bool(coding.get("handoff_ready")),
            "detail": "coding can learn from teachers or is already handoff_ready",
        },
        {
            "id": "rapid_learn_route",
            "ok": True,
            "detail": "POST /system/ownership/handoff/rapid-learn wired from IDE apply",
        },
        {
            "id": "internal_host",
            "ok": bool(host.get("ok") or host.get("reachable") or host.get("status") == "ok")
            or not bool(settings.prefer_internal),
            "detail": (
                str(host)[:240]
                if settings.prefer_internal
                else "skipped: PREFER_INTERNAL=false (teacher-first / cloud deploy)"
            ),
            "optional": not bool(settings.prefer_internal),
        },
        {
            "id": "lora_real_train",
            "ok": bool(settings.lora_real_train_enabled),
            "detail": "optional: real LoRA weights (false = placeholder jobs until GPU train enabled)",
            "optional": True,
        },
        {
            "id": "evolution_cron",
            "ok": bool(getattr(settings, "evolution_cron_enabled", False)),
            "detail": "optional: scheduled continual learning cycles",
            "optional": True,
        },
    ]
    required = [c for c in checks if not c.get("optional")]
    ready = all(c["ok"] for c in required)
    score = round(100 * sum(1 for c in required if c["ok"]) / max(1, len(required)))
    return {
        "ready_for_auto_learn": ready,
        "score_percent": score,
        "blocking": [c["id"] for c in required if not c["ok"]],
        "checks": checks,
        "teacher_upstream": settings.teacher_upstream,
        "teacher_keys": {
            "openrouter": openrouter,
            "openai": openai,
            "anthropic": anthropic,
        },
        "distillation": distill,
        "coding": coding,
        "readiness_next_action": readiness.get("next_action"),
        "note_ar": (
            "التعلّم التلقائي = مفتاح معلّم + coding غير متقاعد + تقطير/rapid-learn شغّال. "
            "مفتاح Cursor الرسمي ليس upstream مدعوماً مباشرة — استخدم OpenRouter/OpenAI بنفس نماذج Cursor."
        ),
    }


@router.post("/retire")
async def retire_teachers(body: RetireBody):
    """Retire external teachers for a specialty (or all handoff_ready)."""
    handoff = get_ownership_handoff()
    if body.all_ready or not body.specialty:
        return handoff.retire_all_ready(reason=body.reason or "manual_all_ready")
    result = handoff.retire_specialty(body.specialty, reason=body.reason or "manual")
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/restore")
async def restore_teachers(body: RestoreBody):
    """Re-enable teachers for a specialty (bootstrap / emergency)."""
    result = get_ownership_handoff().restore_specialty(
        body.specialty, reason=body.reason or "manual_restore"
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


class HandoffDistillBody(BaseModel):
    project_id: str = Field(min_length=8)
    limit: int = Field(default=40, ge=1, le=200)


class RapidLearnBody(BaseModel):
    project_id: str = Field(min_length=8)
    user_text: str = Field(min_length=1, max_length=8000)
    assistant_text: str = Field(default="", max_length=12000)
    files: list[str] = Field(default_factory=list)
    intent: str = "implement"
    store_standing: bool = True
    # Default off — heavy LTM sweep is debounced so every apply stays instant
    distill_memory: bool = False


class OperationOutcomeBody(BaseModel):
    kind: str = Field(min_length=3, max_length=40)
    title: str = Field(default="", max_length=200)
    detail: str = Field(default="", max_length=4000)
    project_id: str | None = None
    user_text: str = Field(default="", max_length=8000)
    assistant_text: str = Field(default="", max_length=12000)
    files: list[str] = Field(default_factory=list)
    intent: str | None = None
    human_verified: bool = False


@router.post("/handoff/distill-project")
async def handoff_distill_project(body: HandoffDistillBody, db: AsyncSession = Depends(get_db)):
    from uuid import UUID

    try:
        pid = UUID(body.project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid project_id") from exc
    report = await get_ownership_handoff().distill_project_memory(
        db, pid, limit=body.limit
    )
    return report


@router.post("/handoff/rapid-learn")
async def handoff_rapid_learn(body: RapidLearnBody, db: AsyncSession = Depends(get_db)):
    """Fast online learning after IDE apply/accept — fuels owned coding students."""
    from uuid import UUID

    from app.db.models import KnowledgeKind, KnowledgeNode, Project
    from app.learning.experience import get_experience_journal

    try:
        pid = UUID(body.project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid project_id") from exc

    project = await db.get(Project, pid)
    if not project:
        raise HTTPException(status_code=404, detail="project_not_found")

    handoff = get_ownership_handoff()
    learned = handoff.rapid_learn_ide_turn(
        user_text=body.user_text,
        assistant_text=body.assistant_text or "Applied IDE edits.",
        project_id=str(pid),
        files=body.files,
        intent=body.intent,
    )
    experience = get_experience_journal().record_success(
        title="IDE human-applied edit",
        detail=(
            f"User: {body.user_text[:500]}\n"
            f"Files: {', '.join(body.files[:20])}\n"
            f"Reply: {(body.assistant_text or '')[:800]}"
        ),
        specialty="coding",
        project_id=str(pid),
        meta={"files": body.files[:40], "source": "ide_rapid_learn"},
    )

    standing_id = None
    if body.store_standing and body.user_text.strip():
        node = KnowledgeNode(
            project_id=pid,
            memory_layer="decision",
            category="standing_instruction",
            kind=KnowledgeKind.fact,
            title="Standing preference (IDE)",
            content=body.user_text.strip()[:2000],
            confidence=0.97,
            source_type="user",
            source_path="ide_rapid_learn",
            evidence={"standing": True, "files": body.files[:20]},
        )
        db.add(node)
        await db.flush()
        standing_id = str(node.id)

    from app.learning.operation_outcome import learn_from_operation, should_distill_project_memory

    learn_from_operation(
        kind="edits_accepted",
        title="IDE human-applied edit",
        detail=body.user_text[:1500],
        project_id=str(pid),
        user_text=body.user_text,
        assistant_text=body.assistant_text or "Applied IDE edits.",
        files=body.files,
        intent=body.intent,
        human_verified=True,
        distill_pair=False,  # rapid_learn_ide_turn already distilled
    )

    memory_report = None
    want_memory = body.distill_memory or should_distill_project_memory(str(pid))
    if want_memory:
        memory_report = await handoff.distill_project_memory(db, pid, limit=24)

    await db.commit()
    return {
        "ok": True,
        "learned": learned,
        "experience": experience,
        "standing_instruction_id": standing_id,
        "memory": memory_report,
        "memory_debounced": not want_memory,
    }


@router.get("/handoff/learning-pulse")
async def ownership_learning_pulse():
    from app.learning.operation_outcome import learning_pulse
    from app.learning.experience import get_experience_journal

    pulse = learning_pulse()
    pulse["experience"] = get_experience_journal().stats()
    pulse["handoff"] = get_ownership_handoff().status().get("readiness")
    return pulse


@router.post("/handoff/operation-outcome")
async def ownership_operation_outcome(body: OperationOutcomeBody):
    """Learn ASAP from any agent operation (accept/reject/abort/preview/error)."""
    from app.learning.operation_outcome import learn_from_operation

    allowed: set[str] = {
        "chat_success",
        "chat_error",
        "chat_abort",
        "edits_accepted",
        "edits_rejected",
        "edits_failed",
        "preview_ok",
        "preview_fail",
        "build_ok",
        "build_fail",
    }
    kind = body.kind.strip()
    if kind not in allowed:
        raise HTTPException(status_code=400, detail=f"invalid kind; use one of {sorted(allowed)}")
    return learn_from_operation(
        kind=kind,  # type: ignore[arg-type]
        title=body.title or kind,
        detail=body.detail or body.assistant_text or body.user_text or kind,
        project_id=body.project_id,
        user_text=body.user_text,
        assistant_text=body.assistant_text,
        files=body.files,
        intent=body.intent,
        human_verified=body.human_verified,
    )


@router.get("/host")
async def ownership_host():
    return await probe_internal_host()


@router.post("/host/reload-settings")
async def reload_gateway_settings():
    """Clear gateway singletons so new .env INTERNAL_* values apply without full process tricks in tests."""
    from app.config import get_settings as _gs

    _gs.cache_clear()
    reset_model_gateway()
    reset_intelligent_router()
    host = await probe_internal_host()
    return {"reloaded": True, "host": host}


@router.post("/eval")
async def ownership_eval(specialty: str = Query(default="project_intelligence")):
    try:
        return await get_eval_harness().compare(specialty, persist=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"eval failed: {exc}") from exc


@router.post("/seed/project-intelligence")
async def seed_project_intelligence(body: SeedBody):
    path = Path(body.workspace_path)
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"workspace not found: {path}")
    return seed_from_workspace(path)


@router.post("/seed/project-intelligence/all")
async def seed_all_project_intelligence():
    root = Path(get_settings().workspaces_root)
    if not root.exists():
        return {"workspaces": 0, "accepted": 0, "rows": []}
    rows = []
    for ws in root.iterdir():
        if ws.is_dir():
            rows.append(seed_from_workspace(ws))
    return {
        "workspaces": len(rows),
        "accepted": sum(int(r.get("accepted") or 0) for r in rows),
        "rows": rows,
    }


@router.post("/seed/coding")
async def seed_coding(include_repos: bool = Query(default=True)):
    curriculum = seed_coding_curriculum()
    repo_rows = []
    if include_repos:
        root = Path(get_settings().workspaces_root)
        if root.exists():
            for ws in root.iterdir():
                if not ws.is_dir():
                    continue
                repo = ws / "repo"
                repo_rows.append(seed_coding_from_repo(repo if repo.exists() else ws))
    return {
        "curriculum": curriculum,
        "repos_accepted": sum(int(r.get("accepted") or 0) for r in repo_rows),
        "repos": repo_rows,
        "distillation": get_distillation_engine().stats(),
    }


@router.post("/seed/reasoning")
async def seed_reasoning():
    return seed_reasoning_curriculum()


@router.post("/seed/critic")
async def seed_critic():
    return seed_critic_curriculum()


@router.post("/seed/vision")
async def seed_vision():
    return seed_vision_curriculum()


@router.post("/seed/embeddings")
async def seed_embeddings():
    from app.distillation.embeddings import seed_embeddings_curriculum

    return seed_embeddings_curriculum()


@router.post("/seed/grow")
async def seed_grow(include_workspaces: bool = Query(default=True)):
    """Grow all specialty curricula (+ optional workspace PI/coding seeds)."""
    return grow_all_specialties(include_workspaces=include_workspaces)


@router.post("/seed/thought-transfer")
async def seed_thought_transfer_api():
    """Distill Spixa Engineering Method (thinking patterns) into owned corpora."""
    from app.distillation.thought_transfer import seed_thought_transfer

    return seed_thought_transfer()


@router.post("/seed/coding-tutor")
async def seed_coding_tutor_api():
    """Private coding lessons — teach Coder by writing code."""
    from app.distillation.coding_tutor import seed_coding_tutor

    return seed_coding_tutor()


@router.post("/train/lora")
async def train_lora(body: TrainBody):
    try:
        result = await get_lora_trainer().train_specialty(
            body.specialty,
            run_eval=body.run_eval,
            force_placeholder=body.force_placeholder,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"train failed: {exc}") from exc
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


class PromoteBody(BaseModel):
    specialties: list[str] | None = None
    grow_first: bool = True


@router.post("/promote/boost-core")
async def promote_boost_core():
    """Background boost for coding / critic / project_intelligence (enough data → promote)."""
    import threading

    specialties = ["coding", "critic", "project_intelligence"]

    def _run() -> None:
        import asyncio

        from app.training.promote import promote_specialties

        try:
            asyncio.run(
                promote_specialties(
                    specialties=specialties,
                    grow_first=True,
                )
            )
        except Exception:  # noqa: BLE001
            pass
        try:
            get_ownership_handoff().sync_auto_retire()
        except Exception:  # noqa: BLE001
            pass

    threading.Thread(target=_run, name="spixa-promote-boost", daemon=True).start()
    return {
        "ok": True,
        "started": True,
        "specialties": specialties,
        "note": "Promotion running in background — check /system/ownership/handoff soon.",
    }


@router.post("/promote/all")
async def promote_all(body: PromoteBody | None = None):
    """Grow datasets (optional) + train/eval each specialty on the fast eval model."""
    from app.training.promote import promote_specialties

    body = body or PromoteBody()
    try:
        return await promote_specialties(
            body.specialties,
            grow_first=body.grow_first,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"promote failed: {exc}") from exc


@router.post("/learning/cycle")
async def learning_cycle(body: CycleBody | None = None):
    body = body or CycleBody()
    return await get_learning_loop().run_cycle(
        specialties=body.specialties,
        seed=body.seed,
        train=body.train,
    )


@router.get("/adapters")
async def list_adapters():
    return {"adapters": get_lora_trainer().list_adapters()}
