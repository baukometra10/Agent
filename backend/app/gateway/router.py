"""Model Gateway — external teachers + internal students via Intelligent Router."""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.distillation.engine import get_distillation_engine
from app.gateway.cache import ResponseCache
from app.gateway.intelligent_router import (
    IntelligentModelRouter,
    RouteTier,
    get_intelligent_router,
)
from app.gateway.internal import family_catalog, internal_chat
from app.gateway.catalog import chief_catalog
from app.gateway.providers import (
    ProviderError,
    anthropic_chat,
    cursor_cloud_agent_chat,
    openai_chat,
    openai_embed,
    openrouter_chat,
    strip_model_id,
)
from app.gateway.types import ModelInvocation, ModelResponse, ModelRole

__all__ = [
    "ModelGateway",
    "ModelInvocation",
    "ModelResponse",
    "ModelRole",
    "get_model_gateway",
    "reset_model_gateway",
]


class ModelGateway:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        router: IntelligentModelRouter | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.router = router or get_intelligent_router()
        self._routes: dict[ModelRole, str] = {
            ModelRole.reasoning: self.settings.default_reasoning_model,
            ModelRole.coding: self.settings.default_coding_model,
            ModelRole.fast: self.settings.default_fast_model,
            ModelRole.multimodal: self.settings.default_multimodal_model,
            ModelRole.embedding: self.settings.default_embedding_model,
            ModelRole.critic: self.settings.default_critic_model,
        }

    def resolve(self, role: ModelRole) -> tuple[str, str]:
        model_id = self._routes[role]
        provider, _ = strip_model_id(model_id)
        return provider, model_id

    def set_route(self, role: ModelRole, model_id: str) -> None:
        self._routes[role] = model_id

    def routes(self) -> dict[str, str]:
        return {role.value: model_id for role, model_id in self._routes.items()}

    def provider_key(self, provider: str) -> str:
        if provider == "openrouter":
            return (self.settings.openrouter_api_key or "").strip()
        if provider == "openai":
            return (self.settings.openai_api_key or "").strip()
        if provider == "anthropic":
            return (self.settings.anthropic_api_key or "").strip()
        if provider == "cursor":
            return (self.settings.cursor_api_key or "").strip()
        if provider == "internal":
            return "local"
        return ""

    def _openrouter_ready(self) -> bool:
        return bool((self.settings.openrouter_api_key or "").strip())

    def _cursor_ready(self) -> bool:
        return bool((self.settings.cursor_api_key or "").strip())

    def _use_openrouter_upstream(self) -> bool:
        upstream = (self.settings.teacher_upstream or "openrouter").strip().lower()
        return upstream == "openrouter" and self._openrouter_ready()

    def _use_cursor_upstream(self) -> bool:
        upstream = (self.settings.teacher_upstream or "openrouter").strip().lower()
        return upstream == "cursor" and self._cursor_ready()

    def provider_status(self) -> dict[str, Any]:
        openai_ok = bool((self.settings.openai_api_key or "").strip())
        anthropic_ok = bool((self.settings.anthropic_api_key or "").strip())
        openrouter_ok = self._openrouter_ready()
        cursor_ok = self._cursor_ready()
        internal_hosted = bool((self.settings.internal_model_base_url or "").strip())
        return {
            "force_simulate": bool(self.settings.model_gateway_force_simulate),
            "prefer_internal": bool(self.settings.prefer_internal),
            "teacher_upstream": (self.settings.teacher_upstream or "openrouter"),
            "teacher_upstream_live": self._use_openrouter_upstream()
            or self._use_cursor_upstream()
            or openai_ok
            or anthropic_ok,
            "chiefs": chief_catalog(openrouter_configured=openrouter_ok),
            "providers": {
                "cursor": {
                    "configured": cursor_ok,
                    "live": cursor_ok and not self.settings.model_gateway_force_simulate,
                    "tier": "teacher_cloud_agent",
                    "note": "Cursor Cloud Agents API — coding teacher (poll run.result)",
                },
                "openrouter": {
                    "configured": openrouter_ok,
                    "live": openrouter_ok and not self.settings.model_gateway_force_simulate,
                    "tier": "teacher_upstream",
                    "note": "Single source for GPT/Claude/Gemini/Grok teachers",
                },
                "openai": {
                    "configured": openai_ok,
                    "live": openai_ok and not self.settings.model_gateway_force_simulate,
                    "tier": "teacher_direct",
                },
                "anthropic": {
                    "configured": anthropic_ok,
                    "live": anthropic_ok and not self.settings.model_gateway_force_simulate,
                    "tier": "teacher_direct",
                },
                "internal": {
                    "configured": True,
                    "live": internal_hosted and not self.settings.model_gateway_force_simulate,
                    "tier": "student",
                    "host": (self.settings.internal_model_base_url or "") or "stub",
                },
            },
            "routes": self.routes(),
            "internal_family": family_catalog(self.settings),
            "router": self.router.status(),
            "ownership_goal": {
                "target_internal_coverage": 0.85,
                "doctrine": (
                    "Spixa Proprietary Intelligence Ecosystem — "
                    "Internal Intelligence First; External Teacher → Owned Specialty Family"
                ),
                "doctrine_ar": (
                    "منظومة ذكاء Spixa المملوكة — الذكاء الداخلي أولًا؛ "
                    "المعلّم الخارجي يخدم عائلة التخصصات المملوكة"
                ),
                "quality_rule": (
                    "Escalate when internal quality is below gate; never trade intelligence for cheapness. "
                    "Huge-from-scratch foundation training is not a success gate."
                ),
                "ecosystem": "/system/intelligence/ecosystem",
            },
        }

    async def complete(
        self,
        role: ModelRole,
        prompt: str,
        *,
        system: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ModelResponse:
        meta = dict(metadata or {})
        try:
            from app.gateway.request_context import (
                get_forbid_teacher,
                get_force_internal,
                get_preferred_model,
                get_preferred_provider,
            )

            pref = (meta.get("preferred_provider") or get_preferred_provider() or "").strip().lower()
            pref_model = (meta.get("preferred_model") or get_preferred_model() or "").strip()
            if get_forbid_teacher() or meta.get("forbid_teacher"):
                meta["forbid_teacher"] = True
                meta.pop("force_teacher", None)
            if get_force_internal() or meta.get("force_internal"):
                meta["force_internal"] = True
                meta.pop("force_teacher", None)
                pref_model = ""
        except Exception:  # noqa: BLE001
            pref = ""
            pref_model = ""
        if meta.get("forbid_teacher"):
            # Budget / tab policy: stay on owned path
            meta["force_internal"] = True
            meta.pop("force_teacher", None)
            pref_model = ""
        if pref_model:
            meta["preferred_model"] = pref_model
            meta["force_teacher"] = True
            meta["force_provider"] = "openrouter" if self._use_openrouter_upstream() else pref_model.split("/", 1)[0]
        elif pref in {"openrouter", "upstream"}:
            meta["force_teacher"] = True
            meta["force_provider"] = "openrouter"
            pref = "openrouter"
        elif pref in {"cursor", "cursor-agent", "cloud-agent"}:
            meta["force_teacher"] = True
            meta["force_provider"] = "cursor"
            pref = "cursor"
        elif pref in {"openai", "gpt", "chatgpt"}:
            meta["force_teacher"] = True
            meta["force_provider"] = "openrouter" if self._use_openrouter_upstream() else "openai"
            if self._use_openrouter_upstream() and not meta.get("preferred_model"):
                meta["preferred_model"] = self.settings.default_coding_model
            pref = "openai"
        elif pref in {"anthropic", "claude"}:
            meta["force_teacher"] = True
            meta["force_provider"] = "openrouter" if self._use_openrouter_upstream() else "anthropic"
            if self._use_openrouter_upstream() and not meta.get("preferred_model"):
                meta["preferred_model"] = self.settings.default_critic_model
            pref = "anthropic"
        elif pref in {"internal", "spixa", "local"}:
            meta["force_internal"] = True
            pref = "internal"

        decision = self.router.decide(role, metadata=meta)

        # Cache lookup (role + chosen model + prompt)
        cache_key = ResponseCache.make_key(role.value, decision.model_id, prompt, system)
        if self.settings.model_cache_enabled and not meta.get("skip_cache"):
            hit = self.router.cache.get(cache_key)
            if hit:
                self.router.record_cache_hit()
                return ModelResponse(
                    role=role,
                    model_id=hit.model_id,
                    content=hit.content,
                    tokens_in=hit.tokens_in,
                    tokens_out=hit.tokens_out,
                    simulated=False,
                    route_tier=RouteTier.cache.value,
                    confidence=0.9,
                    raw={"cache": True, "hits": hit.hits, "metadata": meta},
                )

        if (
            self.settings.model_gateway_force_simulate
            and not meta.get("force_teacher")
            and not meta.get("force_internal")
        ):
            response = self._simulate(role, decision.model_id, prompt, system, meta, reason="force_simulate")
            response.route_tier = RouteTier.simulate.value
            return response

        # Explicit chief brain: Spixa internal
        if meta.get("force_internal"):
            internal_id = decision.model_id if str(decision.model_id).startswith("internal/") else f"internal/{role.value}"
            internal_resp = await self._complete_internal(role, internal_id, prompt, system, meta)
            if not internal_resp.error:
                self.router.record_internal(
                    tokens_in=internal_resp.tokens_in, tokens_out=internal_resp.tokens_out
                )
                self._maybe_cache(cache_key, internal_resp)
            return internal_resp

        # Local first — internal student
        if decision.tier == RouteTier.internal and not meta.get("force_teacher"):
            internal_resp = await self._complete_internal(role, decision.model_id, prompt, system, meta)
            escalate, conf = self.router.should_escalate(internal_resp, metadata=meta)
            internal_resp.confidence = conf
            # Coverage climb / owned path: always count internal attempts that aren't hard errors
            if meta.get("force_internal") and not internal_resp.error:
                self.router.record_internal(
                    tokens_in=internal_resp.tokens_in, tokens_out=internal_resp.tokens_out
                )
                self._maybe_cache(cache_key, internal_resp)
                return internal_resp
            if not escalate:
                self.router.record_internal(
                    tokens_in=internal_resp.tokens_in, tokens_out=internal_resp.tokens_out
                )
                self._maybe_cache(cache_key, internal_resp)
                return internal_resp
            # Retired specialty: never call teachers even if confidence would escalate
            from app.gateway.intelligent_router import _specialty_teachers_retired

            if _specialty_teachers_retired(decision.model_id):
                internal_resp.raw = {
                    **(internal_resp.raw or {}),
                    "teacher_blocked": "retired",
                    "would_escalate_confidence": conf,
                }
                self.router.record_internal(
                    tokens_in=internal_resp.tokens_in, tokens_out=internal_resp.tokens_out
                )
                self._maybe_cache(cache_key, internal_resp)
                return internal_resp
            meta = {**meta, "escalated_from": decision.model_id, "internal_confidence": conf}

        # Teacher (external) — hard / escalated / forced — prefer OpenRouter upstream
        teacher_id = str(meta.get("preferred_model") or self._routes[role])
        force_provider = str(meta.get("force_provider") or "").lower()
        if force_provider == "openai" and "/" not in teacher_id:
            teacher_id = (
                self.settings.default_coding_model
                if role == ModelRole.coding
                else self.settings.default_reasoning_model
            )
            if not str(teacher_id).startswith("openai/"):
                teacher_id = "openai/gpt-4.1"
        elif force_provider == "anthropic" and "/" not in teacher_id:
            teacher_id = self.settings.default_critic_model
            if not str(teacher_id).startswith("anthropic/"):
                teacher_id = "anthropic/claude-sonnet-4.5"
        elif force_provider == "openrouter" and not meta.get("preferred_model"):
            teacher_id = (
                self.settings.default_coding_model
                if role in {ModelRole.coding, ModelRole.fast}
                else self.settings.default_reasoning_model
            )
        teacher_resp = await self._complete_teacher(role, teacher_id, prompt, system, meta)
        teacher_resp.route_tier = RouteTier.teacher.value
        _, conf = self.router.should_escalate(teacher_resp, metadata={**meta, "tests_ok": meta.get("tests_ok")})
        teacher_resp.confidence = conf
        if teacher_resp.error:
            self.router.record_failure()
        else:
            self.router.record_teacher(
                escalated=bool(meta.get("escalated_from") or meta.get("force_teacher")),
                tokens_in=teacher_resp.tokens_in,
                tokens_out=teacher_resp.tokens_out,
            )
            self._maybe_cache(cache_key, teacher_resp)
            self._maybe_distill(role, prompt, system, teacher_resp, meta)
        return teacher_resp

    def _maybe_cache(self, key: str, response: ModelResponse) -> None:
        if not self.settings.model_cache_enabled:
            return
        if response.error or response.simulated:
            return
        self.router.cache.put(
            key,
            content=response.content,
            model_id=response.model_id,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
        )

    def _maybe_distill(
        self,
        role: ModelRole,
        prompt: str,
        system: str | None,
        response: ModelResponse,
        meta: dict[str, Any],
    ) -> None:
        if not self.settings.distillation_enabled:
            return
        if response.error or response.simulated:
            return
        # Selective: distill when escalated or explicitly marked costly/recurring
        if not (meta.get("escalated_from") or meta.get("distill") or meta.get("selective_distill")):
            return
        result = get_distillation_engine().ingest_teacher_output(
            role=role.value,
            prompt=prompt,
            system=system,
            teacher_model=response.model_id,
            teacher_output=response.content,
            metadata=meta,
        )
        response.raw = {**(response.raw or {}), "distillation": result}

    async def _complete_internal(
        self,
        role: ModelRole,
        model_id: str,
        prompt: str,
        system: str | None,
        meta: dict[str, Any],
    ) -> ModelResponse:
        try:
            content, tin, tout, raw, stubbed = await internal_chat(
                settings=self.settings,
                model_id=model_id,
                prompt=prompt,
                system=system,
            )
            return ModelResponse(
                role=role,
                model_id=model_id,
                content=content,
                tokens_in=tin,
                tokens_out=tout,
                simulated=stubbed,
                route_tier=RouteTier.internal.value,
                raw={"provider": "internal", "metadata": meta, "upstream": _safe_upstream(raw)},
            )
        except Exception as exc:  # noqa: BLE001
            return ModelResponse(
                role=role,
                model_id=model_id,
                content=f"[provider-error:internal] {exc}",
                simulated=False,
                error=str(exc),
                route_tier=RouteTier.internal.value,
                raw={"provider": "internal", "metadata": meta},
            )

    async def _complete_teacher(
        self,
        role: ModelRole,
        model_id: str,
        prompt: str,
        system: str | None,
        meta: dict[str, Any],
    ) -> ModelResponse:
        provider, bare_model = strip_model_id(model_id)
        # OpenRouter expects the full author/model slug
        or_model = model_id if "/" in model_id else f"{provider}/{bare_model}"

        if self.settings.model_gateway_force_simulate:
            return self._simulate(role, model_id, prompt, system, meta, reason="force_simulate")

        force_provider = str(meta.get("force_provider") or "").lower()
        use_cursor = (
            force_provider == "cursor"
            or self._use_cursor_upstream()
        ) and role in {ModelRole.coding, ModelRole.reasoning, ModelRole.fast}
        cursor_key = (self.settings.cursor_api_key or "").strip()
        if use_cursor and cursor_key:
            try:
                content, tin, tout, raw = await cursor_cloud_agent_chat(
                    api_key=cursor_key,
                    prompt=prompt,
                    system=system,
                    base_url=self.settings.cursor_api_base_url,
                    repo_url=(self.settings.cursor_default_repo_url or "").strip() or None,
                    poll_timeout_seconds=float(self.settings.cursor_poll_timeout_seconds),
                    poll_interval_seconds=float(self.settings.cursor_poll_interval_seconds),
                )
                return ModelResponse(
                    role=role,
                    model_id="cursor/cloud-agent",
                    content=content,
                    tokens_in=tin,
                    tokens_out=tout,
                    simulated=False,
                    route_tier=RouteTier.teacher.value,
                    raw={
                        "provider": "cursor",
                        "upstream": "cursor",
                        "metadata": meta,
                        "response": _safe_upstream(raw),
                    },
                )
            except ProviderError as exc:
                # Fall through to OpenRouter if configured
                if not self._openrouter_ready():
                    return ModelResponse(
                        role=role,
                        model_id="cursor/cloud-agent",
                        content=f"[provider-error:cursor] {exc}",
                        simulated=False,
                        error=str(exc),
                        route_tier=RouteTier.teacher.value,
                        raw={"provider": "cursor", "status": exc.status, "metadata": meta},
                    )
            except Exception as exc:  # noqa: BLE001
                if not self._openrouter_ready():
                    return ModelResponse(
                        role=role,
                        model_id="cursor/cloud-agent",
                        content=f"[provider-error:cursor] {exc}",
                        simulated=False,
                        error=str(exc),
                        route_tier=RouteTier.teacher.value,
                        raw={"provider": "cursor", "metadata": meta},
                    )

        use_or = self._use_openrouter_upstream() or force_provider == "openrouter"
        or_key = (self.settings.openrouter_api_key or "").strip()

        # Preferred path: single upstream for all external teachers
        if use_or and or_key and role != ModelRole.embedding:
            try:
                content, tin, tout, raw = await openrouter_chat(
                    api_key=or_key,
                    model=or_model,
                    prompt=prompt,
                    system=system,
                    base_url=self.settings.openrouter_base_url,
                    site_url=self.settings.openrouter_site_url,
                    app_name=self.settings.openrouter_app_name,
                )
                return ModelResponse(
                    role=role,
                    model_id=or_model,
                    content=content,
                    tokens_in=tin,
                    tokens_out=tout,
                    simulated=False,
                    route_tier=RouteTier.teacher.value,
                    raw={
                        "provider": "openrouter",
                        "upstream": "openrouter",
                        "metadata": meta,
                        "response": _safe_upstream(raw),
                    },
                )
            except ProviderError as exc:
                return ModelResponse(
                    role=role,
                    model_id=or_model,
                    content=f"[provider-error:openrouter] {exc}",
                    simulated=False,
                    error=str(exc),
                    route_tier=RouteTier.teacher.value,
                    raw={"provider": "openrouter", "status": exc.status, "metadata": meta},
                )
            except Exception as exc:  # noqa: BLE001
                return ModelResponse(
                    role=role,
                    model_id=or_model,
                    content=f"[provider-error:openrouter] {exc}",
                    simulated=False,
                    error=str(exc),
                    route_tier=RouteTier.teacher.value,
                    raw={"provider": "openrouter", "metadata": meta},
                )

        # Fallback: direct vendor keys (legacy / embeddings)
        api_key = ""
        if provider == "openai":
            api_key = (self.settings.openai_api_key or "").strip()
        elif provider == "anthropic":
            api_key = (self.settings.anthropic_api_key or "").strip()

        if not api_key:
            return self._simulate(
                role,
                model_id,
                prompt,
                system,
                meta,
                reason=f"missing_{'openrouter' if use_or else provider}_key",
            )

        try:
            if role == ModelRole.embedding:
                if provider != "openai":
                    raise ProviderError(provider, "Embeddings currently require openai/* models")
                content, tin, tout, raw = await openai_embed(
                    api_key=api_key, model=bare_model, prompt=prompt
                )
            elif provider == "openai":
                content, tin, tout, raw = await openai_chat(
                    api_key=api_key, model=bare_model, prompt=prompt, system=system
                )
            elif provider == "anthropic":
                content, tin, tout, raw = await anthropic_chat(
                    api_key=api_key, model=bare_model, prompt=prompt, system=system
                )
            else:
                return self._simulate(
                    role,
                    model_id,
                    prompt,
                    system,
                    meta,
                    reason=f"unsupported_provider:{provider}",
                )
        except ProviderError as exc:
            return ModelResponse(
                role=role,
                model_id=model_id,
                content=f"[provider-error:{exc.provider}] {exc}",
                simulated=False,
                error=str(exc),
                route_tier=RouteTier.teacher.value,
                raw={"provider": provider, "status": exc.status, "metadata": meta},
            )
        except Exception as exc:  # noqa: BLE001
            return ModelResponse(
                role=role,
                model_id=model_id,
                content=f"[provider-error:{provider}] {exc}",
                simulated=False,
                error=str(exc),
                route_tier=RouteTier.teacher.value,
                raw={"provider": provider, "metadata": meta},
            )

        return ModelResponse(
            role=role,
            model_id=model_id,
            content=content,
            tokens_in=tin,
            tokens_out=tout,
            simulated=False,
            route_tier=RouteTier.teacher.value,
            raw={"provider": provider, "metadata": meta, "upstream": _safe_upstream(raw)},
        )

    def _simulate(
        self,
        role: ModelRole,
        model_id: str,
        prompt: str,
        system: str | None,
        metadata: dict[str, Any],
        *,
        reason: str,
    ) -> ModelResponse:
        return ModelResponse(
            role=role,
            model_id=model_id,
            content=(
                f"[simulated:{role.value}] {reason}. "
                f"Would call {model_id} with prompt length={len(prompt)}."
            ),
            simulated=True,
            raw={"system": system, "metadata": metadata, "reason": reason},
        )


def _safe_upstream(raw: dict[str, Any]) -> dict[str, Any]:
    if "dims" in raw:
        return {"dims": raw.get("dims"), "usage": raw.get("usage")}
    if raw.get("stub"):
        return {"stub": True, "model": raw.get("model")}
    usage = raw.get("usage")
    return {
        "id": raw.get("id"),
        "model": raw.get("model"),
        "usage": usage,
        "type": raw.get("type"),
    }


_gateway: ModelGateway | None = None


def get_model_gateway() -> ModelGateway:
    global _gateway
    if _gateway is None:
        _gateway = ModelGateway()
    return _gateway


def reset_model_gateway() -> None:
    global _gateway
    _gateway = None
