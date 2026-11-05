"""Master Orchestrator — entrypoint for project understanding (Phase 4 multi-agent)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.multi_agent import run_multi_agent_understanding
from app.analysis.engine import AnalysisReport, FindingDraft, run_analysis_engine
from app.analysis.store import AnalysisStore
from app.autonomy import may_draft_proposals, may_plan
from app.db.models import AgentDepartment, AgentTask, Project, ProjectStatus, TaskStatus
from app.knowledge.graph import KnowledgeGraphService
from app.planning.engine import PlanningReport, PlanItemDraft, run_planning_engine
from app.planning.store import PlanningStore
from app.proposals.service import ProposalService
from app.security.isolation import assert_path_inside_workspace

AUTO_CATEGORIES = {
    "language",
    "framework",
    "entrypoint",
    "summary",
    "coverage",
    "coverage_gap",
    "code_symbols",
    "api",
    "dependencies",
    "layer",
    "risk",
    "recommendation",
    "impact",
    "purpose",
    "capability",
    "actor",
    "contradiction",
    "ui_surface",
    "design_system",
    "architecture_review",
    "security_review",
    "security_gap",
    "business_review",
    "product_opportunity",
    "code_map",
    "critique",
    "critique_issue",
    "analysis_summary",
    "finding",
    "roadmap",
}


async def _load_project(session: AsyncSession, project_id: UUID) -> Project:
    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise ValueError(f"Project not found: {project_id}")
    return project


async def run_project_understanding(session: AsyncSession, project_id: UUID) -> dict[str, Any]:
    from app.activity import get_activity_bus

    project = await _load_project(session, project_id)
    project.status = ProjectStatus.understanding
    workspace = Path(project.workspace_path)
    assert_path_inside_workspace(workspace, workspace)
    bus = get_activity_bus()
    bus.emit(
        "think",
        "بدء الفهم الذاتي للمشروع",
        detail=project.name,
        project_id=project.id,
        project_name=project.name,
        agent="MasterOrchestrator",
        intensity=0.88,
    )
    bus.emit(
        "neural",
        "إيقاظ شبكة الأقسام",
        detail="Understanding → Analysis → Planning",
        project_id=project.id,
        project_name=project.name,
        agent="MultiAgent",
        intensity=0.92,
    )

    task = AgentTask(
        project_id=project.id,
        department=AgentDepartment.orchestrator,
        agent_name="MasterOrchestrator",
        objective="Autonomous understanding + analysis + strategic planning",
        status=TaskStatus.running,
        started_at=datetime.now(timezone.utc),
        input_payload={"stage": "autonomous_plan", "phase": 6},
    )
    session.add(task)
    await session.flush()

    auto_plan = may_plan(project.settings if isinstance(project.settings, dict) else {})

    try:
        final_state = await run_multi_agent_understanding(
            session,
            project_id=project.id,
            workspace_path=project.workspace_path,
            project_name=project.name,
            parent_task_id=task.id,
            auto_plan=auto_plan,
        )
    except Exception as exc:  # noqa: BLE001
        project.status = ProjectStatus.error
        task.status = TaskStatus.failed
        task.error_message = str(exc)
        task.finished_at = datetime.now(timezone.utc)
        from app.learning.experience import get_experience_journal

        get_experience_journal().record_error(
            title=f"Understanding failed for {project.name}",
            detail=str(exc),
            specialty="project_intelligence",
            project_id=str(project.id),
        )
        await session.commit()
        raise

    scan = final_state.get("scan") or {}
    intel = final_state.get("intelligence") or {}
    analyst = final_state.get("analyst_result") or {}
    critic = final_state.get("critic_result") or {}
    knowledge_items = final_state.get("knowledge") or []
    specialist_reports = final_state.get("specialist_reports") or []
    analysis_payload = final_state.get("analysis") or {}
    if not analysis_payload:
        analysis_report = run_analysis_engine(intel)
        analysis_payload = analysis_report.to_dict()
        knowledge_items = list(knowledge_items) + list(analysis_report.knowledge)
    else:
        analysis_report = AnalysisReport(
            findings=[
                FindingDraft(
                    category=f["category"],
                    kind=f["kind"],
                    severity=f["severity"],
                    title=f["title"],
                    description=f["description"],
                    recommendation=f.get("recommendation", ""),
                    confidence=float(f.get("confidence", 0.5)),
                    affected_parts=f.get("affected_parts") or [],
                    evidence=f.get("evidence") or {},
                    source_agent=f.get("source_agent", "AnalysisEngine"),
                )
                for f in (analysis_payload.get("findings") or [])
            ],
            summary=analysis_payload.get("summary") or {},
            knowledge=analysis_payload.get("knowledge") or [],
        )

    kg = KnowledgeGraphService(session)
    graph_stats = await kg.replace_auto_knowledge(
        project.id,
        knowledge_items,
        categories=AUTO_CATEGORIES,
    )
    written = int(graph_stats.get("nodes_written") or 0)

    analysis_store = AnalysisStore(session)
    findings_stats = await analysis_store.replace_findings(project.id, analysis_report)

    planning_payload = final_state.get("planning") or {}
    planning_stats: dict[str, Any] = {"skipped": True}
    if auto_plan and not planning_payload.get("skipped"):
        if not planning_payload.get("items"):
            planning_report = run_planning_engine(
                project_name=project.name,
                findings=[f.to_dict() for f in analysis_report.findings],
                intelligence=intel,
                autonomous=True,
            )
            planning_payload = planning_report.to_dict()
            knowledge_items = list(knowledge_items) + list(planning_report.knowledge)
            # refresh knowledge with roadmap node
            graph_stats = await kg.replace_auto_knowledge(
                project.id,
                knowledge_items,
                categories=AUTO_CATEGORIES,
            )
            written = int(graph_stats.get("nodes_written") or 0)
        else:
            planning_report = PlanningReport(
                title=planning_payload.get("title") or f"Strategic roadmap — {project.name}",
                vision=planning_payload.get("vision") or "",
                items=[
                    PlanItemDraft(
                        title=i["title"],
                        description=i.get("description", ""),
                        rationale=i.get("rationale", ""),
                        goal=i.get("goal", ""),
                        category=i.get("category", "quality"),
                        priority=int(i.get("priority", 50)),
                        complexity=i.get("complexity", "medium"),
                        impact_score=float(i.get("impact_score", 0.5)),
                        risk_score=float(i.get("risk_score", 0.5)),
                        affected_parts=i.get("affected_parts") or [],
                        dependencies=i.get("dependencies") or [],
                        risks=i.get("risks", ""),
                        acceptance_criteria=i.get("acceptance_criteria", ""),
                        evidence=i.get("evidence") or {},
                        finding_fingerprint=i.get("finding_fingerprint"),
                        sort_order=int(i.get("sort_order", 0)),
                    )
                    for i in (planning_payload.get("items") or [])
                ],
                summary=planning_payload.get("summary") or {},
                knowledge=planning_payload.get("knowledge") or [],
                autonomous=bool(planning_payload.get("autonomous", True)),
            )
        planning_stats = await PlanningStore(session).publish_roadmap(project.id, planning_report)

    proposal_stats: dict[str, Any] = {"drafted": 0}
    if may_draft_proposals(project.settings if isinstance(project.settings, dict) else {}):
        proposal_stats = await ProposalService(session).draft_from_roadmap(project.id)

    coverage = intel.get("coverage") or {}
    project.languages = scan.get("languages") or []
    project.frameworks = scan.get("frameworks") or []
    project.tech_stack = {
        **(scan.get("tech_stack") or {}),
        "intelligence": {
            "code_stats": (intel.get("code") or {}).get("stats") or {},
            "layers": coverage.get("layers") or [],
            "purpose_known": coverage.get("purpose_known", False),
            "business": {
                "actors": (intel.get("business") or {}).get("actors") or [],
                "capabilities": (intel.get("business") or {}).get("capabilities") or [],
            },
            "visual": (intel.get("visual") or {}).get("ui_surfaces") or [],
            "architecture_risks": (intel.get("architecture") or {}).get("risks") or [],
        },
        "multi_agent": {
            "specialists": [r.get("agent_name") for r in specialist_reports],
            "critic_approved": critic.get("approved"),
            "needs_human": final_state.get("needs_human", False),
        },
        "analysis": findings_stats.get("summary") or {},
        "planning": planning_stats,
        "proposals": proposal_stats,
        "autonomy": (project.settings or {}).get("autonomy")
        if isinstance(project.settings, dict)
        else {},
    }
    project.file_stats = scan.get("file_stats") or {}
    progress = float(
        coverage.get("understanding_progress")
        or min(1.0, 0.35 + 0.05 * len(project.frameworks))
    )
    if critic.get("approved"):
        progress = min(0.98, progress + 0.05)
    project.understanding_progress = progress
    project.last_analyzed_at = datetime.now(timezone.utc)
    project.status = ProjectStatus.ready

    task.status = TaskStatus.succeeded
    task.output_payload = {
        "summary": analyst.get("summary"),
        "critic_summary": critic.get("summary"),
        "critic_approved": critic.get("approved"),
        "needs_human": final_state.get("needs_human", False),
        "specialists": specialist_reports,
        "knowledge_written": written,
        "findings_written": findings_stats.get("findings_written"),
        "analysis_summary": findings_stats.get("summary"),
        "planning": planning_stats,
        "proposals": proposal_stats,
        "edges_written": graph_stats.get("edges_written"),
        "counts_by_layer": graph_stats.get("counts_by_layer"),
        "progress": project.understanding_progress,
        "coverage": coverage,
    }
    task.evidence = {
        "analyst": analyst.get("evidence") or {},
        "critic": critic.get("evidence") or {},
        "analysis": findings_stats.get("summary") or {},
        "planning": planning_stats,
        "proposals": proposal_stats,
    }
    task.finished_at = datetime.now(timezone.utc)

    # Engineering advisory: improvements + risks as human-gated proposals
    from app.advisory.intake import IntakeAdvisor
    from app.learning.experience import get_experience_journal

    advisory: dict[str, Any] = {}
    try:
        advisory = await IntakeAdvisor(session).advise_after_understanding(project)
        get_experience_journal().record_success(
            title=f"Understood engineering of {project.name}",
            detail=advisory.get("message_ar") or analyst.get("summary") or "",
            specialty="project_intelligence",
            project_id=str(project.id),
            meta={"risks": len(advisory.get("risks") or []), "improvements": len(advisory.get("improvements") or [])},
        )
    except Exception as adv_exc:  # noqa: BLE001
        get_experience_journal().record_error(
            title=f"Advisory failed for {project.name}",
            detail=str(adv_exc),
            specialty="project_intelligence",
            project_id=str(project.id),
        )
        advisory = {"error": str(adv_exc)}

    await session.commit()

    return {
        "project_id": str(project.id),
        "status": project.status.value,
        "understanding_progress": project.understanding_progress,
        "knowledge_written": written,
        "summary": analyst.get("summary"),
        "scan": {
            "languages": project.languages,
            "frameworks": project.frameworks,
            "file_stats": project.file_stats,
        },
        "intelligence": {
            "coverage": coverage,
            "code_stats": (intel.get("code") or {}).get("stats") or {},
            "layers": coverage.get("layers") or [],
            "purpose": (intel.get("business") or {}).get("purpose"),
            "api_endpoints": ((intel.get("code") or {}).get("api_endpoints") or [])[:20],
            "architecture_risks": (intel.get("architecture") or {}).get("risks") or [],
        },
        "knowledge_graph": graph_stats,
        "multi_agent": {
            "specialists": specialist_reports,
            "critic": {
                "approved": critic.get("approved"),
                "needs_human": critic.get("needs_human"),
                "summary": critic.get("summary"),
            },
            "needs_human": final_state.get("needs_human", False),
        },
        "analysis": {
            "summary": findings_stats.get("summary") or {},
            "findings_written": findings_stats.get("findings_written"),
            "findings": (analysis_payload.get("findings") or [])[:30],
        },
        "planning": planning_stats,
        "proposals": proposal_stats,
        "advisory": advisory,
        "autonomy": {
            "auto_plan": auto_plan,
            "auto_draft_proposals": True,
            "auto_execute": False,
            "policy": "cursor_like_chat_plus_autonomous_evolution_gated_execute",
        },
    }
