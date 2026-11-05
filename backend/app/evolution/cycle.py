"""Continuous evolution cycle — understand/analyze/plan/draft only.

Execute/merge/deploy stay outside this loop (human gates).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.activity import get_activity_bus
from app.autonomy import autonomy_of, may_draft_proposals, may_plan
from app.db.models import Project, ProjectStatus
from app.quality.engine import QualityEngine
from app.services.project_service import ProjectService


class EvolutionCycle:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run_project(self, project_id: UUID) -> dict[str, Any]:
        service = ProjectService(self.session)
        project = await service.get_project(project_id)
        if not project:
            raise ValueError("Project not found")

        policy = autonomy_of(project.settings if isinstance(project.settings, dict) else {})
        bus = get_activity_bus()
        bus.emit(
            "think",
            "دورة تطور مستمرة",
            detail=project.name,
            project_id=project.id,
            project_name=project.name,
            agent="MasterOrchestrator",
            intensity=0.8,
        )

        results: dict[str, Any] = {"project_id": str(project.id), "steps": []}

        if policy.get("auto_understand", True) or may_plan(project.settings):
            project.status = ProjectStatus.evolving
            await self.session.flush()
            understanding = await service.run_understanding(project.id)
            results["steps"].append({"step": "understanding", "ok": True, "summary": understanding})
            # re-load after understanding commit patterns
            project = await service.get_project(project_id) or project

        if policy.get("auto_analyze", True):
            quality = await QualityEngine(self.session).run(
                project,
                focus="full",
                draft_proposal=may_draft_proposals(project.settings),
            )
            results["steps"].append(
                {
                    "step": "quality",
                    "ok": True,
                    "findings": len(quality.get("findings") or []),
                    "proposal_id": quality.get("proposal_id"),
                }
            )

        project = await service.get_project(project_id) or project
        project.last_evolution_at = datetime.now(timezone.utc)
        if project.status == ProjectStatus.evolving:
            project.status = ProjectStatus.ready
        await self.session.commit()

        bus.emit(
            "status",
            "انتهت دورة التطور (بدون تنفيذ)",
            detail="execution/merge/deploy ما زالت بشرية",
            project_id=project.id,
            project_name=project.name,
            agent="MasterOrchestrator",
            intensity=0.4,
        )
        bus.set_idle(hint=f"آخر دورة تطور: {project.name}")
        results["status"] = "completed"
        results["last_evolution_at"] = project.last_evolution_at.isoformat()
        results["refused"] = ["auto_execute", "auto_merge", "auto_deploy"]
        return results
