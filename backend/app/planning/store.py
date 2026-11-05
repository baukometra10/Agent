"""Persist autonomous roadmaps per project (never cross project boundaries)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Roadmap, RoadmapItem, RoadmapItemStatus, RoadmapStatus
from app.planning.engine import PlanningReport


class PlanningStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def publish_roadmap(
        self,
        project_id: UUID,
        report: PlanningReport,
    ) -> dict[str, Any]:
        # Supersede previous active roadmaps for this project only
        await self.session.execute(
            update(Roadmap)
            .where(
                Roadmap.project_id == project_id,
                Roadmap.status == RoadmapStatus.active,
            )
            .values(status=RoadmapStatus.superseded)
        )

        version = 1
        prev = await self.session.execute(
            select(Roadmap)
            .where(Roadmap.project_id == project_id)
            .order_by(Roadmap.version.desc())
            .limit(1)
        )
        last = prev.scalar_one_or_none()
        if last:
            version = int(last.version) + 1

        roadmap = Roadmap(
            project_id=project_id,
            version=version,
            title=report.title,
            vision=report.vision,
            status=RoadmapStatus.active,
            summary=report.summary,
            generated_by="PlanningEngine",
            autonomous=report.autonomous,
        )
        self.session.add(roadmap)
        await self.session.flush()

        for item in report.items:
            self.session.add(
                RoadmapItem(
                    roadmap_id=roadmap.id,
                    project_id=project_id,
                    finding_fingerprint=item.finding_fingerprint,
                    title=item.title,
                    description=item.description,
                    rationale=item.rationale,
                    goal=item.goal,
                    category=item.category,
                    priority=item.priority,
                    complexity=item.complexity,
                    impact_score=item.impact_score,
                    risk_score=item.risk_score,
                    status=RoadmapItemStatus.ready_for_proposal
                    if item.priority >= 70
                    else RoadmapItemStatus.planned,
                    affected_parts=item.affected_parts,
                    dependencies=item.dependencies,
                    risks=item.risks,
                    acceptance_criteria=item.acceptance_criteria,
                    evidence=item.evidence,
                    sort_order=item.sort_order,
                )
            )
        await self.session.flush()
        return {
            "roadmap_id": str(roadmap.id),
            "version": version,
            "items_written": len(report.items),
            "summary": report.summary,
            "autonomous": report.autonomous,
        }

    async def get_active_roadmap(self, project_id: UUID) -> Roadmap | None:
        result = await self.session.execute(
            select(Roadmap)
            .where(
                Roadmap.project_id == project_id,
                Roadmap.status == RoadmapStatus.active,
            )
            .options(selectinload(Roadmap.items))
            .order_by(Roadmap.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
