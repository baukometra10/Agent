"""Departmental agent registry — stubs grow into full experts over phases."""

from __future__ import annotations

from app.agents.base import AgentSpec
from app.db.models import AgentDepartment
from app.gateway.router import ModelRole

AGENT_REGISTRY: list[AgentSpec] = [
    # Orchestration / Critic — Cursor-class hierarchy
    AgentSpec(
        "MasterOrchestrator",
        AgentDepartment.orchestrator,
        "Lead agent — plans, routes specialists, synthesizes (Cursor seat)",
        ModelRole.reasoning,
        tier="conductor",
        cursor_role="Primary Agent",
    ),
    AgentSpec(
        "IndependentCritic",
        AgentDepartment.critic,
        "Challenges plans and findings; never implement+approve",
        ModelRole.critic,
        tier="critic",
        cursor_role="Reviewer",
    ),
    # Understanding
    AgentSpec("ProjectAnalyst", AgentDepartment.understanding, "Understands project purpose", ModelRole.reasoning),
    AgentSpec("CodebaseExplorer", AgentDepartment.understanding, "Maps codebase structure", ModelRole.fast),
    AgentSpec("BusinessLogicAnalyst", AgentDepartment.understanding, "Extracts business rules", ModelRole.reasoning),
    # Engineering
    AgentSpec("SoftwareArchitect", AgentDepartment.engineering, "System architecture", ModelRole.reasoning),
    AgentSpec("BackendArchitect", AgentDepartment.engineering, "Backend architecture", ModelRole.reasoning),
    AgentSpec("FrontendArchitect", AgentDepartment.engineering, "Frontend architecture", ModelRole.reasoning),
    AgentSpec("DatabaseArchitect", AgentDepartment.engineering, "Data architecture", ModelRole.reasoning),
    # Design
    AgentSpec("UIDesigner", AgentDepartment.design, "UI design proposals", ModelRole.multimodal),
    AgentSpec("UXResearcher", AgentDepartment.design, "UX evaluation", ModelRole.multimodal),
    AgentSpec("DesignSystemAgent", AgentDepartment.design, "Design system consistency", ModelRole.multimodal),
    # Product
    AgentSpec("ProductManager", AgentDepartment.product, "Product strategy", ModelRole.reasoning),
    AgentSpec("RequirementsAnalyst", AgentDepartment.product, "Requirements analysis", ModelRole.fast),
    AgentSpec("FeatureStrategist", AgentDepartment.product, "Feature opportunities", ModelRole.reasoning),
    # Development
    AgentSpec("BackendDeveloper", AgentDepartment.development, "Backend coding", ModelRole.coding, can_execute_code=True),
    AgentSpec("FrontendDeveloper", AgentDepartment.development, "Frontend coding", ModelRole.coding, can_execute_code=True),
    AgentSpec("FullstackDeveloper", AgentDepartment.development, "Full-stack coding", ModelRole.coding, can_execute_code=True),
    AgentSpec("RefactoringAgent", AgentDepartment.development, "Safe refactors", ModelRole.coding, can_execute_code=True),
    # Security
    AgentSpec("SecurityAuditor", AgentDepartment.security, "Security review", ModelRole.reasoning),
    AgentSpec("PermissionsAnalyst", AgentDepartment.security, "AuthZ analysis", ModelRole.fast),
    AgentSpec("VulnerabilityAnalyst", AgentDepartment.security, "Vulnerability hunting", ModelRole.reasoning),
    # Quality
    AgentSpec("QAEngineer", AgentDepartment.quality, "QA strategy", ModelRole.fast),
    AgentSpec("TestEngineer", AgentDepartment.quality, "Test generation/execution", ModelRole.coding),
    AgentSpec("CodeReviewer", AgentDepartment.quality, "Independent code review", ModelRole.critic),
    AgentSpec("PerformanceAnalyst", AgentDepartment.quality, "Performance analysis", ModelRole.reasoning),
    # Operations
    AgentSpec("DevOpsEngineer", AgentDepartment.operations, "Infra and pipelines", ModelRole.coding),
    AgentSpec("DeploymentAgent", AgentDepartment.operations, "Deployments", ModelRole.coding),
    AgentSpec("MonitoringAgent", AgentDepartment.operations, "Observability", ModelRole.fast),
    # Documentation
    AgentSpec("TechnicalWriter", AgentDepartment.documentation, "Docs authoring", ModelRole.fast),
    AgentSpec("APIDocumentationAgent", AgentDepartment.documentation, "API docs", ModelRole.fast),
    AgentSpec("KnowledgeCurator", AgentDepartment.documentation, "Knowledge hygiene", ModelRole.fast),
]


def list_agents() -> list[dict]:
    return [
        {
            "name": a.name,
            "department": a.department.value,
            "description": a.description,
            "model_role": a.model_role.value,
            "can_execute_code": a.can_execute_code,
            "can_self_approve": a.can_self_approve,
            "tier": a.tier,
            "cursor_role": a.cursor_role or a.department.value,
        }
        for a in AGENT_REGISTRY
    ]


def get_agent_spec(name: str) -> AgentSpec | None:
    for spec in AGENT_REGISTRY:
        if spec.name == name:
            return spec
    return None


AGENT_INDEX: dict[str, AgentSpec] = {spec.name: spec for spec in AGENT_REGISTRY}
