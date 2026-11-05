"""Phase 7 — Proposal & Approval System."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    DecisionRecord,
    FindingStatus,
    Proposal,
    ProposalStatus,
    RoadmapItem,
    RoadmapItemStatus,
    AnalysisFinding,
)


class ProposalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_proposals(
        self,
        project_id: UUID,
        *,
        status: str | None = None,
    ) -> list[Proposal]:
        stmt = select(Proposal).where(Proposal.project_id == project_id)
        if status:
            stmt = stmt.where(Proposal.status == ProposalStatus(status))
        stmt = stmt.order_by(Proposal.priority.desc(), Proposal.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get(self, project_id: UUID, proposal_id: UUID) -> Proposal | None:
        result = await self.session.execute(
            select(Proposal).where(
                Proposal.id == proposal_id,
                Proposal.project_id == project_id,
            )
        )
        return result.scalar_one_or_none()

    async def draft_from_roadmap(
        self,
        project_id: UUID,
        *,
        min_priority: int = 70,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Autonomously draft awaiting_approval proposals from high-priority roadmap items."""
        items = await self.session.execute(
            select(RoadmapItem)
            .where(
                RoadmapItem.project_id == project_id,
                RoadmapItem.status.in_(
                    [RoadmapItemStatus.planned, RoadmapItemStatus.ready_for_proposal]
                ),
                RoadmapItem.priority >= min_priority,
            )
            .order_by(RoadmapItem.priority.desc())
            .limit(limit)
        )
        created = 0
        proposals: list[dict[str, Any]] = []
        for item in items.scalars().all():
            existing = await self.session.execute(
                select(Proposal).where(
                    Proposal.project_id == project_id,
                    Proposal.roadmap_item_id == item.id,
                    Proposal.status.in_(
                        [
                            ProposalStatus.draft,
                            ProposalStatus.awaiting_approval,
                            ProposalStatus.approved,
                            ProposalStatus.executing,
                        ]
                    ),
                )
            )
            if existing.scalar_one_or_none():
                continue

            proposal = Proposal(
                project_id=project_id,
                roadmap_item_id=item.id,
                title=item.title,
                problem=item.description,
                proposal=item.goal,
                rationale=item.rationale,
                impact=f"Impact score={item.impact_score:.2f}; parts={item.affected_parts}",
                risks=item.risks,
                acceptance_criteria=item.acceptance_criteria,
                priority=item.priority,
                complexity=item.complexity,
                status=ProposalStatus.awaiting_approval,
                category=item.category,
                affected_parts=item.affected_parts or [],
                dependencies=item.dependencies or [],
                evidence={
                    **(item.evidence or {}),
                    "finding_fingerprint": item.finding_fingerprint,
                    "roadmap_item_id": str(item.id),
                },
                origin="roadmap",
                notified_at=datetime.now(timezone.utc),
            )
            self.session.add(proposal)
            item.status = RoadmapItemStatus.in_proposal
            if item.finding_fingerprint:
                await self._mark_finding_converted(project_id, item.finding_fingerprint)
            created += 1
            proposals.append({"title": proposal.title, "priority": proposal.priority})

        await self.session.flush()
        return {"drafted": created, "proposals": proposals}

    async def create_from_user_request(
        self,
        project_id: UUID,
        *,
        title: str,
        user_request: str,
        rationale: str,
        proposal_text: str,
        affected_parts: list[Any] | None = None,
        category: str = "feature",
        priority: int = 60,
    ) -> Proposal:
        proposal = Proposal(
            project_id=project_id,
            title=title,
            problem=user_request,
            proposal=proposal_text,
            rationale=rationale,
            impact="User-requested change; blast radius to be validated before execution.",
            risks="Requires independent review before merge.",
            acceptance_criteria=(
                "1) User request satisfied.\n"
                "2) Existing tests pass / new tests added.\n"
                "3) Independent review approved."
            ),
            priority=priority,
            complexity="medium",
            status=ProposalStatus.awaiting_approval,
            category=category,
            affected_parts=affected_parts or [],
            evidence={"origin": "chat"},
            origin="chat",
            user_request=user_request,
            notified_at=datetime.now(timezone.utc),
        )
        self.session.add(proposal)
        await self.session.flush()
        return proposal

    async def approve(self, project_id: UUID, proposal_id: UUID) -> Proposal:
        proposal = await self._require(project_id, proposal_id)
        if proposal.status not in {
            ProposalStatus.awaiting_approval,
            ProposalStatus.revision_requested,
            ProposalStatus.draft,
        }:
            raise ValueError(f"Cannot approve proposal in status {proposal.status.value}")
        proposal.status = ProposalStatus.approved
        proposal.approved_at = datetime.now(timezone.utc)
        self.session.add(
            DecisionRecord(
                project_id=project_id,
                decision=f"Approved proposal: {proposal.title}",
                rationale=proposal.rationale,
                made_by="human",
                alternatives=["reject", "request_revision"],
                evidence={"proposal_id": str(proposal.id)},
                related_proposal_id=proposal.id,
            )
        )
        await self.session.flush()
        return proposal

    async def reject(self, project_id: UUID, proposal_id: UUID, reason: str = "") -> Proposal:
        proposal = await self._require(project_id, proposal_id)
        proposal.status = ProposalStatus.rejected
        proposal.revision_notes = reason or proposal.revision_notes
        self.session.add(
            DecisionRecord(
                project_id=project_id,
                decision=f"Rejected proposal: {proposal.title}",
                rationale=reason or "Rejected by human",
                made_by="human",
                alternatives=["approve", "request_revision"],
                evidence={"proposal_id": str(proposal.id)},
                related_proposal_id=proposal.id,
            )
        )
        await self.session.flush()
        return proposal

    async def request_revision(
        self, project_id: UUID, proposal_id: UUID, notes: str
    ) -> Proposal:
        proposal = await self._require(project_id, proposal_id)
        proposal.status = ProposalStatus.revision_requested
        proposal.revision_notes = notes
        self.session.add(
            DecisionRecord(
                project_id=project_id,
                decision=f"Revision requested: {proposal.title}",
                rationale=notes,
                made_by="human",
                alternatives=["approve", "reject"],
                evidence={"proposal_id": str(proposal.id)},
                related_proposal_id=proposal.id,
            )
        )
        await self.session.flush()
        return proposal

    async def _require(self, project_id: UUID, proposal_id: UUID) -> Proposal:
        proposal = await self.get(project_id, proposal_id)
        if not proposal:
            raise ValueError("Proposal not found")
        return proposal

    async def _mark_finding_converted(self, project_id: UUID, fingerprint: str) -> None:
        result = await self.session.execute(
            select(AnalysisFinding).where(
                AnalysisFinding.project_id == project_id,
                AnalysisFinding.fingerprint == fingerprint,
            )
        )
        finding = result.scalar_one_or_none()
        if finding:
            finding.status = FindingStatus.converted_to_proposal
