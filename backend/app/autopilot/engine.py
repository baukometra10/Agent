"""مساعد الطيار — unattended monitor that NEVER touches original project files.

User enables autopilot before leaving. Agent:
1. Clones each project into an experimental sandbox
2. Analyzes / ideates only inside the sandbox
3. Sends a comprehensive report (email/queue) with why / risks / improvements
4. Leaves originals untouched until human approves proposals
"""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activity import get_activity_bus
from app.advisory.intake import IntakeAdvisor
from app.autopilot.notify import send_report_email
from app.autopilot.sandbox_patch import apply_experimental_patches
from app.autopilot.sandbox_review import review_sandbox
from app.config import Settings, get_settings
from app.db.models import Project
from app.intelligence.scanner import scan_workspace
from app.learning.experience import get_experience_journal
from app.proposals.service import ProposalService
from app.security.isolation import assert_path_inside_workspace


class AutopilotEngine:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = Path(self.settings.workspaces_root).parent / "autopilot"
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / "state.json"

    def status(self) -> dict[str, Any]:
        state = self._load_state()
        interval = max(30, int(self.settings.autopilot_interval_seconds))
        return {
            "enabled": bool(state.get("enabled")),
            "paused_for_manual": bool(state.get("paused_for_manual")),
            "mode": "مساعد الطيار",
            "mode_en": "Autopilot",
            "doctrine": (
                "Monitor + ideate on sandbox copies only. "
                "Never write original project files. Report to human for approval. "
                "While ON, background loop keeps cycling; manual chat pauses it."
            ),
            "notify_email": state.get("notify_email"),
            "project_ids": state.get("project_ids") or [],
            "last_run": state.get("last_run"),
            "last_report_path": state.get("last_report_path"),
            "runs_root": str(self.root / "runs"),
            "interval_seconds": interval,
            "ui_mode": (
                "manual"
                if not state.get("enabled")
                else "paused_manual"
                if state.get("paused_for_manual")
                else "autonomous"
            ),
        }

    def enable(
        self,
        *,
        notify_email: str | None = None,
        project_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        state = self._load_state()
        state["enabled"] = True
        state["paused_for_manual"] = False
        state["enabled_at"] = datetime.now(timezone.utc).isoformat()
        if notify_email is not None:
            state["notify_email"] = notify_email
        if project_ids is not None:
            state["project_ids"] = project_ids
        self._save_state(state)
        get_activity_bus().emit(
            "status",
            "مساعد الطيار مفعّل",
            detail="حلقة خلفية · نسخ تجريبية فقط — الأصول محمية",
            agent="Autopilot",
            intensity=0.85,
        )
        return self.status()

    def disable(self) -> dict[str, Any]:
        state = self._load_state()
        state["enabled"] = False
        state["paused_for_manual"] = False
        state["disabled_at"] = datetime.now(timezone.utc).isoformat()
        self._save_state(state)
        get_activity_bus().emit(
            "status",
            "مساعد الطيار متوقف",
            detail="وضع يدوي — أنت تعطي الأوامر",
            agent="Autopilot",
            intensity=0.4,
        )
        return self.status()

    def pause_for_manual(self, *, reason: str = "user_chat") -> dict[str, Any]:
        """When the human starts commanding manually — stop autonomous cycles."""
        state = self._load_state()
        if not state.get("enabled"):
            return self.status()
        state["paused_for_manual"] = True
        state["paused_at"] = datetime.now(timezone.utc).isoformat()
        state["pause_reason"] = reason
        self._save_state(state)
        get_activity_bus().emit(
            "status",
            "مساعد الطيار معلّق (عمل يدوي)",
            detail=reason,
            agent="Autopilot",
            intensity=0.55,
        )
        return self.status()

    def resume_autonomous(self) -> dict[str, Any]:
        state = self._load_state()
        state["enabled"] = True
        state["paused_for_manual"] = False
        state["resumed_at"] = datetime.now(timezone.utc).isoformat()
        self._save_state(state)
        get_activity_bus().emit(
            "status",
            "استئناف مساعد الطيار",
            detail="الحلقة الخلفية ستكمل الدورات",
            agent="Autopilot",
            intensity=0.8,
        )
        return self.status()

    def _clone_to_sandbox(self, project: Project, run_id: str) -> Path:
        """Copy originals into an experimental tree. Never return the original path."""
        src = Path(project.workspace_path)
        if not src.exists():
            raise FileNotFoundError(f"workspace missing: {src}")
        # Safety: source must be under workspaces_root
        assert_path_inside_workspace(Path(self.settings.workspaces_root), src)

        dest = self.root / "runs" / run_id / project.slug
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            src,
            dest,
            ignore=shutil.ignore_patterns(
                "__pycache__",
                ".venv",
                "node_modules",
                ".next",
                "*.pyc",
                "memory",  # keep sandbox clean; LTM stays with original
            ),
            dirs_exist_ok=False,
        )
        # Hard guarantee: sandbox != original
        if dest.resolve() == src.resolve():
            raise RuntimeError("sandbox path collided with original workspace")
        from app.autopilot.markers import write_sandbox_marker

        marker = write_sandbox_marker(dest)
        marker.write_text(
            json.dumps(
                {
                    "product": "Spixa",
                    "original_workspace": str(src),
                    "project_id": str(project.id),
                    "run_id": run_id,
                    "rule": "experimental only — do not promote without human approval",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return dest

    async def run_once(
        self,
        session: AsyncSession,
        *,
        force: bool = False,
        notify_email: str | None = None,
        project_ids: list[UUID] | None = None,
    ) -> dict[str, Any]:
        state = self._load_state()
        if not state.get("enabled") and not force:
            return {"ok": False, "reason": "autopilot_disabled", "status": self.status()}

        run_id = uuid.uuid4().hex[:12]
        bus = get_activity_bus()
        bus.emit(
            "think",
            "مساعد الطيار يبدأ دورة مراقبة",
            detail=f"run={run_id} · sandbox only",
            agent="Autopilot",
            intensity=0.9,
        )

        ids = project_ids
        if ids is None and state.get("project_ids"):
            ids = [UUID(x) for x in state["project_ids"]]

        stmt = select(Project).order_by(Project.created_at.desc())
        if ids:
            stmt = stmt.where(Project.id.in_(ids))
        else:
            stmt = stmt.limit(int(self.settings.autopilot_max_projects))
        result = await session.execute(stmt)
        projects = list(result.scalars().all())

        project_blocks: list[dict[str, Any]] = []
        for project in projects:
            try:
                block = await self._inspect_project(session, project, run_id)
                project_blocks.append(block)
                get_experience_journal().record_success(
                    title=f"Autopilot inspected {project.name}",
                    detail=json.dumps(block, ensure_ascii=False, default=str)[:2000],
                    specialty="project_intelligence",
                    project_id=str(project.id),
                    meta={"run_id": run_id, "sandbox": True},
                )
            except Exception as exc:  # noqa: BLE001
                get_experience_journal().record_error(
                    title=f"Autopilot failed on {project.name}",
                    detail=str(exc),
                    specialty="project_intelligence",
                    project_id=str(project.id),
                    meta={"run_id": run_id},
                )
                project_blocks.append(
                    {
                        "project_id": str(project.id),
                        "project_name": project.name,
                        "error": str(exc),
                        "originals_touched": False,
                    }
                )

        urgent = self._report_is_urgent(project_blocks)
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "projects_scanned": len(project_blocks),
            "originals_touched": False,
            "urgent": urgent,
            "urgency": "security_high" if urgent else "normal",
            "sandbox_rule": "All analysis ran on experimental copies under data/autopilot/runs",
            "projects": project_blocks,
            "human_gate": (
                "Review proposals in Spixa. Approve before any write to original workspaces."
            ),
        }

        email = notify_email or state.get("notify_email") or ""
        # Prefer per-project owner emails if no global override
        if not email and projects:
            email = next((p.owner_email for p in projects if p.owner_email), "") or ""

        notify = send_report_email(
            report, to_email=str(email or ""), settings=self.settings, urgent=urgent
        )
        state["last_run"] = report["generated_at"]
        state["last_report_path"] = notify.get("queued_path") or notify.get("latest")
        state["last_run_id"] = run_id
        self._save_state(state)

        bus.emit(
            "memory",
            "تقرير مساعد الطيار جاهز",
            detail=f"projects={len(project_blocks)} · emailed={notify.get('sent')}",
            agent="Autopilot",
            intensity=0.7,
            payload={"run_id": run_id, "notify": notify},
        )
        return {"ok": True, "report": report, "notify": notify, "status": self.status()}

    async def _inspect_project(
        self, session: AsyncSession, project: Project, run_id: str
    ) -> dict[str, Any]:
        sandbox = self._clone_to_sandbox(project, run_id)
        # Analyze sandbox tree only
        repo = sandbox / "repo"
        target = repo if repo.exists() else sandbox
        scan = scan_workspace(target)

        # Advisory from persisted findings (project DB) + fresh sandbox scan signals
        advisory = await IntakeAdvisor(session).advise_after_understanding(project)
        sandbox_review = review_sandbox(sandbox)
        experiment = apply_experimental_patches(
            sandbox,
            project_name=project.name,
            review=sandbox_review,
            advisory=advisory,
        )
        # Human-gated proposal pointing at sandbox experiment (never auto-applied to originals)
        proposal_info = await self._draft_sandbox_proposal(
            session,
            project,
            experiment=experiment,
            review=sandbox_review,
            run_id=run_id,
        )

        languages = scan.languages if hasattr(scan, "languages") else (scan.get("languages") if isinstance(scan, dict) else [])
        frameworks = scan.frameworks if hasattr(scan, "frameworks") else (scan.get("frameworks") if isinstance(scan, dict) else [])
        file_stats = scan.file_stats if hasattr(scan, "file_stats") else (scan.get("file_stats") if isinstance(scan, dict) else {})

        improvements = [
            f"{i.get('title')}: {i.get('recommendation')}"
            for i in (advisory.get("improvements") or [])[:6]
        ]
        improvements += [
            f"{i.get('title')}: {i.get('recommendation')}"
            for i in (sandbox_review.get("improvements") or [])[:6]
        ]
        risks = [
            f"[{i.get('severity')}] {i.get('title')}: {i.get('recommendation')}"
            for i in (advisory.get("risks") or [])[:6]
        ]
        risks += [
            f"[{i.get('severity')}] {i.get('title')}: {i.get('recommendation')}"
            for i in (sandbox_review.get("risks") or [])[:6]
        ]
        security = [
            f"[{i.get('severity')}] {i.get('title')}: {i.get('recommendation')}"
            for i in (sandbox_review.get("security") or [])[:8]
        ]
        proposed = [
            f"{p.get('kind')}: {p.get('title')}"
            for p in ((advisory.get("proposals_drafted") or {}).get("items") or [])
        ]
        if proposal_info:
            proposed.append(f"sandbox_experiment: {proposal_info.get('title')}")

        why = (
            f"أثناء غيابك راقب مساعد الطيار نسخة تجريبية من «{project.name}». "
            f"اللغات={languages} · الأطر={frameworks} · ملفات={sandbox_review.get('files_scanned')}. "
            f"طُبّقت {experiment.get('patch_count', 0)} تعديلات تجريبية داخل sandbox فقط. "
            "الهدف: تحسين الجودة وتقليل مخاطر الأمن قبل لمس الملفات الأصلية."
        )
        return {
            "project_id": str(project.id),
            "project_name": project.name,
            "sandbox_path": str(sandbox),
            "original_workspace": project.workspace_path,
            "originals_touched": False,
            "scan": {
                "languages": languages,
                "frameworks": frameworks,
                "file_stats": file_stats,
            },
            "sandbox_review": {
                "files_scanned": sandbox_review.get("files_scanned"),
                "security_count": len(sandbox_review.get("security") or []),
                "risk_count": len(sandbox_review.get("risks") or []),
                "improvement_count": len(sandbox_review.get("improvements") or []),
            },
            "experiment": {
                "files_changed": experiment.get("files_changed"),
                "patch_count": experiment.get("patch_count"),
                "diff_path": experiment.get("diff_path"),
                "suggestions_path": experiment.get("suggestions_path"),
                "combined_diff_preview": (experiment.get("combined_diff") or "")[:4000],
            },
            "proposal": proposal_info,
            "why": why,
            "improvements": improvements,
            "risks": risks,
            "security": security,
            "proposed_fixes": proposed,
            "advisory_message": advisory.get("message_ar"),
            "engineering_brief": advisory.get("engineering_brief"),
        }

    async def _draft_sandbox_proposal(
        self,
        session: AsyncSession,
        project: Project,
        *,
        experiment: dict[str, Any],
        review: dict[str, Any],
        run_id: str,
    ) -> dict[str, Any] | None:
        files = experiment.get("files_changed") or []
        if not files:
            return None
        title = f"مساعد الطيار: تجربة sandbox ({run_id})"
        service = ProposalService(session)
        # Avoid flooding: one open copilot proposal per project
        from sqlalchemy import select
        from app.db.models import Proposal, ProposalStatus

        existing = await session.execute(
            select(Proposal).where(
                Proposal.project_id == project.id,
                Proposal.origin == "copilot_sandbox",
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
            return {"skipped": True, "reason": "open_copilot_proposal_exists"}

        sec_n = len(review.get("security") or [])
        risk_n = len(review.get("risks") or [])
        proposal = await service.create_from_user_request(
            project.id,
            title=title,
            user_request=(
                "مساعد الطيار أنشأ تعديلات داخل نسخة تجريبية فقط. "
                "راجع الـ diff ثم وافق قبل أي نقل للأصل."
            ),
            rationale=(
                f"Security hits={sec_n}, risks={risk_n}, "
                f"sandbox files={', '.join(files[:8])}"
            ),
            proposal_text=(
                "Apply the experimental sandbox changes after human review. "
                f"Diff at: {experiment.get('diff_path')}. "
                f"Brief: {experiment.get('suggestions_path')}."
            ),
            affected_parts=files[:12],
            category="quality",
            priority=70 + min(20, sec_n * 5),
        )
        proposal.origin = "copilot_sandbox"
        proposal.risks = (
            "Changes currently exist only under data/autopilot/runs. "
            "Do not copy blindly — validate blast radius."
        )
        proposal.evidence = {
            **(proposal.evidence or {}),
            "sandbox_path": experiment.get("manifest_path"),
            "diff_path": experiment.get("diff_path"),
            "combined_diff_preview": (experiment.get("combined_diff") or "")[:3000],
            "run_id": run_id,
            "originals_touched": False,
        }
        await session.flush()
        return {
            "proposal_id": str(proposal.id),
            "title": proposal.title,
            "status": proposal.status.value,
        }

    @staticmethod
    def _report_is_urgent(project_blocks: list[dict[str, Any]]) -> bool:
        for block in project_blocks:
            if not isinstance(block, dict):
                continue
            for row in (block.get("security") or []) + (block.get("risks") or []):
                text = str(row).lower()
                if "[critical]" in text or "[high]" in text or "critical" in text:
                    return True
            review = block.get("sandbox_review") or {}
            if int(review.get("security_count") or 0) > 0:
                # Any sandbox security hit is urgent for the human inbox
                return True
        return False

    def list_reports(self, *, limit: int = 20) -> list[dict[str, Any]]:
        root = Path(self.settings.learning_data_root) / "autopilot" / "reports"
        if not root.exists():
            return []
        files = sorted(root.glob("report-*.json"), reverse=True)[:limit]
        out: list[dict[str, Any]] = []
        for path in files:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            out.append(
                {
                    "id": path.stem,
                    "path": str(path),
                    "generated_at": data.get("generated_at"),
                    "run_id": data.get("run_id"),
                    "projects_scanned": data.get("projects_scanned"),
                    "originals_touched": data.get("originals_touched", False),
                    "urgent": bool(data.get("urgent")),
                    "summary": self._summarize_report(data),
                    "report": data,
                }
            )
        return out

    def latest_report(self) -> dict[str, Any] | None:
        rows = self.list_reports(limit=1)
        return rows[0] if rows else None

    @staticmethod
    def _summarize_report(data: dict[str, Any]) -> str:
        projects = data.get("projects") or []
        n = len(projects)
        risks = sum(len(p.get("risks") or []) for p in projects if isinstance(p, dict))
        sec = sum(len(p.get("security") or []) for p in projects if isinstance(p, dict))
        patches = sum(
            int((p.get("experiment") or {}).get("patch_count") or 0)
            for p in projects
            if isinstance(p, dict)
        )
        return f"مساعد الطيار: {n} مشاريع · مخاطر={risks} · أمن={sec} · تعديلات تجريبية={patches}"

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"enabled": False}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"enabled": False}

    def _save_state(self, state: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )


_autopilot: AutopilotEngine | None = None


def get_autopilot() -> AutopilotEngine:
    global _autopilot
    if _autopilot is None:
        _autopilot = AutopilotEngine()
    return _autopilot


def reset_autopilot() -> None:
    global _autopilot
    _autopilot = None
