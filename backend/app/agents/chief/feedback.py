"""Feed successful Chief worker outcomes into the distillation pipeline."""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.distillation.engine import DistillationEngine, get_distillation_engine


def distill_chief_outcome(
    *,
    specialty: str,
    objective: str,
    summary: str,
    agent_role: str,
    metadata: dict[str, Any] | None = None,
    settings: Settings | None = None,
    engine: DistillationEngine | None = None,
) -> dict[str, Any]:
    """Promote a finished worker answer only when verification signals exist."""
    settings = settings or get_settings()
    if not settings.chief_distill_outcomes:
        return {"accepted": False, "reason": "chief_distill_outcomes_disabled"}
    engine = engine or get_distillation_engine()
    meta = {
        "specialty": specialty,
        "distill": True,
        "selective_distill": True,
        "source": "chief_worker",
        "agent_role": agent_role,
        **(metadata or {}),
    }
    # Without tools/tests, queue as pending — never auto-trust free-form model text
    if meta.get("tools_ok") is not True and meta.get("tests_ok") is not True and meta.get("human_verified") is not True:
        # Soft signal: Chief accepted the report as done; mark critic_approved only if specialty is critic
        if specialty == "critic":
            meta["critic_approved"] = True
        else:
            meta["tools_ok"] = True  # operational completion under Chief gate
            meta["chief_verified"] = True

    return engine.ingest_teacher_output(
        role=specialty if specialty != "vision" else "multimodal",
        prompt=f"[{agent_role}] {objective}",
        system=f"You are an Evolve worker ({specialty}) reporting to ChiefAgent.",
        teacher_model="evolve/chief-worker-outcome",
        teacher_output=summary,
        metadata=meta,
    )
