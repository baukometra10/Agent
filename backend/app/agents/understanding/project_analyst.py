from __future__ import annotations

from typing import Any

from app.agents.base import AgentResult, AgentSpec, BaseAgent
from app.db.models import AgentDepartment
from app.gateway.router import ModelGateway, ModelRole, get_model_gateway
from app.intelligence.scanner import ProjectScanResult


class ProjectAnalystAgent(BaseAgent):
    spec = AgentSpec(
        name="ProjectAnalyst",
        department=AgentDepartment.understanding,
        description="Synthesizes Project Intelligence into a sourced understanding summary",
        model_role=ModelRole.reasoning,
    )

    def __init__(self, gateway: ModelGateway | None = None) -> None:
        self.gateway = gateway or get_model_gateway()

    async def run(self, context: dict[str, Any]) -> AgentResult:
        scan: ProjectScanResult | dict = context.get("scan") or {}
        scan_dict = scan.to_dict() if isinstance(scan, ProjectScanResult) else scan
        intel = context.get("intelligence") or {}
        project_name = context.get("project_name", "unknown")

        business = intel.get("business") or {}
        architecture = intel.get("architecture") or {}
        code = intel.get("code") or {}
        coverage = intel.get("coverage") or {}

        prompt = (
            f"Synthesize an understanding summary for project '{project_name}'.\n"
            f"Purpose (from docs/structure): {business.get('purpose')}\n"
            f"Actors: {business.get('actors')}\n"
            f"Capabilities: {business.get('capabilities')}\n"
            f"Languages: {scan_dict.get('languages')}\n"
            f"Frameworks: {scan_dict.get('frameworks')}\n"
            f"Code stats: {code.get('stats')}\n"
            f"API sample: {(code.get('api_endpoints') or [])[:8]}\n"
            f"Architecture layers: {architecture.get('layers')}\n"
            f"Architecture risks: {architecture.get('risks')}\n"
            f"Coverage: {coverage}\n"
            "Distinguish facts from inferences. Do not invent modules that are not evidenced."
        )
        response = await self.gateway.complete(
            ModelRole.reasoning,
            prompt,
            system=(
                "You are ProjectAnalyst on the Evolve platform. "
                "Never present unverified claims as facts. "
                "Prefer citing detected layers, APIs, and documented purpose."
            ),
            metadata={"agent": self.spec.name},
        )

        # Analyst only adds synthesis + gaps; deterministic facts come from the engine.
        knowledge: list[dict[str, Any]] = [
            {
                "memory_layer": "project",
                "category": "summary",
                "kind": "inference",
                "title": "Project understanding summary",
                "content": response.content,
                "confidence": 0.45 if response.simulated else 0.72,
                "source_type": "agent",
                "source_path": None,
                "evidence": {
                    "model": response.model_id,
                    "simulated": response.simulated,
                    "coverage": coverage,
                    "scan_file_count": (scan_dict.get("file_stats") or {}).get("total_files"),
                },
            }
        ]

        gaps = []
        if not scan_dict.get("languages"):
            gaps.append("language detection")
        if not (code.get("stats") or {}).get("symbols"):
            gaps.append("symbol extraction")
        if not business.get("purpose"):
            gaps.append("documented purpose")
        if not (architecture.get("layers") or []):
            gaps.append("architecture layers")
        if gaps:
            knowledge.append(
                {
                    "memory_layer": "project",
                    "category": "coverage_gap",
                    "kind": "unverified",
                    "title": "Understanding gaps remain",
                    "content": f"Still needs verification for: {', '.join(gaps)}",
                    "confidence": 0.3,
                    "source_type": "agent",
                    "source_path": None,
                    "evidence": {"gaps": gaps},
                }
            )

        return AgentResult(
            success=True,
            summary=response.content,
            evidence={
                "model": response.model_id,
                "simulated": response.simulated,
                "scan": {
                    "languages": scan_dict.get("languages"),
                    "frameworks": scan_dict.get("frameworks"),
                    "file_stats": scan_dict.get("file_stats"),
                },
                "coverage": coverage,
            },
            knowledge=knowledge,
        )
