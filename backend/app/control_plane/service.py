"""Phase 12 — Multi-project control plane.

Aggregates fleet health without ever mixing project memory, workspaces,
or evolution state. Batch operations run strictly sequentially per project.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activity import get_activity_bus
from app.autonomy import autonomy_of
from app.db.models import (
    AnalysisFinding,
    FindingStatus,
    Project,
    ProjectStatus,
    Proposal,
    ProposalStatus,
)
from app.evolution.cycle import EvolutionCycle
from app.services.project_service import ProjectService


class ControlPlaneService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def fleet(self) -> dict[str, Any]:
        projects = await ProjectService(self.session).list_projects()
        cards: list[dict[str, Any]] = []
        for project in projects:
            cards.append(await self._project_card(project))

        by_status: dict[str, int] = {}
        awaiting = 0
        for card in cards:
            by_status[card["status"]] = by_status.get(card["status"], 0) + 1
            awaiting += int(card["awaiting_approval"])

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "totals": {
                "projects": len(cards),
                "by_status": by_status,
                "awaiting_approval": awaiting,
            },
            "projects": cards,
            "isolation_guarantee": (
                "Each project keeps a unique workspace + namespace; "
                "fleet APIs never share knowledge graphs or agent memory. "
                "SpixaPattern library shares only abstract approved patterns — never client paths or secrets."
            ),
            "knowledge_network": {
                "private": "project KnowledgeGraph",
                "shared": "approved SpixaPattern abstracts only",
            },
        }

    async def evolve_fleet(
        self,
        *,
        only_ready: bool = True,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Run evolution cycles one project at a time (hard isolation)."""
        bus = get_activity_bus()
        bus.emit(
            "think",
            "لوحة التحكم متعددة المشاريع — دورة أسطول",
            detail=f"limit={limit}",
            agent="MasterOrchestrator",
            intensity=0.7,
            set_focus=False,
        )

        projects = await ProjectService(self.session).list_projects()
        selected: list[Project] = []
        for project in projects:
            if only_ready and project.status not in {
                ProjectStatus.ready,
                ProjectStatus.created,
                ProjectStatus.evolving,
            }:
                continue
            policy = autonomy_of(project.settings if isinstance(project.settings, dict) else {})
            if not policy.get("auto_plan", True):
                continue
            selected.append(project)
            if len(selected) >= limit:
                break

        results: list[dict[str, Any]] = []
        for project in selected:
            try:
                # Fresh cycle instance; never pass other project context
                outcome = await EvolutionCycle(self.session).run_project(project.id)
                results.append(
                    {
                        "project_id": str(project.id),
                        "slug": project.slug,
                        "ok": True,
                        "result": {
                            "status": outcome.get("status"),
                            "steps": [s.get("step") for s in outcome.get("steps") or []],
                        },
                    }
                )
            except Exception as exc:  # noqa: BLE001
                results.append(
                    {
                        "project_id": str(project.id),
                        "slug": project.slug,
                        "ok": False,
                        "error": str(exc),
                    }
                )

        return {
            "status": "completed",
            "processed": len(results),
            "results": results,
            "isolation": "sequential_per_project",
        }

    async def _project_card(self, project: Project) -> dict[str, Any]:
        awaiting = await self.session.scalar(
            select(func.count())
            .select_from(Proposal)
            .where(
                Proposal.project_id == project.id,
                Proposal.status.in_(
                    [
                        ProposalStatus.awaiting_approval,
                        ProposalStatus.awaiting_merge,
                        ProposalStatus.approved,
                    ]
                ),
            )
        )
        open_findings = await self.session.scalar(
            select(func.count())
            .select_from(AnalysisFinding)
            .where(
                AnalysisFinding.project_id == project.id,
                AnalysisFinding.status == FindingStatus.open,
            )
        )
        policy = autonomy_of(project.settings if isinstance(project.settings, dict) else {})
        return {
            "id": str(project.id),
            "name": project.name,
            "slug": project.slug,
            "status": project.status.value if hasattr(project.status, "value") else str(project.status),
            "isolation_namespace": project.isolation_namespace,
            "understanding_progress": project.understanding_progress,
            "last_analyzed_at": project.last_analyzed_at.isoformat()
            if project.last_analyzed_at
            else None,
            "last_evolution_at": project.last_evolution_at.isoformat()
            if project.last_evolution_at
            else None,
            "awaiting_approval": int(awaiting or 0),
            "open_findings": int(open_findings or 0),
            "languages": project.languages or [],
            "frameworks": project.frameworks or [],
            "autonomy": policy,
            "href": f"/projects/{project.id}",
        }
