from unittest.mock import AsyncMock, patch

import pytest

from app.config import Settings
from app.distillation.engine import DistillationEngine
from app.gateway.intelligent_router import IntelligentModelRouter, reset_intelligent_router
from app.gateway.providers import ProviderError, strip_model_id
from app.gateway.router import ModelGateway, ModelRole, reset_model_gateway


@pytest.fixture(autouse=True)
def _reset_singletons():
    reset_model_gateway()
    reset_intelligent_router()
    yield
    reset_model_gateway()
    reset_intelligent_router()


@pytest.mark.asyncio
async def test_gateway_simulates_without_keys():
    settings = Settings(
        openai_api_key="",
        anthropic_api_key="",
        prefer_internal=True,
        internal_model_base_url="",
        model_cache_enabled=False,
    )
    router = IntelligentModelRouter(settings=settings)
    gateway = ModelGateway(settings=settings, router=router)
    response = await gateway.complete(ModelRole.fast, "classify this file", metadata={"skip_cache": True})
    # stub internal escalates → teacher missing key → simulate
    assert response.simulated is True
    assert response.role == ModelRole.fast
    assert response.route_tier in {"teacher", "simulate", "internal"}


@pytest.mark.asyncio
async def test_local_first_then_escalate_to_teacher():
    settings = Settings(
        openai_api_key="sk-live",
        prefer_internal=True,
        teacher_bootstrap_first=False,
        internal_model_base_url="",
        internal_confidence_threshold=0.55,
        model_cache_enabled=False,
        model_gateway_force_simulate=False,
        distillation_enabled=False,
        anthropic_api_key="",
    )
    router = IntelligentModelRouter(settings=settings)
    gateway = ModelGateway(settings=settings, router=router)

    async def fake_openai(**kwargs):
        return ("teacher-answer", 10, 4, {"id": "c1", "usage": {"prompt_tokens": 10}})

    with patch("app.gateway.router.openai_chat", new=AsyncMock(side_effect=fake_openai)):
        response = await gateway.complete(
            ModelRole.fast,
            "hi",
            metadata={"skip_cache": True},
        )
    assert response.content == "teacher-answer"
    assert response.route_tier == "teacher"
    assert router.metrics.escalations >= 1
    assert router.metrics.teacher_ok >= 1


def test_auto_teacher_upstream_prefers_cursor_when_live():
    settings = Settings(
        teacher_upstream="auto",
        cursor_api_key="cursor-key",
        openrouter_api_key="or-key",
        model_gateway_force_simulate=False,
    )
    gateway = ModelGateway(settings=settings, router=IntelligentModelRouter(settings=settings))
    assert gateway.active_teacher_upstream() == "cursor"
    assert gateway._use_cursor_upstream() is True


def test_stuck_internal_escalates_even_when_handoff_ready(monkeypatch):
    settings = Settings(
        openai_api_key="sk-live",
        prefer_internal=True,
        teacher_bootstrap_first=False,
        prefer_promoted_internal=True,
        promoted_no_escalate=True,
        internal_confidence_threshold=0.55,
        model_cache_enabled=False,
        distillation_enabled=False,
        model_gateway_force_simulate=False,
    )
    router = IntelligentModelRouter(settings=settings)
    from app.gateway.types import ModelResponse, ModelRole

    stuck = ModelResponse(
        role=ModelRole.coding,
        model_id="internal/coding",
        content="I don't know how to continue",
        simulated=False,
    )
    escalate, conf = router.should_escalate(
        stuck,
        metadata={"prefer_promoted": True, "ide_coding": True},
    )
    assert escalate is True
    assert conf < 0.3


@pytest.mark.asyncio
async def test_bootstrap_teacher_first_when_specialty_not_ready():
    settings = Settings(
        openai_api_key="sk-live",
        prefer_internal=True,
        teacher_bootstrap_first=True,
        internal_model_base_url="",
        model_cache_enabled=False,
        distillation_enabled=False,
        model_gateway_force_simulate=False,
        anthropic_api_key="",
        openrouter_api_key="",
    )
    router = IntelligentModelRouter(settings=settings)
    gateway = ModelGateway(settings=settings, router=router)
    decision = router.decide(ModelRole.coding, metadata={"skip_cache": True})
    assert decision.tier.value == "teacher"
    assert decision.reason == "bootstrap_teacher_first"

    with patch(
        "app.gateway.router.openai_chat",
        new=AsyncMock(return_value=("bootstrap-teacher", 3, 2, {"id": "b1"})),
    ):
        response = await gateway.complete(
            ModelRole.coding,
            "build a button",
            metadata={"skip_cache": True},
        )
    assert response.content == "bootstrap-teacher"
    assert response.route_tier == "teacher"
    assert router.metrics.teacher_ok >= 1


@pytest.mark.asyncio
async def test_force_teacher_skips_internal():
    settings = Settings(
        openai_api_key="sk-live",
        prefer_internal=True,
        model_cache_enabled=False,
        distillation_enabled=False,
        model_gateway_force_simulate=False,
        internal_model_base_url="",
    )
    gateway = ModelGateway(settings=settings, router=IntelligentModelRouter(settings=settings))

    with patch(
        "app.gateway.router.openai_chat",
        new=AsyncMock(return_value=("direct", 1, 1, {"id": "x"})),
    ):
        response = await gateway.complete(
            ModelRole.fast,
            "hi",
            metadata={"force_teacher": True, "skip_cache": True},
        )
    assert response.content == "direct"
    assert response.route_tier == "teacher"


@pytest.mark.asyncio
async def test_cache_hit():
    settings = Settings(
        openai_api_key="sk-live",
        prefer_internal=True,
        model_cache_enabled=True,
        distillation_enabled=False,
        model_gateway_force_simulate=False,
        internal_model_base_url="",
        internal_confidence_threshold=0.9,  # force escalate from stub
    )
    router = IntelligentModelRouter(settings=settings)
    gateway = ModelGateway(settings=settings, router=router)
    mock = AsyncMock(return_value=("cached-body", 2, 2, {"id": "z"}))
    with patch("app.gateway.router.openai_chat", new=mock):
        a = await gateway.complete(ModelRole.fast, "same prompt", metadata={"skip_cache": False})
        b = await gateway.complete(ModelRole.fast, "same prompt", metadata={"skip_cache": False})
    assert a.content == "cached-body"
    assert b.route_tier == "cache"
    assert mock.await_count == 1


@pytest.mark.asyncio
async def test_distillation_requires_verification(tmp_path):
    settings = Settings(distillation_enabled=True, distillation_data_root=tmp_path)
    engine = DistillationEngine(settings=settings)
    rejected = engine.ingest_teacher_output(
        role="coding",
        prompt="write add()",
        system=None,
        teacher_model="openai/gpt-4.1",
        teacher_output="def add(a,b): return a+b",
        metadata={"distill": True},
    )
    assert rejected["accepted"] is False
    assert rejected["queued_pending"] is True

    accepted = engine.ingest_teacher_output(
        role="coding",
        prompt="write add()",
        system=None,
        teacher_model="openai/gpt-4.1",
        teacher_output="def add(a,b): return a+b",
        metadata={"distill": True, "tests_ok": True},
    )
    assert accepted["accepted"] is True
    stats = engine.stats()
    assert stats["examples_by_specialty"]["coding"] == 1


@pytest.mark.asyncio
async def test_gateway_provider_error_surface():
    settings = Settings(
        openai_api_key="sk-bad",
        prefer_internal=True,
        model_cache_enabled=False,
        distillation_enabled=False,
        model_gateway_force_simulate=False,
        internal_model_base_url="",
    )
    gateway = ModelGateway(settings=settings, router=IntelligentModelRouter(settings=settings))
    with patch(
        "app.gateway.router.openai_chat",
        new=AsyncMock(side_effect=ProviderError("openai", "401 unauthorized", status=401)),
    ):
        response = await gateway.complete(
            ModelRole.fast,
            "hi",
            metadata={"force_teacher": True, "skip_cache": True},
        )
    assert response.simulated is False
    assert response.error
    assert "provider-error" in response.content


def test_strip_model_id():
    assert strip_model_id("openai/gpt-4.1") == ("openai", "gpt-4.1")
    assert strip_model_id("anthropic/claude-sonnet-4-5") == ("anthropic", "claude-sonnet-4-5")
    assert strip_model_id("gpt-4.1-mini") == ("openai", "gpt-4.1-mini")


def test_provider_status_includes_ownership():
    settings = Settings(openai_api_key="sk", anthropic_api_key="")
    status = ModelGateway(settings=settings, router=IntelligentModelRouter(settings=settings)).provider_status()
    assert status["providers"]["internal"]["tier"] == "student"
    assert status["ownership_goal"]["target_internal_coverage"] == 0.85
    assert len(status["internal_family"]) == 6
