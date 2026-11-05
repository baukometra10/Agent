"""Curated verified seeds for Internal Reasoning specialty."""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.distillation.engine import DistillationEngine, get_distillation_engine

REASONING_SEED_PAIRS: tuple[dict[str, str], ...] = (
    {
        "prompt": "A feature needs DB migration, API change, and UI. Order the work to minimize risk. Be terse.",
        "output": (
            "1) Design the schema change and backward-compatible API contract.\n"
            "2) Ship migration + API behind a flag or additive fields.\n"
            "3) Update UI once the API is live.\n"
            "4) Remove flag / old path after verification.\n"
            "Rationale: data and contract risk first; UI last reduces rollback cost."
        ),
    },
    {
        "prompt": "Decide: auto-merge agent code to main, or require human approval? Give the rule Evolve should follow.",
        "output": (
            "Require human approval before merge/deploy. Agents may understand, plan, and draft "
            "automatically, but execution that changes production history stays human-gated. "
            "This bounds blast radius while preserving autonomy on analysis."
        ),
    },
    {
        "prompt": "Two projects share one vector memory. Name the main failure mode and the fix.",
        "output": (
            "Failure: cross-project knowledge contamination / secret leakage via shared retrieval.\n"
            "Fix: hard isolation — per-project workspace, namespace, and memory graph; never share embeddings stores."
        ),
    },
    {
        "prompt": "When should Evolve escalate from an internal student model to an external teacher?",
        "output": (
            "Escalate only when Local First fails evidence gates: tool/test failure, empty/error output, "
            "or confidence below threshold. Do not escalate for convenience or because a teacher exists."
        ),
    },
    {
        "prompt": "Pick one metric for model ownership success and one anti-metric.",
        "output": (
            "Metric: share of successful tasks served by internal/cache (target ~85%).\n"
            "Anti-metric: raw request count to teachers — it ignores failure and double-counts retries."
        ),
    },
)


def seed_reasoning_curriculum(
    *,
    settings: Settings | None = None,
    engine: DistillationEngine | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    engine = engine or get_distillation_engine()
    accepted = 0
    ids: list[str] = []
    for pair in REASONING_SEED_PAIRS:
        result = engine.ingest_teacher_output(
            role="reasoning",
            prompt=pair["prompt"],
            system="You are Internal Reasoning. Prefer clear decisions and tradeoffs.",
            teacher_model="evolve/curated-reasoning-curriculum",
            teacher_output=pair["output"],
            metadata={
                "specialty": "reasoning",
                "distill": True,
                "tools_ok": True,
                "human_verified": True,
            },
        )
        if result.get("accepted"):
            accepted += 1
            ids.append(str(result.get("id")))
    return {"pairs": len(REASONING_SEED_PAIRS), "accepted": accepted, "ids": ids}
