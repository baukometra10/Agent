"""Phase 9 — Design & UI Engineering Engine.

Produces design-system tokens, UX notes, and HTML wireframe drafts.
Never ships UI to production without human-gated proposal execution.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.activity import get_activity_bus
from app.db.models import AgentDepartment, AgentTask, DecisionRecord, Project, TaskStatus
from app.gateway.router import ModelRole, get_model_gateway
from app.intelligence.visual_intelligence import analyze_visual
from app.proposals.service import ProposalService
from app.security.isolation import assert_path_inside_workspace


class DesignEngine:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.gateway = get_model_gateway()

    async def run(
        self,
        project: Project,
        *,
        brief: str = "",
        draft_proposal: bool = True,
    ) -> dict[str, Any]:
        bus = get_activity_bus()
        bus.emit(
            "think",
            "محرك التصميم يبدأ",
            detail=brief or project.name,
            project_id=project.id,
            project_name=project.name,
            agent="UIDesigner",
            intensity=0.88,
        )

        workspace = Path(project.workspace_path)
        repo = assert_path_inside_workspace(workspace, workspace / "repo")
        if not repo.exists():
            repo = workspace

        visual = analyze_visual(repo)
        surfaces = visual.to_dict().get("ui_surfaces") or []
        bus.emit(
            "tool",
            "مسح السطح البصري",
            detail=f"surfaces={len(surfaces)} · signals={len(visual.design_signals)}",
            project_id=project.id,
            project_name=project.name,
            agent="UXResearcher",
            intensity=0.7,
            payload=visual.to_dict(),
        )

        task = AgentTask(
            project_id=project.id,
            department=AgentDepartment.design,
            agent_name="UIDesigner",
            objective=f"Design pack: {brief or project.name}",
            status=TaskStatus.running,
            started_at=datetime.now(timezone.utc),
            input_payload={"brief": brief},
        )
        self.session.add(task)
        await self.session.flush()

        pack = await self._compose_pack(project, brief, visual)
        written = self._write_pack(repo, pack)

        bus.emit(
            "code",
            "كتابة حزمة التصميم",
            detail=", ".join(written[:4]),
            project_id=project.id,
            project_name=project.name,
            agent="DesignSystemAgent",
            intensity=0.95,
            payload={"files": written, "tokens": pack.get("tokens")},
        )

        proposal = None
        if draft_proposal:
            proposals = ProposalService(self.session)
            proposal = await proposals.create_from_user_request(
                project.id,
                title=f"Design system refresh — {project.name}",
                user_request=brief or "Improve UI consistency and accessibility",
                rationale="Design Engine produced tokens + wireframe for human review before merge.",
                proposal_text=(
                    "Apply design tokens and wireframe under design/evolve/. "
                    "Frontend developers implement against the token contract."
                ),
                affected_parts=written,
                category="design",
                priority=65,
            )

        task.status = TaskStatus.succeeded
        task.output_payload = {"files": written, "pack": {"title": pack["title"]}}
        task.finished_at = datetime.now(timezone.utc)
        self.session.add(
            DecisionRecord(
                project_id=project.id,
                decision="Design pack drafted",
                rationale="Human must approve before treating design as source of truth in product UI",
                made_by="DesignEngine",
                alternatives=["revise_brief", "reject"],
                evidence={"files": written, "proposal_id": str(proposal.id) if proposal else None},
                related_proposal_id=proposal.id if proposal else None,
            )
        )
        await self.session.commit()

        bus.emit(
            "decision",
            "حزمة تصميم جاهزة للمراجعة البشرية",
            detail=pack["title"],
            project_id=project.id,
            project_name=project.name,
            agent="UIDesigner",
            intensity=0.45,
        )
        bus.set_idle(hint=f"تصميم بانتظار مراجعة: {pack['title']}")

        return {
            "status": "drafted",
            "files": written,
            "pack": pack,
            "proposal_id": str(proposal.id) if proposal else None,
            "visual": visual.to_dict() if hasattr(visual, "to_dict") else {},
        }

    async def _compose_pack(self, project: Project, brief: str, visual: Any) -> dict[str, Any]:
        visual_dict = visual.to_dict() if hasattr(visual, "to_dict") else {}
        prompt = (
            "Produce a concise UI design brief for Evolve Design Engine.\n"
            f"Project: {project.name}\nBrief: {brief}\nVisual signals: {visual_dict}\n"
            "Focus on hierarchy, accessibility, and tokenizable colors."
        )
        response = await self.gateway.complete(
            ModelRole.multimodal,
            prompt,
            system="You are UIDesigner + DesignSystemAgent. Prefer clear token contracts.",
            metadata={"agent": "UIDesigner", "project_id": str(project.id)},
        )
        slug = re.sub(r"[^a-z0-9]+", "-", project.slug.lower()).strip("-")[:40] or "ui"
        tokens = {
            "--bg": "#070b1a",
            "--ink": "#e8eeff",
            "--muted": "#8b9bc7",
            "--accent": "#4f7cff",
            "--accent-2": "#7b5cff",
            "--success": "#3ddc97",
            "--danger": "#ff5c7a",
            "--radius": "14px",
            "--font-display": "Cairo, sans-serif",
            "--font-body": "IBM Plex Sans Arabic, sans-serif",
        }
        css = ":root {\n" + "\n".join(f"  {k}: {v};" for k, v in tokens.items()) + "\n}\n"
        wireframe = f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8" />
  <title>{project.name} — Evolve Wireframe</title>
  <style>
{css}
  body {{ margin:0; font-family: var(--font-body); background: var(--bg); color: var(--ink); }}
  header {{ padding: 1.25rem 1.5rem; border-bottom: 1px solid rgba(120,140,200,.2); }}
  h1 {{ font-family: var(--font-display); margin: 0 0 .35rem; }}
  main {{ display:grid; gap:1rem; padding:1.25rem; grid-template-columns: 1.2fr .8fr; }}
  .card {{ background: rgba(18,28,58,.72); border:1px solid rgba(120,140,200,.16); border-radius: var(--radius); padding:1rem; }}
  .cta {{ display:inline-block; margin-top:.75rem; padding:.55rem 1rem; border-radius:999px; background:var(--accent); color:white; text-decoration:none; }}
  </style>
</head>
<body>
  <header>
    <h1>{project.name}</h1>
    <p style="color:var(--muted);margin:0">Wireframe generated by Evolve Design Engine</p>
  </header>
  <main>
    <section class="card">
      <h2>المسار الرئيسي</h2>
      <p>{brief or "Hero + primary action. Keep first viewport focused."}</p>
      <a class="cta" href="#">إجراء أساسي</a>
    </section>
    <aside class="card">
      <h2>ملاحظات UX</h2>
      <p style="color:var(--muted)">{response.content[:500]}</p>
    </aside>
  </main>
</body>
</html>
"""
        spec_md = (
            f"# Design Pack — {project.name}\n\n"
            f"## Brief\n{brief or 'Improve consistency and accessibility'}\n\n"
            f"## Model notes\n{response.content[:1500]}\n\n"
            f"## Tokens\n```css\n{css}```\n\n"
            f"## Visual intelligence\n```json\n{visual_dict}\n```\n"
        )
        return {
            "title": f"Design pack — {project.name}",
            "slug": slug,
            "tokens": tokens,
            "css": css,
            "wireframe_html": wireframe,
            "spec_md": spec_md,
            "model": response.model_id,
            "simulated": response.simulated,
        }

    def _write_pack(self, repo: Path, pack: dict[str, Any]) -> list[str]:
        base = repo / "design" / "evolve" / pack["slug"]
        base.mkdir(parents=True, exist_ok=True)
        files = {
            "DESIGN.md": pack["spec_md"],
            "tokens.css": pack["css"],
            "wireframe.html": pack["wireframe_html"],
        }
        written: list[str] = []
        for name, content in files.items():
            path = base / name
            assert_path_inside_workspace(repo, path.resolve())
            path.write_text(content, encoding="utf-8")
            written.append(str(path.relative_to(repo)).replace("\\", "/"))
        return written
