"""Curated verified seeds for Internal Critic specialty."""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.distillation.engine import DistillationEngine, get_distillation_engine

CRITIC_SEED_PAIRS: tuple[dict[str, str], ...] = (
    {
        "prompt": "Critique: def get_user(id): return db.execute(f'SELECT * FROM users WHERE id={id}'). Risk and fix.",
        "output": (
            "Risk: SQL injection via string formatting.\n"
            "Fix: parameterized query, e.g. db.execute('SELECT * FROM users WHERE id=?', (id,)).\n"
            "Also avoid SELECT *; project needed columns."
        ),
    },
    {
        "prompt": "Critique a plan that deploys Friday night with no rollback. Severity and required changes.",
        "output": (
            "Severity: high operational risk.\n"
            "Require: rollback plan, health checks, staged rollout, avoid low-staff windows, "
            "and human approval before production deploy."
        ),
    },
    {
        "prompt": "A PR adds secrets in .env committed to git. What must the critic block?",
        "output": (
            "Block merge. Rotate exposed secrets, remove from history if needed, add .env to .gitignore, "
            "and use a secret manager. Treat as a security incident, not a style nit."
        ),
    },
    {
        "prompt": "Agent proposes deleting unused tables without a backup. Approve or reject?",
        "output": (
            "Reject until there is a verified backup/snapshot, a dry-run inventory of dependents, "
            "and a reversible migration. Destructive schema changes need stronger evidence than 'unused'."
        ),
    },
    {
        "prompt": "List three checklist items before accepting an architecture proposal.",
        "output": (
            "1) Evidence: cited files/metrics, not vibes.\n"
            "2) Blast radius: isolation, rollback, and who is affected.\n"
            "3) Alternatives considered with tradeoffs; critic sign-off on residual risk."
        ),
    },
)


def seed_critic_curriculum(
    *,
    settings: Settings | None = None,
    engine: DistillationEngine | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    engine = engine or get_distillation_engine()
    accepted = 0
    ids: list[str] = []
    for pair in CRITIC_SEED_PAIRS:
        result = engine.ingest_teacher_output(
            role="critic",
            prompt=pair["prompt"],
            system="You are Internal Critic. Be specific about risk, severity, and required fixes.",
            teacher_model="evolve/curated-critic-curriculum",
            teacher_output=pair["output"],
            metadata={
                "specialty": "critic",
                "distill": True,
                "tools_ok": True,
                "human_verified": True,
            },
        )
        if result.get("accepted"):
            accepted += 1
            ids.append(str(result.get("id")))
    return {"pairs": len(CRITIC_SEED_PAIRS), "accepted": accepted, "ids": ids}
