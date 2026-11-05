"""Independent Critic — challenges unsupported findings before acceptance."""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentResult, AgentSpec, BaseAgent
from app.db.models import AgentDepartment
from app.gateway.router import ModelGateway, ModelRole, get_model_gateway


class IndependentCriticAgent(BaseAgent):
    spec = AgentSpec(
        name="IndependentCritic",
        department=AgentDepartment.critic,
        description="Challenges plans and findings; rejects unsupported claims",
        model_role=ModelRole.critic,
        can_self_approve=False,
    )

    def __init__(self, gateway: ModelGateway | None = None) -> None:
        self.gateway = gateway or get_model_gateway()

    async def run(self, context: dict[str, Any]) -> AgentResult:
        specialist_reports = context.get("specialist_reports") or []
        intelligence = context.get("intelligence") or {}
        knowledge = context.get("knowledge") or []

        unverified = [k for k in knowledge if k.get("kind") == "unverified"]
        inferences = [k for k in knowledge if k.get("kind") == "inference"]
        facts = [k for k in knowledge if k.get("kind") == "fact"]
        failed = [r for r in specialist_reports if not r.get("success", True)]

        issues: list[dict[str, Any]] = []
        if len(unverified) > max(3, len(facts)):
            issues.append(
                {
                    "severity": "high",
                    "title": "Too many unverified claims relative to facts",
                    "detail": f"unverified={len(unverified)} facts={len(facts)}",
                }
            )
        for item in inferences:
            if float(item.get("confidence") or 0) >= 0.85 and not item.get("evidence"):
                issues.append(
                    {
                        "severity": "medium",
                        "title": f"High-confidence inference lacks evidence: {item.get('title')}",
                        "detail": "Inferences above 0.85 must cite evidence",
                    }
                )
        if failed:
            issues.append(
                {
                    "severity": "high",
                    "title": "One or more specialists failed",
                    "detail": ", ".join(r.get("agent_name", "?") for r in failed),
                }
            )

        purpose = (intelligence.get("business") or {}).get("purpose")
        if not purpose and any(
            r.get("agent_name") == "BusinessLogicAnalyst" and r.get("success")
            for r in specialist_reports
        ):
            issues.append(
                {
                    "severity": "medium",
                    "title": "Business analyst succeeded without documented purpose",
                    "detail": "Treat business conclusions as unverified until docs exist",
                }
            )

        prompt = (
            "Critique the following multi-agent understanding package. "
            "Reject unsupported certainty. List concrete issues.\n"
            f"Facts={len(facts)} Inferences={len(inferences)} Unverified={len(unverified)}\n"
            f"Specialists={specialist_reports}\n"
            f"Heuristic issues={issues}"
        )
        response = await self.gateway.complete(
            ModelRole.critic,
            prompt,
            system=(
                "You are IndependentCritic on Evolve. "
                "You may not approve developer work. Challenge weak evidence."
            ),
            metadata={"agent": self.spec.name},
        )

        approved = len([i for i in issues if i["severity"] == "high"]) == 0
        knowledge_out = [
            {
                "memory_layer": "decision",
                "category": "critique",
                "kind": "inference" if approved else "unverified",
                "title": "Independent critic review",
                "content": response.content,
                "confidence": 0.55 if response.simulated else 0.75,
                "source_type": "agent",
                "source_path": None,
                "evidence": {
                    "approved": approved,
                    "issues": issues,
                    "model": response.model_id,
                    "simulated": response.simulated,
                },
            }
        ]
        for issue in issues:
            knowledge_out.append(
                {
                    "memory_layer": "decision",
                    "category": "critique_issue",
                    "kind": "unverified" if issue["severity"] == "high" else "inference",
                    "title": issue["title"],
                    "content": issue["detail"],
                    "confidence": 0.7 if issue["severity"] == "high" else 0.55,
                    "source_type": "agent",
                    "source_path": None,
                    "evidence": issue,
                }
            )

        return AgentResult(
            success=True,
            summary=response.content,
            evidence={
                "approved": approved,
                "issues": issues,
                "model": response.model_id,
                "counts": {
                    "facts": len(facts),
                    "inferences": len(inferences),
                    "unverified": len(unverified),
                },
            },
            knowledge=knowledge_out,
            needs_human=not approved,
        )
