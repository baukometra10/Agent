"""Venture orchestrator — multi-phase pipeline with human gates."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.activity import get_activity_bus
from app.db.models import (
    DecisionRecord,
    Project,
    ProposalStatus,
    VenturePhase,
    VenturePhaseName,
    VenturePhaseStatus,
    VentureRun,
    VentureStatus,
)
from app.proposals.service import ProposalService
from app.quality.engine import QualityEngine
from app.services.project_service import ProjectService
from app.venture.adversarial import AdversarialLab
from app.venture.evolution_sim import EvolutionSimulator
from app.venture.generative import GenerativeDesignEngine
from app.venture.patterns import PatternLibrary
from app.venture.phases import PHASE_LABELS_AR, PHASE_ORDER, PHASE_REQUIRES_APPROVAL
from app.venture.twin import DigitalTwinService


class VentureOrchestrator:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.projects = ProjectService(session)
        self.generative = GenerativeDesignEngine(session)
        self.twin = DigitalTwinService(session)
        self.adversarial = AdversarialLab(session)
        self.evolution = EvolutionSimulator(session)
        self.patterns = PatternLibrary(session)
        self.proposals = ProposalService(session)

    async def list_ventures(self, project_id: UUID) -> list[dict[str, Any]]:
        result = await self.session.execute(
            select(VentureRun)
            .where(VentureRun.project_id == project_id)
            .options(selectinload(VentureRun.phases))
            .order_by(VentureRun.created_at.desc())
        )
        return [self.serialize(v) for v in result.scalars().all()]

    async def get(self, project_id: UUID, venture_id: UUID) -> VentureRun | None:
        result = await self.session.execute(
            select(VentureRun)
            .where(VentureRun.id == venture_id, VentureRun.project_id == project_id)
            .options(selectinload(VentureRun.phases))
        )
        return result.scalar_one_or_none()

    async def create(self, project_id: UUID, *, brief: str, title: str | None = None) -> dict[str, Any]:
        project = await self.projects.get_project(project_id)
        if not project:
            raise ValueError("Project not found")
        clean = (brief or "").strip()
        if len(clean) < 8:
            raise ValueError("Brief too short")
        title_clean = (title or "").strip() or clean.split("\n", 1)[0][:80]
        venture = VentureRun(
            project_id=project_id,
            title=title_clean,
            brief=clean,
            status=VentureStatus.running,
            current_phase=VenturePhaseName.understand.value,
            decision_log=[
                {
                    "at": datetime.now(timezone.utc).isoformat(),
                    "event": "created",
                    "by": "VentureOrchestrator",
                    "detail": title_clean,
                }
            ],
            artifacts={},
        )
        self.session.add(venture)
        await self.session.flush()
        for i, phase in enumerate(PHASE_ORDER):
            self.session.add(
                VenturePhase(
                    venture_id=venture.id,
                    name=phase.value,
                    sort_order=i,
                    status=VenturePhaseStatus.pending,
                    requires_approval=PHASE_REQUIRES_APPROVAL.get(phase.value, False),
                )
            )
        await self.session.commit()
        # Auto-run understand + capabilities
        await self.advance(project_id, venture.id, auto=True)
        venture = await self.get(project_id, venture.id)
        assert venture
        return self.serialize(venture)

    async def advance(
        self,
        project_id: UUID,
        venture_id: UUID,
        *,
        auto: bool = False,
        selected_architecture_id: str | None = None,
    ) -> dict[str, Any]:
        venture = await self.get(project_id, venture_id)
        if not venture:
            raise ValueError("Venture not found")
        if venture.status in {VentureStatus.cancelled, VentureStatus.rejected, VentureStatus.completed}:
            return self.serialize(venture)

        project = await self.projects.get_project(project_id)
        if not project:
            raise ValueError("Project not found")

        if selected_architecture_id:
            venture.selected_architecture_id = selected_architecture_id
            self._log(venture, "architecture_selected", selected_architecture_id)

        phase = self._current_phase_row(venture)
        if not phase:
            venture.status = VentureStatus.completed
            await self.session.commit()
            return self.serialize(venture)

        # If awaiting approval, do not run unless explicitly approved via approve()
        if phase.status == VenturePhaseStatus.awaiting_approval and auto:
            return self.serialize(venture)
        if phase.status == VenturePhaseStatus.awaiting_approval and not auto:
            # Caller should use approve(); treat as no-op
            return self.serialize(venture)

        if phase.status in {VenturePhaseStatus.completed, VenturePhaseStatus.approved, VenturePhaseStatus.skipped}:
            nxt = self._next_phase_row(venture, phase)
            if not nxt:
                venture.status = VentureStatus.completed
                venture.current_phase = phase.name
                await self.session.commit()
                return self.serialize(venture)
            venture.current_phase = nxt.name
            phase = nxt

        bus = get_activity_bus()
        bus.emit(
            "think",
            f"Venture · {PHASE_LABELS_AR.get(phase.name, phase.name)}",
            detail=venture.title,
            project_id=project.id,
            project_name=project.name,
            agent="VentureOrchestrator",
            intensity=0.85,
        )

        phase.status = VenturePhaseStatus.running
        phase.started_at = datetime.now(timezone.utc)
        venture.status = VentureStatus.running
        venture.current_phase = phase.name
        await self.session.flush()

        try:
            output = await self._run_phase(project, venture, phase.name)
            phase.output = output
            phase.finished_at = datetime.now(timezone.utc)
            artifacts = dict(venture.artifacts or {})
            artifacts[phase.name] = output
            venture.artifacts = artifacts
            self._log(venture, "phase_completed", phase.name, extra={"keys": list(output.keys())[:12]})

            if phase.requires_approval:
                phase.status = VenturePhaseStatus.awaiting_approval
                venture.status = VentureStatus.awaiting_approval
                self._log(venture, "awaiting_approval", phase.name)
            else:
                phase.status = VenturePhaseStatus.completed
                # Chain next free phases (understand → capabilities)
                await self.session.commit()
                if phase.name in {
                    VenturePhaseName.understand.value,
                    VenturePhaseName.capabilities.value,
                }:
                    return await self.advance(project_id, venture_id, auto=True)
                return self.serialize(await self.get(project_id, venture_id) or venture)

            await self.session.commit()
            return self.serialize(await self.get(project_id, venture_id) or venture)
        except Exception as exc:  # noqa: BLE001
            phase.status = VenturePhaseStatus.failed
            phase.output = {"error": str(exc)[:500]}
            phase.finished_at = datetime.now(timezone.utc)
            venture.status = VentureStatus.failed
            self._log(venture, "phase_failed", phase.name, extra={"error": str(exc)[:300]})
            await self.session.commit()
            raise

    async def approve(
        self,
        project_id: UUID,
        venture_id: UUID,
        *,
        actor: str = "human",
        selected_architecture_id: str | None = None,
        acknowledge_adversarial: bool = False,
    ) -> dict[str, Any]:
        venture = await self.get(project_id, venture_id)
        if not venture:
            raise ValueError("Venture not found")
        phase = self._current_phase_row(venture)
        if not phase or phase.status != VenturePhaseStatus.awaiting_approval:
            raise ValueError("No phase awaiting approval")

        # Adversarial gate for high-risk phases (overridable with explicit ack)
        if phase.name in {
            VenturePhaseName.architecture.value,
            VenturePhaseName.implement.value,
            VenturePhaseName.prototype.value,
        }:
            report = (phase.output or {}).get("adversarial") or {}
            if report.get("blocking") and not acknowledge_adversarial:
                raise ValueError(
                    "Adversarial Lab blocking: resolve critical findings or set acknowledge_adversarial=true"
                )
            if report.get("blocking") and acknowledge_adversarial:
                self._log(
                    venture,
                    "adversarial_acknowledged",
                    phase.name,
                    extra={"by": actor, "critical_count": report.get("critical_count")},
                )

        if selected_architecture_id:
            venture.selected_architecture_id = selected_architecture_id

        phase.status = VenturePhaseStatus.approved
        phase.approved_at = datetime.now(timezone.utc)
        phase.approved_by = actor
        self._log(venture, "phase_approved", phase.name, extra={"by": actor})
        self.session.add(
            DecisionRecord(
                project_id=project_id,
                decision=f"Approved venture phase {phase.name}",
                rationale=venture.title,
                made_by=actor,
                alternatives=["reject", "revise"],
                evidence={
                    "venture_id": str(venture.id),
                    "phase": phase.name,
                    "acknowledge_adversarial": acknowledge_adversarial,
                },
            )
        )
        await self.session.commit()

        # Re-load after commit to avoid stale/detached state
        venture = await self.get(project_id, venture_id)
        if not venture:
            raise ValueError("Venture missing after approve")
        phase = self._current_phase_row(venture)
        if not phase:
            venture.status = VentureStatus.completed
            await self.session.commit()
            return self.serialize(venture)
        nxt = self._next_phase_row(venture, phase)
        if not nxt:
            venture.status = VentureStatus.completed
            await self.session.commit()
            return self.serialize(venture)
        venture.current_phase = nxt.name
        venture.status = VentureStatus.running
        await self.session.commit()
        return await self.advance(project_id, venture_id, auto=False)

    async def start_demo_company_os(self, project_id: UUID) -> dict[str, Any]:
        """Golden-path demo brief: adaptive company operating system."""
        brief = (
            "أريد منظومة لإدارة شركة، تتكيف مع توسع الشركة، وتطور عملياتها، "
            "وتكتشف الاختناقات، وتقترح تحسينات مستمرة — مع بوابات موافقة بشرية قبل الدمج."
        )
        return await self.create(
            project_id,
            brief=brief,
            title="Demo · Firmen-OS / منظومة الشركة",
        )

    async def reject(
        self,
        project_id: UUID,
        venture_id: UUID,
        *,
        reason: str = "",
        actor: str = "human",
    ) -> dict[str, Any]:
        venture = await self.get(project_id, venture_id)
        if not venture:
            raise ValueError("Venture not found")
        phase = self._current_phase_row(venture)
        if phase:
            phase.status = VenturePhaseStatus.rejected
            phase.finished_at = datetime.now(timezone.utc)
            phase.output = {**(phase.output or {}), "reject_reason": reason}
        venture.status = VentureStatus.rejected
        self._log(venture, "rejected", phase.name if phase else "", extra={"by": actor, "reason": reason})
        await self.session.commit()
        return self.serialize(venture)

    async def _run_phase(self, project: Project, venture: VentureRun, name: str) -> dict[str, Any]:
        brief = venture.brief
        if name == VenturePhaseName.understand.value:
            twin = await self.twin.rebuild(project)
            understanding = None
            try:
                understanding = await self.projects.run_understanding(project.id)
            except Exception as exc:  # noqa: BLE001
                understanding = {"error": str(exc)[:300]}
            return {
                "purpose_hint": twin.get("purpose"),
                "twin": twin,
                "understanding": understanding,
                "label": PHASE_LABELS_AR[name],
            }

        if name == VenturePhaseName.capabilities.value:
            design = await self.generative.build_spec(project, brief)
            artifacts = dict(venture.artifacts or {})
            artifacts["design"] = design
            venture.artifacts = artifacts
            return {
                "spec": design.get("spec"),
                "files": design.get("files"),
                "patterns_used": design.get("patterns_used"),
                "label": PHASE_LABELS_AR[name],
            }

        if name == VenturePhaseName.architecture.value:
            spec = ((venture.artifacts or {}).get("capabilities") or {}).get("spec") or (
                (venture.artifacts or {}).get("design") or {}
            ).get("spec")
            twin = dict((project.settings or {}).get("digital_twin") or {})
            alts = await self.evolution.generate_alternatives(
                project, brief=brief, spec=spec, twin=twin
            )
            chosen = venture.selected_architecture_id or alts.get("recommended_id")
            arch_blob = next(
                (a for a in alts.get("alternatives") or [] if a.get("id") == chosen),
                (alts.get("alternatives") or [None])[0],
            )
            critique = await self.adversarial.critique(
                project,
                artifact_title="architecture alternatives",
                artifact_text=str(alts)[:6000],
                twin_context=twin,
            )
            return {
                "evolution": alts,
                "selected_id": chosen,
                "selected": arch_blob,
                "adversarial": critique,
                "label": PHASE_LABELS_AR[name],
            }

        if name == VenturePhaseName.prototype.value:
            design = (venture.artifacts or {}).get("design") or (venture.artifacts or {}).get("capabilities") or {}
            files = design.get("files") or []
            proposal = await self.proposals.create_from_user_request(
                project.id,
                title=f"Venture prototype — {venture.title}"[:255],
                user_request=brief,
                rationale="Generative design pack ready for human review before implementation.",
                proposal_text=(
                    "Review .spixa/design pack and approve before DevelopmentEngine execution.\n"
                    f"Files: {', '.join(files[:12])}"
                ),
                affected_parts=files[:40],
                category="venture",
                priority=80,
            )
            venture.proposal_id = proposal.id
            critique = await self.adversarial.critique(
                project,
                artifact_title=proposal.title,
                artifact_text=f"{proposal.proposal}\n{proposal.risks}\n{brief}",
                twin_context=dict((project.settings or {}).get("digital_twin") or {}),
            )
            return {
                "proposal_id": str(proposal.id),
                "files": files,
                "adversarial": critique,
                "label": PHASE_LABELS_AR[name],
            }

        if name == VenturePhaseName.simulate.value:
            files = ((venture.artifacts or {}).get("prototype") or {}).get("files") or []
            sim = await self.twin.simulate_change(
                project,
                change_summary=brief,
                affected_paths=[f for f in files if isinstance(f, str)][:30],
            )
            return {"simulation": sim, "label": PHASE_LABELS_AR[name]}

        if name == VenturePhaseName.implement.value:
            # Quality pass + documentation notes; execution stays on approved proposal via existing APIs
            quality = await QualityEngine(self.session).run(
                project, focus="full", draft_proposal=False
            )
            proposal_id = venture.proposal_id
            if proposal_id:
                prop = await self.proposals.get(project.id, proposal_id)
                if prop and prop.status == ProposalStatus.awaiting_approval:
                    pass
            critique = await self.adversarial.critique(
                project,
                artifact_title="implement gate",
                artifact_text=str(quality)[:5000],
                twin_context=dict((project.settings or {}).get("digital_twin") or {}),
            )
            docs = {
                "note": "Implementation proceeds only after proposal approve + execute + merge (human).",
                "proposal_id": str(proposal_id) if proposal_id else None,
                "quality_findings": len(quality.get("findings") or []),
            }
            return {
                "quality": {
                    "findings": len(quality.get("findings") or []),
                    "proposal_id": quality.get("proposal_id"),
                },
                "docs": docs,
                "adversarial": critique,
                "label": PHASE_LABELS_AR[name],
            }

        if name == VenturePhaseName.monitor.value:
            twin = await self.twin.rebuild(project)
            return {
                "twin": twin,
                "suggestions": [
                    "Enable EvolutionCycle for continuous understand/analyze (no auto-merge).",
                    "Watch twin risk nodes after traffic grows.",
                    "Harvest successful patterns into Spixa Pattern Library (abstract only).",
                ],
                "label": PHASE_LABELS_AR[name],
            }

        return {"label": PHASE_LABELS_AR.get(name, name)}

    def _current_phase_row(self, venture: VentureRun) -> VenturePhase | None:
        by_name = {p.name: p for p in venture.phases or []}
        return by_name.get(venture.current_phase) or (
            sorted(venture.phases or [], key=lambda p: p.sort_order)[0] if venture.phases else None
        )

    def _next_phase_row(self, venture: VentureRun, current: VenturePhase) -> VenturePhase | None:
        ordered = sorted(venture.phases or [], key=lambda p: p.sort_order)
        for p in ordered:
            if p.sort_order > current.sort_order:
                return p
        return None

    def _log(self, venture: VentureRun, event: str, detail: str = "", extra: dict[str, Any] | None = None) -> None:
        log = list(venture.decision_log or [])
        entry: dict[str, Any] = {
            "at": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "detail": detail,
        }
        if extra:
            entry["extra"] = extra
        log.append(entry)
        venture.decision_log = log[-200:]

    def serialize(self, venture: VentureRun) -> dict[str, Any]:
        phases = sorted(venture.phases or [], key=lambda p: p.sort_order)
        return {
            "id": str(venture.id),
            "project_id": str(venture.project_id),
            "title": venture.title,
            "brief": venture.brief,
            "status": venture.status.value if hasattr(venture.status, "value") else venture.status,
            "current_phase": venture.current_phase,
            "selected_architecture_id": venture.selected_architecture_id,
            "proposal_id": str(venture.proposal_id) if venture.proposal_id else None,
            "decision_log": venture.decision_log or [],
            "artifacts": venture.artifacts or {},
            "phases": [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "label": PHASE_LABELS_AR.get(p.name, p.name),
                    "sort_order": p.sort_order,
                    "status": p.status.value if hasattr(p.status, "value") else p.status,
                    "requires_approval": p.requires_approval,
                    "output": p.output or {},
                    "approved_at": p.approved_at.isoformat() if p.approved_at else None,
                    "approved_by": p.approved_by,
                }
                for p in phases
            ],
            "created_at": venture.created_at.isoformat() if venture.created_at else None,
            "updated_at": venture.updated_at.isoformat() if venture.updated_at else None,
        }
