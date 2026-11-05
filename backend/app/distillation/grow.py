"""Grow verified specialty datasets (curriculum packs) in one call."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.distillation.coding import seed_coding_curriculum, seed_coding_from_repo
from app.distillation.critic import seed_critic_curriculum
from app.distillation.engine import DistillationEngine, get_distillation_engine
from app.distillation.project_intel import seed_from_workspace
from app.distillation.reasoning import seed_reasoning_curriculum
from app.distillation.embeddings import seed_embeddings_curriculum
from app.distillation.vision import seed_vision_curriculum
from app.distillation.thought_transfer import seed_thought_transfer
from app.distillation.coding_tutor import seed_coding_tutor


def grow_all_specialties(
    *,
    settings: Settings | None = None,
    engine: DistillationEngine | None = None,
    include_workspaces: bool = True,
) -> dict[str, Any]:
    settings = settings or get_settings()
    engine = engine or get_distillation_engine()
    out: dict[str, Any] = {
        "thought_transfer": seed_thought_transfer(settings=settings, engine=engine),
        "coding_tutor": seed_coding_tutor(settings=settings, engine=engine),
        "reasoning": seed_reasoning_curriculum(settings=settings, engine=engine),
        "critic": seed_critic_curriculum(settings=settings, engine=engine),
        "coding": seed_coding_curriculum(settings=settings, engine=engine),
        "vision": seed_vision_curriculum(settings=settings, engine=engine),
        "embeddings": seed_embeddings_curriculum(settings=settings, engine=engine),
    }

    if include_workspaces:
        root = Path(settings.workspaces_root)
        pi_rows = []
        coding_repo_rows = []
        if root.exists():
            for ws in root.iterdir():
                if not ws.is_dir():
                    continue
                pi_rows.append(seed_from_workspace(ws, settings=settings, engine=engine))
                repo = ws / "repo"
                coding_repo_rows.append(
                    seed_coding_from_repo(repo if repo.exists() else ws, engine=engine)
                )
        out["project_intelligence"] = {
            "workspaces": len(pi_rows),
            "accepted": sum(int(r.get("accepted") or 0) for r in pi_rows),
            "rows": pi_rows,
        }
        out["coding_repos"] = {
            "accepted": sum(int(r.get("accepted") or 0) for r in coding_repo_rows),
            "rows": coding_repo_rows,
        }
    else:
        out["project_intelligence"] = {"workspaces": 0, "accepted": 0, "rows": []}

    out["distillation"] = engine.stats()
    return out
