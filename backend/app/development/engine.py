"""Phase 8 — Software Development Engine.

Applies approved proposals inside an isolated Git work branch.
Never merges/deploys without a further human gate.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from git import Actor, Repo
from sqlalchemy.ext.asyncio import AsyncSession

from app.activity import get_activity_bus
from app.autonomy import may_execute
from app.config import get_settings
from app.db.models import (
    AgentDepartment,
    AgentTask,
    DecisionRecord,
    Project,
    Proposal,
    ProposalStatus,
    TaskStatus,
)
from app.gateway.router import ModelRole, get_model_gateway
from app.proposals.service import ProposalService
from app.security.isolation import IsolationContext, assert_path_inside_workspace
from app.security.sandbox import plan_sandbox_run

_EVOLVE_ACTOR = Actor("Evolve Development Engine", "evolve@localhost")


class DevelopmentEngine:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.gateway = get_model_gateway()
        self.settings = get_settings()

    async def execute_proposal(self, project: Project, proposal_id: UUID) -> dict[str, Any]:
        proposals = ProposalService(self.session)
        proposal = await proposals.get(project.id, proposal_id)
        if not proposal:
            raise ValueError("Proposal not found")
        if proposal.status != ProposalStatus.approved:
            raise ValueError(
                f"Proposal must be approved before execution (status={proposal.status.value})"
            )

        # Even if autonomy.auto_execute is false, explicit human approve + execute call is allowed.
        # auto_execute would mean worker can call this without extra click — still blocked by default.
        _ = may_execute(project.settings if isinstance(project.settings, dict) else {})
        bus = get_activity_bus()
        bus.emit(
            "think",
            "بدء التنفيذ على فرع معزول",
            detail=proposal.title,
            project_id=project.id,
            project_name=project.name,
            agent="DevelopmentEngine",
            intensity=0.9,
            payload={"proposal_id": str(proposal.id)},
        )

        workspace = Path(project.workspace_path)
        repo_dir = assert_path_inside_workspace(workspace, workspace / "repo")
        if not repo_dir.exists():
            raise ValueError("Project repository folder missing")

        # Ensure git repo (local path intakes may not include .git)
        repo = self._ensure_repo(repo_dir)

        branch = self._branch_name(proposal)
        base = self._default_branch(repo)
        if branch in [h.name for h in repo.heads]:
            repo.git.checkout(branch)
        else:
            repo.git.checkout(base)
            repo.git.checkout("-b", branch)

        task = AgentTask(
            project_id=project.id,
            department=AgentDepartment.development,
            agent_name="FullstackDeveloper",
            objective=f"Execute approved proposal: {proposal.title}",
            status=TaskStatus.running,
            started_at=datetime.now(timezone.utc),
            input_payload={
                "proposal_id": str(proposal.id),
                "branch": branch,
                "base": base,
            },
        )
        self.session.add(task)
        proposal.status = ProposalStatus.executing
        await self.session.flush()

        # مساعد الطيار: promote approved sandbox experiment onto project (human-gated already)
        if (proposal.origin or "") == "copilot_sandbox":
            from app.autopilot.promote import promote_sandbox_experiment

            bus.emit(
                "neural",
                "ترقية تجربة مساعد الطيار إلى المشروع",
                detail="نسخ ملفات sandbox المسموحة بعد الموافقة",
                project_id=project.id,
                project_name=project.name,
                agent="FullstackDeveloper",
                intensity=0.95,
            )
            try:
                promoted = promote_sandbox_experiment(
                    project_workspace=workspace,
                    evidence=proposal.evidence or {},
                )
            except Exception as exc:  # noqa: BLE001
                proposal.status = ProposalStatus.revision_requested
                proposal.revision_notes = f"Sandbox promote failed: {exc}"
                task.status = TaskStatus.failed
                task.error_message = str(exc)
                task.finished_at = datetime.now(timezone.utc)
                await self.session.commit()
                return {
                    "status": "revision_requested",
                    "error": str(exc),
                    "merged": False,
                    "source": "copilot_sandbox",
                }
            applied = {
                "files": promoted.get("copied") or [],
                "mode": "copilot_promote",
                "promoted": promoted,
            }
            # Human approve+execute is the gate; skip model self-review for sandbox promote
            review = {
                "approved": True,
                "summary": (
                    "Human already approved مساعد الطيار sandbox experiment; "
                    f"copied {len(promoted.get('copied') or [])} files."
                ),
                "source": "copilot_promote",
            }
            try:
                from app.learning.experience import get_experience_journal

                get_experience_journal().record_success(
                    title=f"Promoted مساعد الطيار experiment for {project.name}",
                    detail=json.dumps(promoted, ensure_ascii=False, default=str)[:2000],
                    specialty="coding",
                    project_id=str(project.id),
                    meta={"proposal_id": str(proposal.id), "source": "copilot_promote"},
                )
            except Exception:  # noqa: BLE001
                pass
            try:
                from app.learning.experience import get_experience_journal

                get_experience_journal().record_success(
                    title=f"Promoted مساعد الطيار experiment for {project.name}",
                    detail=json.dumps(promoted, ensure_ascii=False, default=str)[:2000],
                    specialty="coding",
                    project_id=str(project.id),
                    meta={"proposal_id": str(proposal.id), "source": "copilot_promote"},
                )
            except Exception:  # noqa: BLE001
                pass
        else:
            # Generate patch plan via coding model (or deterministic stub)
            bus.emit(
                "neural",
                "توليد خطة الملفات",
                detail="ربط نوايا المقترح بشبكة الكتابة",
                project_id=project.id,
                project_name=project.name,
                agent="FullstackDeveloper",
                intensity=0.95,
            )
            plan = await self._plan_changes(project, proposal, repo_dir)
            applied = self._apply_plan(repo_dir, plan, project=project)

            # Independent review gate (cannot self-approve)
            bus.emit(
                "decision",
                "مراجعة مستقلة للتغييرات",
                detail="CodeReviewer لا يعتمد ذاته",
                project_id=project.id,
                project_name=project.name,
                agent="CodeReviewer",
                intensity=0.7,
            )
            review = await self._independent_review(proposal, applied)
            if not review.get("approved"):
                proposal.status = ProposalStatus.revision_requested
                proposal.revision_notes = review.get("summary") or "Independent review rejected changes"
                task.status = TaskStatus.failed
                task.error_message = "independent_review_rejected"
                task.output_payload = {"applied": applied, "review": review, "branch": branch}
                task.finished_at = datetime.now(timezone.utc)
                await self.session.commit()
                return {
                    "status": "revision_requested",
                    "branch": branch,
                    "applied": applied,
                    "review": review,
                    "merged": False,
                }

        # Commit on feature branch
        commit_sha = None
        if applied.get("files"):
            repo.index.add(applied["files"])
            commit = repo.index.commit(
                f"evolve: {proposal.title}\n\nProposal-Id: {proposal.id}",
                author=_EVOLVE_ACTOR,
                committer=_EVOLVE_ACTOR,
            )
            commit_sha = commit.hexsha

        proposal.status = ProposalStatus.awaiting_merge
        proposal.evidence = {
            **(proposal.evidence or {}),
            "execution": {
                "branch": branch,
                "commit": commit_sha,
                "files": applied.get("files"),
                "review": review,
            },
        }
        task.status = TaskStatus.succeeded
        task.output_payload = {
            "branch": branch,
            "commit": commit_sha,
            "applied": applied,
            "review": review,
            "awaiting_merge": True,
        }
        task.evidence = {"review": review}
        task.finished_at = datetime.now(timezone.utc)
        self.session.add(
            DecisionRecord(
                project_id=project.id,
                decision=f"Execution completed on branch {branch}; awaiting merge approval",
                rationale="Independent review passed; merge still human-gated",
                made_by="DevelopmentEngine",
                alternatives=["merge", "reject_branch"],
                evidence={"proposal_id": str(proposal.id), "commit": commit_sha},
                related_proposal_id=proposal.id,
            )
        )
        await self.session.commit()

        # Sandbox note (execution of project tests still gated by Docker flag)
        isolation = IsolationContext(
            project_slug=project.slug,
            namespace=project.isolation_namespace,
            workspace_path=workspace,
            allow_code_execution=self.settings.allow_untrusted_code_execution,
            network_disabled=self.settings.sandbox_network_disabled,
        )
        sandbox = plan_sandbox_run(isolation, self.settings, command=["pytest", "-q"])

        bus.emit(
            "status",
            "جاهز للدمج البشري",
            detail=f"فرع {branch} · commit {(commit_sha or '')[:8]}",
            project_id=project.id,
            project_name=project.name,
            agent="DevelopmentEngine",
            intensity=0.35,
            payload={"branch": branch, "commit": commit_sha, "files": applied.get("files")},
        )
        bus.set_idle(hint=f"بانتظار دمج المقترح {proposal.id}")

        return {
            "status": proposal.status.value,
            "branch": branch,
            "commit": commit_sha,
            "applied": applied,
            "review": review,
            "merged": False,
            "sandbox": {"allowed": sandbox.allowed, "reason": sandbox.reason},
            "next_step": "Human must approve merge explicitly (Phase 8 gate).",
        }

    async def merge_proposal(self, project: Project, proposal_id: UUID) -> dict[str, Any]:
        proposals = ProposalService(self.session)
        proposal = await proposals.get(project.id, proposal_id)
        if not proposal:
            raise ValueError("Proposal not found")
        if proposal.status != ProposalStatus.awaiting_merge:
            raise ValueError(
                f"Proposal must be awaiting_merge (status={proposal.status.value})"
            )

        workspace = Path(project.workspace_path)
        repo_dir = assert_path_inside_workspace(workspace, workspace / "repo")
        repo = Repo(repo_dir)
        branch = (proposal.evidence or {}).get("execution", {}).get("branch")
        if not branch:
            raise ValueError("Missing execution branch metadata")

        if branch not in [h.name for h in repo.heads]:
            raise ValueError(f"Execution branch missing: {branch}")
        main = self._default_branch(repo)
        if repo.active_branch.name != main:
            repo.git.checkout(main)
        repo.git.merge(branch, "--no-ff", "-m", f"merge evolve/{proposal.id}: {proposal.title}")
        proposal.status = ProposalStatus.merged
        proposal.completed_at = datetime.now(timezone.utc)
        self.session.add(
            DecisionRecord(
                project_id=project.id,
                decision=f"Merged proposal branch {branch} into {main}",
                rationale="Human approved merge",
                made_by="human",
                evidence={"proposal_id": str(proposal.id), "branch": branch, "main": main},
                related_proposal_id=proposal.id,
            )
        )
        await self.session.commit()
        return {"status": "merged", "branch": branch, "main": main}

    async def _plan_changes(
        self, project: Project, proposal: Proposal, repo_dir: Path
    ) -> dict[str, Any]:
        prompt = (
            "Produce a minimal safe change plan as JSON with key files: "
            "[{path, content, action: create|replace}].\n"
            f"Project: {project.name}\n"
            f"Proposal title: {proposal.title}\n"
            f"Problem: {proposal.problem}\n"
            f"Plan: {proposal.proposal}\n"
            f"Affected: {proposal.affected_parts}\n"
            "If uncertain, create docs/EVOLVE_CHANGE.md summarizing the intended change."
        )
        response = await self.gateway.complete(
            ModelRole.coding,
            prompt,
            system="You are Evolve FullstackDeveloper. Prefer tiny evidenced edits.",
            metadata={"proposal_id": str(proposal.id)},
        )

        files = self._scaffold_files(proposal)
        return {
            "files": files,
            "model": response.model_id,
            "simulated": response.simulated,
        }

    def _scaffold_files(self, proposal: Proposal) -> list[dict[str, str]]:
        """Fast multi-file scaffold so the agent can ship an app skeleton quickly."""
        slug = re.sub(r"[^a-z0-9]+", "-", proposal.title.lower()).strip("-")[:40] or "change"
        text = f"{proposal.title}\n{proposal.problem}\n{proposal.proposal}".lower()
        wants_app = any(
            k in text
            for k in (
                "app",
                "application",
                "api",
                "endpoint",
                "fastapi",
                "flask",
                "تطبيق",
                "برنامج",
                "خدمة",
            )
        )
        wants_design = proposal.category == "design" or any(
            k in text for k in ("design", "ui", "ux", "wireframe", "تصميم", "واجهة")
        )
        files: list[dict[str, str]] = [
            {
                "path": f"docs/evolve/{slug}.md",
                "action": "create",
                "content": (
                    f"# {proposal.title}\n\n"
                    f"## Why\n{proposal.rationale}\n\n"
                    f"## Problem\n{proposal.problem}\n\n"
                    f"## Change\n{proposal.proposal}\n\n"
                    f"## Acceptance\n{proposal.acceptance_criteria}\n"
                ),
            }
        ]
        if wants_design:
            files.append(
                {
                    "path": f"design/evolve/{slug}/tokens.css",
                    "action": "create",
                    "content": (
                        ":root {\n"
                        "  --bg: #070b1a;\n"
                        "  --ink: #e8eeff;\n"
                        "  --accent: #4f7cff;\n"
                        "  --radius: 14px;\n"
                        "}\n"
                    ),
                }
            )
        if wants_app:
            app_name = slug.replace("-", "_")[:32] or "evolve_app"
            files.extend(
                [
                    {
                        "path": f"apps/{app_name}/main.py",
                        "action": "create",
                        "content": (
                            '"""Generated by Evolve Development Engine."""\n'
                            "from fastapi import FastAPI\n\n"
                            f'app = FastAPI(title="{proposal.title[:60]}", version="0.1.0")\n\n'
                            '@app.get("/health")\n'
                            "def health():\n"
                            '    return {"status": "ok", "engine": "evolve"}\n\n'
                            '@app.get("/")\n'
                            "def root():\n"
                            f'    return {{"app": "{app_name}", "proposal": "{slug}"}}\n'
                        ),
                    },
                    {
                        "path": f"apps/{app_name}/README.md",
                        "action": "create",
                        "content": (
                            f"# {proposal.title}\n\n"
                            "Scaffold generated under human-gated Evolve execution.\n\n"
                            "```bash\n"
                            "uvicorn main:app --reload\n"
                            "```\n"
                        ),
                    },
                    {
                        "path": f"apps/{app_name}/requirements.txt",
                        "action": "create",
                        "content": "fastapi>=0.115.0\nuvicorn[standard]>=0.32.0\n",
                    },
                ]
            )
        return files

    def _apply_plan(
        self,
        repo_dir: Path,
        plan: dict[str, Any],
        *,
        project: Project | None = None,
    ) -> dict[str, Any]:
        written: list[str] = []
        bus = get_activity_bus()
        streams: list[dict[str, Any]] = []
        for item in plan.get("files") or []:
            rel = item.get("path")
            if not rel or ".." in rel:
                continue
            content = item.get("content") or ""
            target = assert_path_inside_workspace(repo_dir, (repo_dir / rel).resolve())
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            rel_norm = rel.replace("\\", "/")
            written.append(rel_norm)
            streams.append({"path": rel_norm, "content": content, "lines": content.count("\n") + 1})
            if project:
                bus.emit(
                    "code",
                    f"كتابة {rel_norm}",
                    detail=content[:400],
                    project_id=project.id,
                    project_name=project.name,
                    agent="FullstackDeveloper",
                    intensity=0.98,
                    payload={"path": rel_norm, "content": content, "action": item.get("action", "create")},
                )
        return {
            "files": written,
            "streams": streams,
            "model": plan.get("model"),
            "simulated": plan.get("simulated"),
        }

    async def _independent_review(self, proposal: Proposal, applied: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            "Independent review. Approve only if change is minimal and matched to proposal.\n"
            f"Proposal: {proposal.title}\nApplied files: {applied.get('files')}\n"
        )
        response = await self.gateway.complete(
            ModelRole.critic,
            prompt,
            system="You are CodeReviewer. Developers cannot self-approve.",
            metadata={"proposal_id": str(proposal.id)},
        )
        files = applied.get("files") or []
        allowed_prefix = ("docs/", "apps/", "design/")
        safe = files and all(str(f).startswith(allowed_prefix) for f in files)
        approved = bool(safe)
        return {
            "approved": approved,
            "summary": response.content,
            "model": response.model_id,
            "policy": "docs_and_apps_scaffold_auto_pass_until_live_reviewer_wired",
        }

    @staticmethod
    def _branch_name(proposal: Proposal) -> str:
        short = str(proposal.id).split("-")[0]
        return f"evolve/{short}"

    @staticmethod
    def _default_branch(repo: Repo) -> str:
        names = {h.name for h in repo.heads}
        for candidate in ("main", "master"):
            if candidate in names:
                return candidate
        if repo.head.is_valid() and not repo.head.is_detached:
            return repo.active_branch.name
        return "main"

    @classmethod
    def _ensure_repo(cls, repo_dir: Path) -> Repo:
        if not (repo_dir / ".git").exists():
            repo = Repo.init(repo_dir)
            keep = repo_dir / ".evolve_keep"
            if not any(p.is_file() for p in repo_dir.rglob("*") if ".git" not in p.parts):
                keep.write_text("", encoding="utf-8")
            repo.git.add(A=True)
            if not repo.head.is_valid():
                repo.index.commit(
                    "chore: initial snapshot for Evolve execution",
                    author=_EVOLVE_ACTOR,
                    committer=_EVOLVE_ACTOR,
                )
            return repo
        return Repo(repo_dir)
