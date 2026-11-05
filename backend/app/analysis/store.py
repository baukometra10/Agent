"""Persist Analysis Engine findings (project-scoped)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.engine import AnalysisReport, FindingDraft
from app.db.models import AnalysisFinding, FindingKind, FindingSeverity, FindingStatus


class AnalysisStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replace_findings(
        self,
        project_id: UUID,
        report: AnalysisReport,
    ) -> dict[str, Any]:
        await self.session.execute(
            delete(AnalysisFinding).where(AnalysisFinding.project_id == project_id)
        )
        written = 0
        for draft in report.findings:
            self.session.add(self._to_row(project_id, draft))
            written += 1
        await self.session.flush()
        return {"findings_written": written, "summary": report.summary}

    def _to_row(self, project_id: UUID, draft: FindingDraft) -> AnalysisFinding:
        return AnalysisFinding(
            project_id=project_id,
            category=draft.category,
            kind=FindingKind(draft.kind),
            severity=FindingSeverity(draft.severity),
            status=FindingStatus.open,
            title=draft.title,
            description=draft.description,
            recommendation=draft.recommendation,
            confidence=draft.confidence,
            affected_parts=draft.affected_parts,
            evidence=draft.evidence,
            source_agent=draft.source_agent,
            fingerprint=draft.fingerprint(),
        )

    async def list_findings(
        self,
        project_id: UUID,
        *,
        category: str | None = None,
        kind: str | None = None,
        severity: str | None = None,
        limit: int = 200,
    ) -> list[AnalysisFinding]:
        stmt = select(AnalysisFinding).where(AnalysisFinding.project_id == project_id)
        if category:
            stmt = stmt.where(AnalysisFinding.category == category)
        if kind:
            stmt = stmt.where(AnalysisFinding.kind == FindingKind(kind))
        if severity:
            stmt = stmt.where(AnalysisFinding.severity == FindingSeverity(severity))
        stmt = stmt.order_by(AnalysisFinding.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
