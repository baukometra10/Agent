"""Phase 11 — Deployment Engine.

Plans and records human-gated deploys. Never pushes to production unless
explicit confirm is called (and even then defaults to dry-run/simulated).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.activity import get_activity_bus
from app.autonomy import autonomy_of
from app.config import get_settings
from app.db.models import AgentDepartment, AgentTask, DecisionRecord, Project, TaskStatus
from app.deployment.adapters import get_deploy_adapter, list_deploy_adapters
from app.deployment.adapters.base import DeployRequest
from app.gateway.router import ModelRole, get_model_gateway
from app.proposals.service import ProposalService
from app.security.isolation import assert_path_inside_workspace


class DeploymentEngine:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.gateway = get_model_gateway()

    async def plan(
        self,
        project: Project,
        *,
        target: str = "staging",
        draft_proposal: bool = True,
    ) -> dict[str, Any]:
        bus = get_activity_bus()
        bus.emit(
            "think",
            "محرك النشر يضع خطة",
            detail=f"target={target}",
            project_id=project.id,
            project_name=project.name,
            agent="DevOpsEngineer",
            intensity=0.85,
        )

        workspace = Path(project.workspace_path)
        repo = assert_path_inside_workspace(workspace, workspace / "repo")
        root = repo if repo.exists() else workspace

        has_docker = (root / "Dockerfile").exists() or (root / "docker-compose.yml").exists()
        has_ci = any((root / p).exists() for p in (".github/workflows", ".gitlab-ci.yml", "azure-pipelines.yml"))

        response = await self.gateway.complete(
            ModelRole.coding,
            (
                f"Create a cautious deploy plan for {project.name} to {target}.\n"
                f"Docker present={has_docker}, CI present={has_ci}.\n"
                "Never assume production credentials exist."
            ),
            system="You are DeploymentAgent. Prefer dry-run and rollback notes.",
            metadata={"agent": "DeploymentAgent", "project_id": str(project.id)},
        )

        plan = {
            "target": target,
            "mode": "dry_run",
            "checks": {
                "dockerfile": has_docker,
                "ci": has_ci,
                "auto_deploy_policy": autonomy_of(
                    project.settings if isinstance(project.settings, dict) else {}
                ).get("auto_deploy", False),
            },
            "steps": [
                "Verify tests/quality gate",
                "Build artifact (container or package)",
                f"Deploy to {target} (human confirm required)",
                "Smoke health check",
                "Record decision + notify owner",
            ],
            "rollback": "Redeploy previous artifact tag; keep DB migrations expandable-only.",
            "model_notes": response.content[:1500],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        out_dir = root / "docs" / "evolve" / "deploy"
        out_dir.mkdir(parents=True, exist_ok=True)
        plan_path = out_dir / f"PLAN_{target}.json"
        plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
        md_path = out_dir / f"PLAN_{target}.md"
        md_path.write_text(
            (
                f"# Deploy plan — {project.name} → {target}\n\n"
                f"Mode: **dry_run** (human gate)\n\n"
                "## Steps\n"
                + "\n".join(f"- {s}" for s in plan["steps"])
                + f"\n\n## Rollback\n{plan['rollback']}\n\n## Notes\n{plan['model_notes']}\n"
            ),
            encoding="utf-8",
        )
        rel_json = str(plan_path.relative_to(root)).replace("\\", "/")
        rel_md = str(md_path.relative_to(root)).replace("\\", "/")

        bus.emit(
            "code",
            "كتابة خطة النشر",
            detail=rel_md,
            project_id=project.id,
            project_name=project.name,
            agent="DeploymentAgent",
            intensity=0.9,
            payload={"path": rel_md, "content": md_path.read_text(encoding="utf-8")[:2000]},
        )

        task = AgentTask(
            project_id=project.id,
            department=AgentDepartment.operations,
            agent_name="DeploymentAgent",
            objective=f"Plan deploy to {target}",
            status=TaskStatus.succeeded,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            output_payload={"plan": plan, "files": [rel_json, rel_md]},
        )
        self.session.add(task)

        proposal = None
        if draft_proposal:
            proposal = await ProposalService(self.session).create_from_user_request(
                project.id,
                title=f"Deploy {project.name} → {target}",
                user_request=f"Prepare and await approval to deploy to {target}",
                rationale="Deployment remains human-gated; plan is dry-run until confirm.",
                proposal_text=f"Follow {rel_md}. Confirm via deploy confirm API after approval.",
                affected_parts=[rel_md, rel_json],
                category="deployment",
                priority=75,
            )

        self.session.add(
            DecisionRecord(
                project_id=project.id,
                decision=f"Deploy plan drafted for {target}",
                rationale="Awaiting human approve + explicit confirm",
                made_by="DeploymentEngine",
                alternatives=["abort", "change_target"],
                evidence={"files": [rel_json, rel_md]},
                related_proposal_id=proposal.id if proposal else None,
            )
        )
        await self.session.commit()
        bus.set_idle(hint=f"نشر {target} بانتظار تأكيد بشري")

        return {
            "status": "planned",
            "target": target,
            "plan": plan,
            "files": [rel_json, rel_md],
            "proposal_id": str(proposal.id) if proposal else None,
            "confirm_required": True,
        }

    async def confirm(
        self,
        project: Project,
        *,
        target: str = "staging",
        proposal_id: UUID | None = None,
        force_simulate: bool = True,
        provider: str | None = None,
    ) -> dict[str, Any]:
        """Human-gated confirm. Defaults to simulated deploy via configured adapter."""
        settings = get_settings()
        provider_name = provider or settings.deploy_provider
        adapter = get_deploy_adapter(provider_name)

        bus = get_activity_bus()
        bus.emit(
            "decision",
            "تأكيد نشر بشري",
            detail=f"provider={adapter.name} simulate={force_simulate} target={target}",
            project_id=project.id,
            project_name=project.name,
            agent="DeploymentAgent",
            intensity=0.75,
        )

        workspace = Path(project.workspace_path)
        repo = assert_path_inside_workspace(workspace, workspace / "repo")
        root = repo if repo.exists() else workspace
        out_dir = root / "docs" / "evolve" / "deploy"
        out_dir.mkdir(parents=True, exist_ok=True)

        result = await adapter.deploy(
            DeployRequest(
                project_name=project.name,
                project_slug=project.slug,
                workspace_path=str(workspace),
                target=target,
                force_simulate=force_simulate,
                metadata={"proposal_id": str(proposal_id) if proposal_id else None},
            )
        )

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        receipt = {
            **result.to_dict(),
            "target": target,
            "at": datetime.now(timezone.utc).isoformat(),
            "proposal_id": str(proposal_id) if proposal_id else None,
            "adapters_available": list_deploy_adapters(),
        }
        path = out_dir / f"RECEIPT_{target}_{stamp}.json"
        path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
        rel = str(path.relative_to(root)).replace("\\", "/")

        self.session.add(
            DecisionRecord(
                project_id=project.id,
                decision=f"Deploy confirm → {receipt['status']}",
                rationale=f"Human confirmed via adapter={adapter.name}",
                made_by="human",
                evidence=receipt,
                related_proposal_id=proposal_id,
            )
        )
        project.last_evolution_at = datetime.now(timezone.utc)
        await self.session.commit()
        bus.set_idle(hint=f"نشر {target}: {receipt['status']}")

        return {"status": receipt["status"], "receipt": receipt, "file": rel, "provider": adapter.name}
