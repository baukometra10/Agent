"""Research Lab — sandbox experiments; human-gated promote only."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ResearchExperiment
from app.eval.harness import get_eval_harness
from app.gateway.router import ModelRole, get_model_gateway


class ResearchLabService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.gateway = get_model_gateway()

    async def list_experiments(self, limit: int = 40) -> list[dict[str, Any]]:
        rows = list(
            (
                await self.session.execute(
                    select(ResearchExperiment).order_by(ResearchExperiment.created_at.desc()).limit(limit)
                )
            ).scalars().all()
        )
        return [self._out(r) for r in rows]

    async def create(
        self,
        *,
        title: str,
        hypothesis: str,
        kind: str = "routing",
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = ResearchExperiment(
            title=title[:255],
            hypothesis=hypothesis,
            kind=kind,
            status="draft",
            config=config or {},
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return self._out(row)

    async def run(self, experiment_id: UUID) -> dict[str, Any]:
        row = await self.session.get(ResearchExperiment, experiment_id)
        if not row:
            raise ValueError("Experiment not found")
        row.status = "running"
        await self.session.flush()

        prompt_a = str((row.config or {}).get("prompt_a") or row.hypothesis)
        prompt_b = str((row.config or {}).get("prompt_b") or f"Improve: {row.hypothesis}")
        system = "You are Spixa Research Lab sandbox. Do not change production."

        resp_a = await self.gateway.complete(
            ModelRole.reasoning,
            prompt_a,
            system=system,
            metadata={"agent": "ResearchLabA", "experiment_id": str(row.id)},
        )
        resp_b = await self.gateway.complete(
            ModelRole.reasoning,
            prompt_b,
            system=system,
            metadata={"agent": "ResearchLabB", "experiment_id": str(row.id)},
        )

        eval_summary: dict[str, Any] = {}
        try:
            harness = get_eval_harness()
            if hasattr(harness, "quick_compare"):
                eval_summary = await harness.quick_compare(resp_a.content, resp_b.content)  # type: ignore[misc]
            elif hasattr(harness, "status"):
                eval_summary = {"harness": "available"}
        except Exception as exc:  # noqa: BLE001
            eval_summary = {"eval_error": str(exc)[:200]}

        len_a, len_b = len(resp_a.content or ""), len(resp_b.content or "")
        winner = "a" if len_a >= len_b else "b"
        recommendation = (
            f"Candidate '{winner}' looks stronger in sandbox. "
            "Do NOT promote to production without human approval."
        )
        row.results = {
            "a": {"model": resp_a.model_id, "simulated": resp_a.simulated, "preview": (resp_a.content or "")[:800]},
            "b": {"model": resp_b.model_id, "simulated": resp_b.simulated, "preview": (resp_b.content or "")[:800]},
            "winner_heuristic": winner,
            "eval": eval_summary,
        }
        row.recommendation = recommendation
        row.status = "completed"
        row.promote_requested = False
        row.promote_approved = False
        await self.session.commit()
        await self.session.refresh(row)
        return self._out(row)

    async def request_promote(self, experiment_id: UUID) -> dict[str, Any]:
        row = await self.session.get(ResearchExperiment, experiment_id)
        if not row:
            raise ValueError("Experiment not found")
        if row.status != "completed":
            raise ValueError("Run experiment before requesting promote")
        row.promote_requested = True
        await self.session.commit()
        return self._out(row)

    async def decide_promote(self, experiment_id: UUID, *, approve: bool, actor: str = "human") -> dict[str, Any]:
        row = await self.session.get(ResearchExperiment, experiment_id)
        if not row:
            raise ValueError("Experiment not found")
        if not row.promote_requested:
            raise ValueError("Promote not requested")
        # Never auto-apply router changes — record decision only
        row.promote_approved = bool(approve)
        if approve:
            row.promoted_at = datetime.now(timezone.utc)
            meta = dict(row.meta or {})
            meta["promote_actor"] = actor
            meta["note"] = "Approval recorded; production router unchanged until separate deploy step."
            row.meta = meta
        else:
            row.promote_requested = False
        await self.session.commit()
        return self._out(row)

    @staticmethod
    def _out(row: ResearchExperiment) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "title": row.title,
            "hypothesis": row.hypothesis,
            "kind": row.kind,
            "status": row.status,
            "config": row.config,
            "results": row.results,
            "recommendation": row.recommendation,
            "promote_requested": row.promote_requested,
            "promote_approved": row.promote_approved,
            "promoted_at": row.promoted_at.isoformat() if row.promoted_at else None,
            "production_auto_changed": False,
        }
