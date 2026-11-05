"""Multi-Agent Orchestrator graph (Phases 4–6).

Flow:
  intelligence → parallel specialists → ProjectAnalyst → IndependentCritic
  → AnalysisEngine → PlanningEngine → END

Autonomy: plan freely; execution remains outside this graph (human-gated).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict
from uuid import UUID

from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.critic import IndependentCriticAgent
from app.agents.runtime import AgentRuntime, DispatchRequest
from app.agents.specialists import build_default_runtime_agents
from app.agents.understanding.project_analyst import ProjectAnalystAgent
from app.analysis.engine import run_analysis_engine
from app.intelligence.engine import run_project_intelligence
from app.planning.engine import run_planning_engine


class MultiAgentState(TypedDict, total=False):
    project_id: str
    workspace_path: str
    project_name: str
    parent_task_id: str
    auto_plan: bool
    intelligence: dict
    scan: dict
    specialist_reports: list[dict]
    analyst_result: dict
    critic_result: dict
    analysis: dict
    planning: dict
    knowledge: list[dict]
    needs_human: bool


PARALLEL_SPECIALISTS = (
    "CodebaseExplorer",
    "BusinessLogicAnalyst",
    "SoftwareArchitect",
    "SecurityAuditor",
    "FeatureStrategist",
)


def build_multi_agent_graph(runtime: AgentRuntime):
    graph = StateGraph(MultiAgentState)

    async def intelligence_node(state: MultiAgentState) -> MultiAgentState:
        report = run_project_intelligence(Path(state["workspace_path"]))
        payload = report.to_dict()
        return {
            **state,
            "intelligence": payload,
            "scan": payload.get("scan") or {},
            "knowledge": list(payload.get("knowledge") or []),
        }

    async def specialists_node(state: MultiAgentState) -> MultiAgentState:
        parent = UUID(state["parent_task_id"]) if state.get("parent_task_id") else None
        requests = [
            DispatchRequest(
                agent_name=name,
                objective=f"Phase-4 specialist pass: {name}",
                context={
                    "project_name": state.get("project_name"),
                    "intelligence": state.get("intelligence") or {},
                    "scan": state.get("scan") or {},
                },
                parent_task_id=parent,
            )
            for name in PARALLEL_SPECIALISTS
        ]
        results = await runtime.run_parallel(requests)
        reports = []
        knowledge = list(state.get("knowledge") or [])
        for item in results:
            reports.append(
                {
                    "agent_name": item.agent_name,
                    "department": item.department,
                    "success": item.result.success,
                    "summary": item.result.summary,
                    "task_id": str(item.task_id) if item.task_id else None,
                    "model_used": item.model_used,
                    "error": item.result.error,
                }
            )
            knowledge.extend(item.result.knowledge)
        return {**state, "specialist_reports": reports, "knowledge": knowledge}

    async def analyst_node(state: MultiAgentState) -> MultiAgentState:
        parent = UUID(state["parent_task_id"]) if state.get("parent_task_id") else None
        runtime.register(ProjectAnalystAgent())
        dispatched = await runtime.run_one(
            DispatchRequest(
                agent_name="ProjectAnalyst",
                objective="Synthesize multi-agent intelligence",
                context={
                    "project_name": state.get("project_name"),
                    "scan": state.get("scan") or {},
                    "intelligence": state.get("intelligence") or {},
                    "specialist_reports": state.get("specialist_reports") or [],
                },
                parent_task_id=parent,
            )
        )
        knowledge = list(state.get("knowledge") or [])
        knowledge.extend(dispatched.result.knowledge)
        return {
            **state,
            "analyst_result": {
                "success": dispatched.result.success,
                "summary": dispatched.result.summary,
                "evidence": dispatched.result.evidence,
                "knowledge": dispatched.result.knowledge,
                "error": dispatched.result.error,
                "task_id": str(dispatched.task_id) if dispatched.task_id else None,
            },
            "knowledge": knowledge,
        }

    async def critic_node(state: MultiAgentState) -> MultiAgentState:
        parent = UUID(state["parent_task_id"]) if state.get("parent_task_id") else None
        runtime.register(IndependentCriticAgent())
        dispatched = await runtime.run_one(
            DispatchRequest(
                agent_name="IndependentCritic",
                objective="Challenge multi-agent findings before acceptance",
                context={
                    "project_name": state.get("project_name"),
                    "intelligence": state.get("intelligence") or {},
                    "specialist_reports": state.get("specialist_reports") or [],
                    "knowledge": state.get("knowledge") or [],
                },
                parent_task_id=parent,
            )
        )
        knowledge = list(state.get("knowledge") or [])
        knowledge.extend(dispatched.result.knowledge)
        approved = bool((dispatched.result.evidence or {}).get("approved", True))
        return {
            **state,
            "critic_result": {
                "success": dispatched.result.success,
                "summary": dispatched.result.summary,
                "evidence": dispatched.result.evidence,
                "approved": approved,
                "needs_human": dispatched.result.needs_human,
                "task_id": str(dispatched.task_id) if dispatched.task_id else None,
            },
            "knowledge": knowledge,
            "needs_human": dispatched.result.needs_human or not approved,
        }

    async def analysis_node(state: MultiAgentState) -> MultiAgentState:
        report = run_analysis_engine(state.get("intelligence") or {})
        knowledge = list(state.get("knowledge") or [])
        knowledge.extend(report.knowledge)
        return {
            **state,
            "analysis": report.to_dict(),
            "knowledge": knowledge,
        }

    async def planning_node(state: MultiAgentState) -> MultiAgentState:
        if state.get("auto_plan") is False:
            return {**state, "planning": {"skipped": True, "reason": "auto_plan disabled"}}
        analysis = state.get("analysis") or {}
        report = run_planning_engine(
            project_name=state.get("project_name") or "project",
            findings=analysis.get("findings") or [],
            intelligence=state.get("intelligence") or {},
            autonomous=True,
        )
        knowledge = list(state.get("knowledge") or [])
        knowledge.extend(report.knowledge)
        return {
            **state,
            "planning": report.to_dict(),
            "knowledge": knowledge,
        }

    graph.add_node("intelligence", intelligence_node)
    graph.add_node("specialists", specialists_node)
    graph.add_node("analyze", analyst_node)
    graph.add_node("critic", critic_node)
    graph.add_node("analysis_engine", analysis_node)
    graph.add_node("planning_engine", planning_node)
    graph.set_entry_point("intelligence")
    graph.add_edge("intelligence", "specialists")
    graph.add_edge("specialists", "analyze")
    graph.add_edge("analyze", "critic")
    graph.add_edge("critic", "analysis_engine")
    graph.add_edge("analysis_engine", "planning_engine")
    graph.add_edge("planning_engine", END)
    return graph.compile()


async def run_multi_agent_understanding(
    session: AsyncSession,
    *,
    project_id: UUID,
    workspace_path: str,
    project_name: str,
    parent_task_id: UUID,
    auto_plan: bool = True,
) -> dict[str, Any]:
    runtime = AgentRuntime(session=session, project_id=project_id)
    for agent in build_default_runtime_agents():
        runtime.register(agent)
    runtime.register(ProjectAnalystAgent())
    runtime.register(IndependentCriticAgent())

    graph = build_multi_agent_graph(runtime)
    final_state = await graph.ainvoke(
        {
            "project_id": str(project_id),
            "workspace_path": workspace_path,
            "project_name": project_name,
            "parent_task_id": str(parent_task_id),
            "auto_plan": auto_plan,
        }
    )
    return dict(final_state)
