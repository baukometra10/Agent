"""After a project is uploaded/understood — engineering brief + improvements + risks.

Does not mutate source files; drafts human-gated proposals only.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AnalysisFinding, Project, Proposal, ProposalStatus
from app.proposals.service import ProposalService
from sqlalchemy import select


class IntakeAdvisor:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def advise_after_understanding(self, project: Project) -> dict[str, Any]:
        """Build an engineering advisory from findings + tech stack; draft proposals."""
        findings = await self.session.execute(
            select(AnalysisFinding)
            .where(AnalysisFinding.project_id == project.id)
            .order_by(AnalysisFinding.created_at.desc())
            .limit(40)
        )
        rows = list(findings.scalars().all())
        stack = project.tech_stack if isinstance(project.tech_stack, dict) else {}
        intel = (stack.get("intelligence") or {}) if isinstance(stack, dict) else {}
        risks = list(intel.get("architecture_risks") or [])
        layers = list(intel.get("layers") or [])
        purpose = bool(intel.get("purpose_known"))

        improvements: list[dict[str, Any]] = []
        risk_items: list[dict[str, Any]] = []

        for f in rows:
            item = {
                "title": f.title,
                "severity": f.severity.value if hasattr(f.severity, "value") else str(f.severity),
                "recommendation": f.recommendation,
                "category": f.category,
            }
            sev = item["severity"]
            if sev in {"high", "critical"} or f.category in {"security", "risk", "security_gap"}:
                risk_items.append(item)
            else:
                improvements.append(item)

        for r in risks[:8]:
            if isinstance(r, dict):
                risk_items.append(
                    {
                        "title": r.get("title") or r.get("risk") or "Architecture risk",
                        "severity": r.get("severity") or "medium",
                        "recommendation": r.get("recommendation") or str(r),
                        "category": "architecture",
                    }
                )
            else:
                risk_items.append(
                    {
                        "title": str(r)[:120],
                        "severity": "medium",
                        "recommendation": "Review architecture risk during planning.",
                        "category": "architecture",
                    }
                )

        if not purpose:
            improvements.insert(
                0,
                {
                    "title": "Clarify product purpose and primary user journeys",
                    "severity": "medium",
                    "recommendation": "Document actors, capabilities, and success metrics in-repo.",
                    "category": "product",
                }
            )

        engineering_brief = {
            "project": project.name,
            "languages": project.languages or [],
            "frameworks": project.frameworks or [],
            "layers": layers,
            "purpose_known": purpose,
            "file_stats": project.file_stats or {},
            "understanding": (
                "Agent mapped languages, frameworks, architecture layers, and open findings. "
                "Suggestions below are proposals only — originals stay untouched until you approve."
            ),
        }

        drafted = await self._draft_top_proposals(project.id, risk_items, improvements)

        return {
            "engineering_brief": engineering_brief,
            "improvements": improvements[:15],
            "risks": risk_items[:15],
            "proposals_drafted": drafted,
            "message_ar": (
                f"فهمت هندسة «{project.name}». "
                f"وجدت {len(risk_items)} مخاطر و{len(improvements)} فرص تحسين. "
                "المقترحات بانتظار موافقتك — لم يُمس أي ملف أصلي."
            ),
        }

    async def _draft_top_proposals(
        self,
        project_id: UUID,
        risks: list[dict[str, Any]],
        improvements: list[dict[str, Any]],
    ) -> dict[str, Any]:
        service = ProposalService(self.session)
        created: list[dict[str, str]] = []
        # Prefer risks first, then improvements
        candidates = [{**r, "_kind": "risk"} for r in risks[:3]] + [
            {**i, "_kind": "improvement"} for i in improvements[:2]
        ]
        for c in candidates:
            title = str(c.get("title") or "Advisory item")[:160]
            # Skip if similar awaiting proposal exists
            existing = await self.session.execute(
                select(Proposal).where(
                    Proposal.project_id == project_id,
                    Proposal.title == title,
                    Proposal.status.in_(
                        [
                            ProposalStatus.draft,
                            ProposalStatus.awaiting_approval,
                            ProposalStatus.approved,
                        ]
                    ),
                )
            )
            if existing.scalar_one_or_none():
                continue
            kind = c.get("_kind")
            proposal = await service.create_from_user_request(
                project_id,
                title=title,
                user_request=f"Intake advisory ({kind}): {title}",
                rationale=(
                    f"Severity={c.get('severity')}. Category={c.get('category')}. "
                    f"Recommendation: {c.get('recommendation')}"
                ),
                proposal_text=(
                    f"Suggested change: {c.get('recommendation') or title}. "
                    "Work must happen on a sandbox copy first; originals require human approval."
                ),
                category="security" if kind == "risk" else "quality",
                priority=85 if kind == "risk" else 65,
            )
            # tag origin
            proposal.origin = "intake_advisory"
            proposal.risks = (
                f"Risk severity={c.get('severity')}. Validate blast radius before execute."
            )
            proposal.evidence = {
                **(proposal.evidence or {}),
                "advisory_kind": kind,
                "category": c.get("category"),
            }
            created.append({"id": str(proposal.id), "title": proposal.title, "kind": str(kind)})

        await self.session.flush()
        return {"drafted": len(created), "items": created}
