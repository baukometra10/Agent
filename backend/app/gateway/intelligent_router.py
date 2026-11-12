"""Intelligent Model Router — Local First, confidence escalate, cache, distill hooks."""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Awaitable

from app.config import Settings, get_settings
from app.gateway.cache import ResponseCache
from app.gateway.internal import ROLE_TO_INTERNAL
from app.gateway.types import ModelResponse, ModelRole


class RouteTier(str, enum.Enum):
    cache = "cache"
    internal = "internal"
    teacher = "teacher"
    simulate = "simulate"


@dataclass
class RouteDecision:
    tier: RouteTier
    model_id: str
    reason: str
    escalate: bool = False
    confidence: float = 0.0
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class RouterMetrics:
    internal_ok: int = 0
    teacher_ok: int = 0
    cache_hits: int = 0
    escalations: int = 0
    failures: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    estimated_cost_usd: float = 0.0
    updated_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        total = self.internal_ok + self.teacher_ok + self.cache_hits
        internal_share = (self.internal_ok + self.cache_hits) / total if total else 0.0
        cost = float(self.estimated_cost_usd or 0.0)
        return {
            "internal_ok": self.internal_ok,
            "teacher_ok": self.teacher_ok,
            "cache_hits": self.cache_hits,
            "escalations": self.escalations,
            "failures": self.failures,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "estimated_cost_usd": round(cost, 6),
            "cost_per_successful_task_usd": round(cost / total, 6) if total else 0.0,
            "successful_tasks": total,
            "internal_coverage_ratio": round(internal_share, 4),
            "target_internal_coverage": 0.85,
            "updated_at": self.updated_at,
            "note": "Coverage = successful tasks served internal/cache ÷ all successful tasks (not raw requests).",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "RouterMetrics":
        data = data or {}
        return cls(
            internal_ok=int(data.get("internal_ok") or 0),
            teacher_ok=int(data.get("teacher_ok") or 0),
            cache_hits=int(data.get("cache_hits") or 0),
            escalations=int(data.get("escalations") or 0),
            failures=int(data.get("failures") or 0),
            tokens_in=int(data.get("tokens_in") or 0),
            tokens_out=int(data.get("tokens_out") or 0),
            estimated_cost_usd=float(data.get("estimated_cost_usd") or 0.0),
            updated_at=data.get("updated_at"),
        )


ConfidenceFn = Callable[[ModelResponse, dict[str, Any]], float]


def _specialty_promoted(model_id: str) -> bool:
    """True when the LoRA adapter for this internal specialty passed promote gates."""
    try:
        from app.gateway.internal import ROLE_TO_INTERNAL, family_catalog
        from app.config import get_settings

        settings = get_settings()
        catalog = {row["id"]: row for row in family_catalog(settings)}
        mid = str(model_id)
        if mid in catalog:
            return bool(catalog[mid].get("adapter_promoted") or catalog[mid].get("ready"))
        # Role-style ids
        for rid, iid in ROLE_TO_INTERNAL.items():
            if mid.endswith(rid) or mid == iid:
                row = catalog.get(iid) or {}
                return bool(row.get("adapter_promoted") or row.get("ready"))
    except Exception:  # noqa: BLE001
        return False
    return False


def _specialty_handoff_ready(model_id: str) -> bool:
    """True when OwnershipHandoff marks the specialty ready to retire teachers."""
    try:
        from app.ownership import get_ownership_handoff

        mid = str(model_id)
        for row in get_ownership_handoff().readiness_map().get("specialties") or []:
            if not row.get("handoff_ready"):
                continue
            if mid == row.get("internal_id") or mid.endswith(str(row.get("specialty") or "")):
                return True
    except Exception:  # noqa: BLE001
        return False
    return False


def _specialty_teachers_retired(model_id: str) -> bool:
    """True when external teachers were retired for this owned specialty."""
    try:
        from app.ownership import get_ownership_handoff

        return get_ownership_handoff().is_specialty_retired(str(model_id))
    except Exception:  # noqa: BLE001
        return False


def default_confidence(response: ModelResponse, meta: dict[str, Any]) -> float:
    """Evidence-oriented confidence — never trust model self-score alone."""
    if response.error:
        return 0.05
    if meta.get("force_teacher"):
        return 0.0
    text = response.content or ""
    if response.simulated and ("[internal-student:" in text or "stub" in (response.raw or {})):
        # Internal stub without hosted weights — low until real student is online
        return float(meta.get("stub_confidence", 0.35))
    if response.simulated:
        return 0.2
    tools_ok = meta.get("tools_ok")
    tests_ok = meta.get("tests_ok")
    # Hosted internal/teacher answer with substance: stay local-first by default
    score = 0.62 if str(response.model_id).startswith("internal/") else 0.55
    if meta.get("prefer_promoted") and _specialty_promoted(response.model_id):
        score += 0.18  # owned specialist ready — trust more, leave teachers behind
    if tools_ok is True:
        score += 0.2
    if tests_ok is True:
        score += 0.2
    if tools_ok is False or tests_ok is False:
        score = min(score, 0.3)
    # Only punish empty/near-empty answers (short valid replies like "ok" must pass Local First)
    if len(text.strip()) == 0:
        score = 0.1
    if text.startswith("[provider-error"):
        score = 0.05
    return max(0.0, min(1.0, score))


class IntelligentModelRouter:
    """Chooses internal vs teacher; records metrics for ownership goals."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        cache: ResponseCache | None = None,
        confidence_fn: ConfidenceFn | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.cache = cache or ResponseCache(
            ttl_seconds=self.settings.model_cache_ttl_seconds,
        )
        self.confidence_fn = confidence_fn or default_confidence
        self.metrics = RouterMetrics()
        self._pending_batch: list[dict[str, Any]] = []
        self._load_metrics()

    def _metrics_path(self) -> Path:
        root = Path(self.settings.learning_data_root) / "ownership"
        root.mkdir(parents=True, exist_ok=True)
        return root / "router_metrics.json"

    def _load_metrics(self) -> None:
        path = self._metrics_path()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.metrics = RouterMetrics.from_dict(data)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return

    def _persist_metrics(self) -> None:
        self.metrics.updated_at = datetime.now(timezone.utc).isoformat()
        path = self._metrics_path()
        try:
            path.write_text(
                json.dumps(self.metrics.as_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            return

    def reset_metrics(self, *, persist: bool = True) -> dict[str, Any]:
        self.metrics = RouterMetrics()
        if persist:
            self._persist_metrics()
        return self.metrics.as_dict()

    def _teacher_upstream_available(self) -> bool:
        """True when at least one external teacher key is configured."""
        s = self.settings
        if bool(s.model_gateway_force_simulate):
            return False
        return bool(
            (s.openrouter_api_key or "").strip()
            or (s.cursor_api_key or "").strip()
            or (s.openai_api_key or "").strip()
            or (s.anthropic_api_key or "").strip()
        )

    def decide(self, role: ModelRole, *, metadata: dict[str, Any] | None = None) -> RouteDecision:
        meta = metadata or {}
        if meta.get("force_teacher"):
            return RouteDecision(
                RouteTier.teacher,
                self._teacher_id(role),
                "force_teacher",
                escalate=True,
                confidence=0.0,
            )
        if meta.get("force_internal"):
            internal_id = ROLE_TO_INTERNAL.get(role.value, "internal/coding")
            return RouteDecision(
                RouteTier.internal,
                internal_id,
                "force_internal",
                confidence=0.5,
            )

        internal_id = ROLE_TO_INTERNAL.get(role.value, "internal/coding")
        # Bootstrap: owned student not ready yet → external teacher leads the turn
        if (
            bool(getattr(self.settings, "teacher_bootstrap_first", True))
            and not meta.get("forbid_teacher")
            and self._teacher_upstream_available()
            and not _specialty_teachers_retired(internal_id)
            and not _specialty_handoff_ready(internal_id)
            and not _specialty_promoted(internal_id)
        ):
            return RouteDecision(
                RouteTier.teacher,
                self._teacher_id(role),
                "bootstrap_teacher_first",
                escalate=True,
                confidence=0.0,
                evidence={"specialty": internal_id, "policy": "bootstrap_allowed"},
            )

        if self.settings.prefer_internal:
            return RouteDecision(
                RouteTier.internal,
                internal_id,
                "local_first",
                confidence=0.5,
            )
        # Default doctrine: local first
        return RouteDecision(
            RouteTier.internal,
            internal_id,
            "local_first_default",
            confidence=0.5,
        )

    def _teacher_id(self, role: ModelRole) -> str:
        mapping = {
            ModelRole.reasoning: self.settings.default_reasoning_model,
            ModelRole.coding: self.settings.default_coding_model,
            ModelRole.fast: self.settings.default_fast_model,
            ModelRole.multimodal: self.settings.default_multimodal_model,
            ModelRole.embedding: self.settings.default_embedding_model,
            ModelRole.critic: self.settings.default_critic_model,
        }
        return mapping[role]

    def should_escalate(
        self,
        response: ModelResponse,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[bool, float]:
        meta = metadata or {}
        conf = self.confidence_fn(response, meta)
        threshold = float(self.settings.internal_confidence_threshold)
        if meta.get("force_teacher"):
            return True, conf
        # Phase 29: retired specialty → teachers off (except explicit force_teacher)
        if _specialty_teachers_retired(response.model_id) and not meta.get("force_teacher"):
            return False, conf
        if response.error:
            return True, conf
        # Ownership handoff: promoted specialists stay internal unless forced/broken
        if (
            self.settings.prefer_promoted_internal
            and self.settings.promoted_no_escalate
            and not response.error
            and not response.simulated
            and _specialty_promoted(response.model_id)
            and conf >= threshold
        ):
            return False, conf
        # Hard prefer: specialty marked handoff_ready → do not escalate teachers
        if (
            self.settings.prefer_promoted_internal
            and meta.get("prefer_promoted")
            and not response.error
            and not meta.get("force_teacher")
            and _specialty_handoff_ready(response.model_id)
            and conf >= max(0.4, threshold - 0.1)
        ):
            return False, conf
        if conf < threshold:
            return True, conf
        return False, conf

    def record_cache_hit(self) -> None:
        self.metrics.cache_hits += 1
        self._persist_metrics()

    def record_internal(self, *, tokens_in: int = 0, tokens_out: int = 0, quality: float | None = None) -> None:
        self.metrics.internal_ok += 1
        self._add_tokens(tokens_in, tokens_out, tier="internal")
        self._persist_metrics()
        try:
            from app.economics.cost_efficiency import get_cost_efficiency_ledger

            get_cost_efficiency_ledger().record_event(
                tier="internal",
                success=True,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                quality=quality,
            )
        except Exception:
            pass

    def record_teacher(
        self,
        *,
        escalated: bool,
        tokens_in: int = 0,
        tokens_out: int = 0,
        quality: float | None = None,
    ) -> None:
        self.metrics.teacher_ok += 1
        if escalated:
            self.metrics.escalations += 1
        self._add_tokens(tokens_in, tokens_out, tier="teacher")
        self._persist_metrics()
        try:
            from app.economics.cost_efficiency import get_cost_efficiency_ledger

            get_cost_efficiency_ledger().record_event(
                tier="teacher",
                success=True,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                quality=quality,
                escalated=escalated,
            )
        except Exception:
            pass

    def record_failure(self) -> None:
        self.metrics.failures += 1
        self._persist_metrics()

    def _add_tokens(self, tokens_in: int, tokens_out: int, *, tier: str) -> None:
        tin = max(0, int(tokens_in or 0))
        tout = max(0, int(tokens_out or 0))
        self.metrics.tokens_in += tin
        self.metrics.tokens_out += tout
        # Rough USD estimates — teachers priced higher; owned internals near-zero host cost.
        if tier == "teacher":
            self.metrics.estimated_cost_usd += tin * 3e-6 + tout * 9e-6
        else:
            self.metrics.estimated_cost_usd += tin * 2e-7 + tout * 2e-7

    def enqueue_batch(self, item: dict[str, Any]) -> None:
        self._pending_batch.append(item)

    def drain_batch(self, max_items: int = 32) -> list[dict[str, Any]]:
        chunk = self._pending_batch[:max_items]
        self._pending_batch = self._pending_batch[max_items:]
        return chunk

    def status(self) -> dict[str, Any]:
        return {
            "prefer_internal": self.settings.prefer_internal,
            "prefer_promoted_internal": self.settings.prefer_promoted_internal,
            "promoted_no_escalate": self.settings.promoted_no_escalate,
            "confidence_threshold": self.settings.internal_confidence_threshold,
            "cache": self.cache.stats(),
            "metrics": self.metrics.as_dict(),
            "batch_pending": len(self._pending_batch),
            "mechanisms": [
                "local_first",
                "prefer_promoted",
                "teacher_retirement",
                "confidence_routing",
                "caching",
                "batching",
                "selective_distillation",
            ],
        }


_router: IntelligentModelRouter | None = None


def get_intelligent_router() -> IntelligentModelRouter:
    global _router
    if _router is None:
        _router = IntelligentModelRouter()
    return _router


def reset_intelligent_router() -> None:
    global _router
    _router = None
