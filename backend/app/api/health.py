from fastapi import APIRouter

from app import __version__
from app.agents.registry import list_agents
from app.agents.runtime import departments_overview
from app.config import get_settings
from app.gateway import get_model_gateway
from app.intelligence.languages import language_catalog
from app.knowledge.memory import LAYER_DESCRIPTIONS, MEMORY_LAYERS

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": __version__,
        "env": settings.app_env,
    }


@router.get("/system/models")
async def model_routes():
    gateway = get_model_gateway()
    status = gateway.provider_status()
    from app.distillation import get_distillation_engine

    return {
        "routes": status["routes"],
        "providers": status["providers"],
        "chiefs": status.get("chiefs"),
        "teacher_upstream": status.get("teacher_upstream"),
        "teacher_upstream_active": status.get("teacher_upstream_active"),
        "teacher_upstream_live": status.get("teacher_upstream_live"),
        "teacher_bootstrap_first": status.get("teacher_bootstrap_first"),
        "force_simulate": status["force_simulate"],
        "prefer_internal": status["prefer_internal"],
        "mode": "simulate" if status["force_simulate"] else "local_first",
        "internal_family": status["internal_family"],
        "router": status["router"],
        "ownership_goal": status["ownership_goal"],
        "distillation": get_distillation_engine().stats(),
    }


@router.post("/system/models/probe")
async def model_probe(
    role: str = "fast",
    force_teacher: bool = False,
    force_provider: str | None = None,
):
    """Tiny completion to verify Local-First / teacher escalate wiring."""
    from app.gateway.router import ModelRole

    try:
        model_role = ModelRole(role)
    except ValueError:
        model_role = ModelRole.fast
    meta: dict = {"probe": True, "force_teacher": force_teacher, "skip_cache": True}
    pref = (force_provider or "").strip().lower()
    if pref in {"cursor", "openrouter", "openai", "anthropic"}:
        meta["force_teacher"] = True
        meta["force_provider"] = pref
    response = await get_model_gateway().complete(
        model_role,
        "Reply with exactly: ok",
        system="You are a health probe for Evolve Model Gateway. Be terse.",
        metadata=meta,
    )
    return {
        "role": response.role.value,
        "model_id": response.model_id,
        "route_tier": response.route_tier,
        "confidence": response.confidence,
        "simulated": response.simulated,
        "error": response.error,
        "tokens_in": response.tokens_in,
        "tokens_out": response.tokens_out,
        "content_preview": (response.content or "")[:240],
        "router": get_model_gateway().router.status(),
    }


@router.get("/system/agents")
async def agents():
    from app.agents.hierarchy import hierarchy_overview

    rows = list_agents()
    return {
        "agents": rows,
        "count": len(rows),
        "hierarchy": hierarchy_overview(),
    }


@router.get("/system/departments")
async def departments():
    return {"departments": departments_overview()}


@router.get("/system/languages")
async def languages():
    return {"languages": language_catalog(), "count": len(language_catalog())}


@router.get("/system/memory-layers")
async def memory_layers():
    return {
        "layers": [
            {"id": layer, "description": LAYER_DESCRIPTIONS[layer]} for layer in MEMORY_LAYERS
        ]
    }


@router.get("/system/deploy-adapters")
async def deploy_adapters():
    from app.config import get_settings
    from app.deployment.adapters import list_deploy_adapters

    settings = get_settings()
    return {
        "active": settings.deploy_provider,
        "azure_deploy_enabled": settings.azure_deploy_enabled,
        "adapters": list_deploy_adapters(),
        "note": "Human gate required. Real Azure calls need AZURE_DEPLOY_ENABLED=true and force_simulate=false.",
    }
