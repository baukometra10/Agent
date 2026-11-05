"""Evolution Simulator — generate & rank architecture alternatives."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Project
from app.economics.cost_efficiency import CostEfficiencyLedger
from app.gateway.router import ModelRole, get_model_gateway
from app.venture.adversarial import AdversarialLab


STYLES = (
    ("modular_monolith", "Single deployable with clear modules — fast iteration."),
    ("service_oriented", "Split high-churn domains into services — scales teams."),
    ("event_driven", "Async events for processes — good for adaptation loops."),
)


class EvolutionSimulator:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.gateway = get_model_gateway()
        self.lab = AdversarialLab(session)
        self.costs = CostEfficiencyLedger()

    async def generate_alternatives(
        self,
        project: Project,
        *,
        brief: str,
        spec: dict[str, Any] | None = None,
        twin: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        alternatives: list[dict[str, Any]] = []
        for style, blurb in STYLES:
            alt_id = uuid4().hex[:10]
            prompt = (
                f"Design architecture alternative style={style}. {blurb}\n"
                f"Goal: {brief}\n"
                f"Spec summary: {json.dumps(spec or {}, ensure_ascii=False)[:2500]}\n"
                f"Twin layers: {(twin or {}).get('layers')}\n"
                "Return JSON: {summary, components, data_flow, migration_cost: low|medium|high, "
                "ops_complexity: low|medium|high, fit_score: 0-1, risks: [str]}"
            )
            response = await self.gateway.complete(
                ModelRole.reasoning,
                prompt,
                system="You compare architecture tradeoffs honestly.",
                metadata={"agent": "EvolutionSimulator", "project_id": str(project.id)},
            )
            body = self._parse_alt(response.content, style, blurb)
            critique = await self.lab.critique(
                project,
                artifact_title=f"alt:{style}",
                artifact_text=json.dumps(body, ensure_ascii=False),
                twin_context=twin,
            )
            cost_hint = {"low": 1, "medium": 2, "high": 3}.get(body.get("migration_cost", "medium"), 2)
            risk_penalty = critique.get("critical_count", 0) * 0.2 + critique.get("high_count", 0) * 0.08
            fit = float(body.get("fit_score") or 0.55)
            rank_score = round(fit - 0.05 * cost_hint - risk_penalty, 3)
            alternatives.append(
                {
                    "id": alt_id,
                    "style": style,
                    "blurb": blurb,
                    **body,
                    "adversarial": {
                        "resilience_score": critique.get("resilience_score"),
                        "blocking": critique.get("blocking"),
                        "critical_count": critique.get("critical_count"),
                    },
                    "rank_score": rank_score,
                    "model": response.model_id,
                }
            )

        alternatives.sort(key=lambda a: a.get("rank_score", 0), reverse=True)
        recommendation = alternatives[0]["id"] if alternatives else None
        try:
            economics = self.costs.report()
        except Exception:  # noqa: BLE001
            economics = {}
        return {
            "alternatives": alternatives,
            "recommended_id": recommendation,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "economics_context": economics if isinstance(economics, dict) else {},
        }

    def _parse_alt(self, content: str, style: str, blurb: str) -> dict[str, Any]:
        text = (content or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            start = text.find("{")
            end = text.rfind("}")
            data = json.loads(text[start : end + 1] if start >= 0 else text)
            if isinstance(data, dict):
                data.setdefault("summary", blurb)
                return data
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        return {
            "summary": blurb,
            "components": ["api", "domain", "data", "ui"],
            "data_flow": "request → domain → store",
            "migration_cost": "medium",
            "ops_complexity": "medium",
            "fit_score": 0.55,
            "risks": ["needs validation against twin"],
            "notes": text[:800],
            "style": style,
        }
