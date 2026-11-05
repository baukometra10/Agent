"""Phase 10 foundation — Testing, Security & Quality Engine.

Produces a review pack (security + QA + performance heuristics).
Does not auto-remediate; drafts findings/proposals for humans.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.activity import get_activity_bus
from app.db.models import (
    AgentDepartment,
    AgentTask,
    AnalysisFinding,
    FindingKind,
    FindingSeverity,
    FindingStatus,
    Project,
    TaskStatus,
)
from app.gateway.router import ModelRole, get_model_gateway
from app.intelligence.scanner import scan_workspace
from app.proposals.service import ProposalService
from app.security.isolation import assert_path_inside_workspace


class QualityEngine:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.gateway = get_model_gateway()

    async def run(
        self,
        project: Project,
        *,
        focus: str = "full",
        draft_proposal: bool = True,
    ) -> dict[str, Any]:
        bus = get_activity_bus()
        bus.emit(
            "think",
            "محرك الجودة والأمن يبدأ",
            detail=focus,
            project_id=project.id,
            project_name=project.name,
            agent="QAEngineer",
            intensity=0.86,
        )

        workspace = Path(project.workspace_path)
        repo = assert_path_inside_workspace(workspace, workspace / "repo")
        target = repo if repo.exists() else workspace
        scan = scan_workspace(target)

        bus.emit(
            "neural",
            "تفعيل SecurityAuditor + TestEngineer",
            detail=f"files≈{(scan.file_stats or {}).get('total_files', 'n/a')}",
            project_id=project.id,
            project_name=project.name,
            agent="SecurityAuditor",
            intensity=0.9,
        )

        task = AgentTask(
            project_id=project.id,
            department=AgentDepartment.quality,
            agent_name="QAEngineer",
            objective=f"Quality/security pack ({focus})",
            status=TaskStatus.running,
            started_at=datetime.now(timezone.utc),
            input_payload={"focus": focus},
        )
        self.session.add(task)
        await self.session.flush()

        checks = self._heuristic_checks(target, scan)
        critique = await self.gateway.complete(
            ModelRole.critic,
            (
                f"Independent quality/security review for {project.name}.\n"
                f"Focus={focus}\nChecks={checks}\n"
                "List top risks and test gaps. Do not approve remediations."
            ),
            system="You are IndependentCritic + SecurityAuditor. Be strict.",
            metadata={"agent": "IndependentCritic", "project_id": str(project.id)},
        )

        findings = []
        for item in checks:
            finding = AnalysisFinding(
                project_id=project.id,
                category=item["category"],
                kind=FindingKind(item["kind"]),
                severity=FindingSeverity(item["severity"]),
                status=FindingStatus.open,
                title=item["title"],
                description=item["description"],
                recommendation=item["recommendation"],
                confidence=item.get("confidence", 0.7),
                affected_parts=item.get("affected_parts") or [],
                evidence=item.get("evidence") or {},
                source_agent=item.get("agent", "QualityEngine"),
                fingerprint=hashlib.sha1(
                    f"quality:{project.id}:{item['title']}".encode()
                ).hexdigest()[:40],
            )
            self.session.add(finding)
            findings.append(item)

        report_path = self._write_report(target, project, checks, critique.content)

        proposal = None
        if draft_proposal and any(c["severity"] in {"high", "critical"} for c in checks):
            top = next(c for c in checks if c["severity"] in {"high", "critical"})
            proposal = await ProposalService(self.session).create_from_user_request(
                project.id,
                title=f"Remediate: {top['title']}",
                user_request=top["description"],
                rationale=top["recommendation"],
                proposal_text=top["recommendation"],
                affected_parts=top.get("affected_parts") or [],
                category="security" if top["category"] == "security" else "quality",
                priority=80,
            )

        task.status = TaskStatus.succeeded
        task.output_payload = {
            "findings": len(findings),
            "report": report_path,
            "critic": critique.model_id,
        }
        task.finished_at = datetime.now(timezone.utc)
        await self.session.commit()

        bus.emit(
            "decision",
            "تقرير جودة/أمن جاهز",
            detail=f"{len(findings)} finding(s)",
            project_id=project.id,
            project_name=project.name,
            agent="CodeReviewer",
            intensity=0.5,
            payload={"report": report_path},
        )
        bus.set_idle(hint=f"جودة: {len(findings)} ملاحظات")

        return {
            "status": "completed",
            "findings": findings,
            "report": report_path,
            "critic": critique.content,
            "proposal_id": str(proposal.id) if proposal else None,
        }

    def _heuristic_checks(self, root: Path, scan: Any) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = []
        text_blobs: list[str] = []
        for path in list(root.rglob("*"))[:200]:
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".py", ".ts", ".tsx", ".js", ".env", ".yml", ".yaml"}:
                continue
            if any(p in path.parts for p in {".git", "node_modules", ".venv"}):
                continue
            try:
                text_blobs.append(path.read_text(encoding="utf-8", errors="ignore")[:4000])
            except OSError:
                continue
        joined = "\n".join(text_blobs).lower()

        if "password" in joined and ("=" in joined or ":" in joined):
            checks.append(
                {
                    "category": "security",
                    "kind": "risk",
                    "severity": "high",
                    "title": "Possible hardcoded secret/password pattern",
                    "description": "Scan detected password-like assignments in source/config samples.",
                    "recommendation": "Move secrets to env/Key Vault; rotate any exposed credentials.",
                    "agent": "VulnerabilityAnalyst",
                    "affected_parts": ["config"],
                    "confidence": 0.62,
                }
            )
        if "eval(" in joined or "dangerouslysetinnerhtml" in joined:
            checks.append(
                {
                    "category": "security",
                    "kind": "risk",
                    "severity": "high",
                    "title": "Dangerous dynamic execution / HTML injection API",
                    "description": "Found eval( or dangerouslySetInnerHTML usage patterns.",
                    "recommendation": "Replace with safe APIs; sanitize any rich HTML inputs.",
                    "agent": "SecurityAuditor",
                    "confidence": 0.7,
                }
            )
        has_tests = any((root / d).exists() for d in ("tests", "test", "__tests__"))
        if not has_tests:
            checks.append(
                {
                    "category": "quality",
                    "kind": "opportunity",
                    "severity": "medium",
                    "title": "No test directory detected",
                    "description": "Repository sample lacks tests/ or __tests__.",
                    "recommendation": "Add baseline unit/integration tests for critical paths.",
                    "agent": "TestEngineer",
                    "confidence": 0.75,
                }
            )
        frameworks = getattr(scan, "frameworks", None) or []
        if not checks:
            checks.append(
                {
                    "category": "quality",
                    "kind": "opportunity",
                    "severity": "low",
                    "title": "Baseline quality sweep clean",
                    "description": f"No high-severity heuristic hits. Frameworks={frameworks}",
                    "recommendation": "Keep CI green; expand coverage for new features.",
                    "agent": "QAEngineer",
                    "confidence": 0.55,
                }
            )
        return checks

    def _write_report(
        self, root: Path, project: Project, checks: list[dict[str, Any]], critique: str
    ) -> str:
        out_dir = root / "docs" / "evolve" / "quality"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "QUALITY_REPORT.md"
        lines = [
            f"# Quality & Security Report — {project.name}",
            "",
            "## Critic",
            critique[:2000],
            "",
            "## Findings",
        ]
        for c in checks:
            lines.append(
                f"- **{c['severity'].upper()}** [{c['category']}] {c['title']}: {c['recommendation']}"
            )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        try:
            return str(path.relative_to(root)).replace("\\", "/")
        except ValueError:
            return str(path)
