"""Phase-4 specialist agents — consume Project Intelligence with model synthesis."""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentResult, AgentSpec, BaseAgent
from app.db.models import AgentDepartment
from app.gateway.router import ModelGateway, ModelRole, get_model_gateway


class _IntelSpecialist(BaseAgent):
    category: str = "general"
    memory_layer: str = "architecture"

    def __init__(self, gateway: ModelGateway | None = None) -> None:
        self.gateway = gateway or get_model_gateway()

    def _extract(self, intelligence: dict[str, Any]) -> dict[str, Any]:
        return intelligence

    async def run(self, context: dict[str, Any]) -> AgentResult:
        intelligence = context.get("intelligence") or {}
        project_name = context.get("project_name", "project")
        payload = self._extract(intelligence)
        prompt = (
            f"You are {self.spec.name}. Analyze project '{project_name}'.\n"
            f"Evidence payload: {payload}\n"
            "Distinguish fact vs inference. Do not invent evidence."
        )
        response = await self.gateway.complete(
            self.spec.model_role,
            prompt,
            system=f"You are {self.spec.name} on Evolve. Cite only provided evidence.",
            metadata={"agent": self.spec.name},
        )
        knowledge = [
            {
                "memory_layer": self.memory_layer,
                "category": self.category,
                "kind": "inference",
                "title": f"{self.spec.name} assessment",
                "content": response.content,
                "confidence": 0.45 if response.simulated else 0.68,
                "source_type": "agent",
                "source_path": None,
                "evidence": {"payload_keys": list(payload.keys()), "model": response.model_id},
            }
        ]
        # Promote deterministic signals as facts when present
        knowledge.extend(self._fact_nodes(payload))
        return AgentResult(
            success=True,
            summary=response.content,
            evidence={"model": response.model_id, "payload": payload},
            knowledge=knowledge,
        )

    def _fact_nodes(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return []


class SoftwareArchitectAgent(_IntelSpecialist):
    spec = AgentSpec(
        name="SoftwareArchitect",
        department=AgentDepartment.engineering,
        description="System architecture assessment",
        model_role=ModelRole.reasoning,
    )
    category = "architecture_review"
    memory_layer = "architecture"

    def _extract(self, intelligence: dict[str, Any]) -> dict[str, Any]:
        arch = intelligence.get("architecture") or {}
        code = intelligence.get("code") or {}
        return {
            "layers": arch.get("layers"),
            "risks": arch.get("risks"),
            "coupling": (arch.get("coupling") or [])[:8],
            "api_endpoints": (code.get("api_endpoints") or [])[:12],
            "entry_flows": code.get("entry_flows"),
        }

    def _fact_nodes(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        nodes = []
        for layer in payload.get("layers") or []:
            nodes.append(
                {
                    "memory_layer": "architecture",
                    "category": "layer",
                    "kind": "fact",
                    "title": f"Layer confirmed for review: {layer.get('layer')}",
                    "content": f"{layer.get('file_count')} files under {layer.get('layer')}",
                    "confidence": 0.85,
                    "source_type": "file",
                    "source_path": (layer.get("files") or [None])[0],
                    "evidence": layer,
                }
            )
        return nodes[:6]


class SecurityAuditorAgent(_IntelSpecialist):
    spec = AgentSpec(
        name="SecurityAuditor",
        department=AgentDepartment.security,
        description="Security posture from structure and signals",
        model_role=ModelRole.reasoning,
    )
    category = "security_review"
    memory_layer = "architecture"

    def _extract(self, intelligence: dict[str, Any]) -> dict[str, Any]:
        scan = intelligence.get("scan") or {}
        code = intelligence.get("code") or {}
        business = intelligence.get("business") or {}
        return {
            "frameworks": scan.get("frameworks"),
            "entry_points": scan.get("entry_points"),
            "api_count": len(code.get("api_endpoints") or []),
            "capabilities": business.get("capabilities"),
            "actors": business.get("actors"),
        }

    def _fact_nodes(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        nodes = []
        if payload.get("api_count", 0) > 0 and not payload.get("actors"):
            nodes.append(
                {
                    "memory_layer": "architecture",
                    "category": "security_gap",
                    "kind": "unverified",
                    "title": "APIs present but actors/roles not evidenced",
                    "content": "Authorization model needs verification before privilege changes.",
                    "confidence": 0.4,
                    "source_type": "agent",
                    "source_path": None,
                    "evidence": payload,
                }
            )
        return nodes


class BusinessLogicAnalystAgent(_IntelSpecialist):
    spec = AgentSpec(
        name="BusinessLogicAnalyst",
        department=AgentDepartment.understanding,
        description="Business rules and capabilities",
        model_role=ModelRole.reasoning,
    )
    category = "business_review"
    memory_layer = "project"

    def _extract(self, intelligence: dict[str, Any]) -> dict[str, Any]:
        business = intelligence.get("business") or {}
        return {
            "purpose": business.get("purpose"),
            "actors": business.get("actors"),
            "capabilities": business.get("capabilities"),
            "contradictions": business.get("contradictions"),
        }


class FeatureStrategistAgent(_IntelSpecialist):
    spec = AgentSpec(
        name="FeatureStrategist",
        department=AgentDepartment.product,
        description="Opportunity signals from gaps and capabilities",
        model_role=ModelRole.reasoning,
    )
    category = "product_opportunity"
    memory_layer = "project"

    def _extract(self, intelligence: dict[str, Any]) -> dict[str, Any]:
        business = intelligence.get("business") or {}
        architecture = intelligence.get("architecture") or {}
        visual = intelligence.get("visual") or {}
        return {
            "capabilities": business.get("capabilities"),
            "contradictions": business.get("contradictions"),
            "risks": architecture.get("risks"),
            "ui_surfaces": visual.get("ui_surfaces"),
            "suggested_future": architecture.get("suggested_future"),
        }


class CodebaseExplorerAgent(_IntelSpecialist):
    spec = AgentSpec(
        name="CodebaseExplorer",
        department=AgentDepartment.understanding,
        description="Maps codebase structure from deterministic intel",
        model_role=ModelRole.fast,
    )
    category = "code_map"
    memory_layer = "architecture"

    def _extract(self, intelligence: dict[str, Any]) -> dict[str, Any]:
        code = intelligence.get("code") or {}
        scan = intelligence.get("scan") or {}
        return {
            "stats": code.get("stats"),
            "languages": scan.get("languages"),
            "top_directories": scan.get("top_directories"),
            "modules_sample": (code.get("modules") or [])[:15],
        }


def build_default_runtime_agents() -> list[BaseAgent]:
    return [
        CodebaseExplorerAgent(),
        BusinessLogicAnalystAgent(),
        SoftwareArchitectAgent(),
        SecurityAuditorAgent(),
        FeatureStrategistAgent(),
        # Critic registered separately in graph usually
    ]
