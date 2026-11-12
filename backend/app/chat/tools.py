"""Read-oriented agent tools (Cursor-like). Writes go through proposals, not direct mutate."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeNode, Project, ProposalStatus
from app.knowledge.graph import KnowledgeGraphService
from app.planning.store import PlanningStore
from app.proposals.service import ProposalService
from app.security.isolation import assert_path_inside_workspace


class ProjectToolbelt:
    def __init__(self, session: AsyncSession, project: Project) -> None:
        self.session = session
        self.project = project
        self.workspace = Path(project.workspace_path)
        self.repo = self.workspace / "repo"
        self.root = self.repo if self.repo.exists() else self.workspace

    def list_files(self, relative: str = ".", limit: int = 80) -> dict[str, Any]:
        base = assert_path_inside_workspace(self.workspace, (self.root / relative).resolve())
        if not base.exists():
            return {"error": "path not found", "path": relative}
        if base.is_file():
            return {"files": [relative], "count": 1}
        files = []
        for path in base.rglob("*"):
            if path.is_file():
                try:
                    rel = str(path.relative_to(self.root)).replace("\\", "/")
                except ValueError:
                    continue
                if any(
                    p in path.parts
                    for p in {".git", "node_modules", ".venv", "__pycache__", ".pytest_cache"}
                ):
                    continue
                files.append(rel)
                if len(files) >= limit:
                    break
        return {"files": files, "count": len(files), "root": str(self.root)}

    def workspace_snapshot(self, *, file_limit: int = 80) -> dict[str, Any]:
        """Shallow + key-file view of the bound folder (local IDE truth)."""
        root = self.root
        if not root.exists():
            return {
                "error": "workspace_missing",
                "workspace_path": str(self.workspace),
                "root": str(root),
            }
        skip = {".git", "node_modules", ".venv", "__pycache__", ".pytest_cache"}
        top_dirs: list[str] = []
        top_files: list[str] = []
        try:
            children = sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError as exc:
            return {
                "error": str(exc),
                "workspace_path": str(self.workspace),
                "root": str(root),
            }
        for child in children:
            if child.name in skip or child.name.startswith(".venv"):
                continue
            if child.is_dir():
                if child.name.startswith(".") and child.name not in {".github", ".spixa"}:
                    continue
                top_dirs.append(child.name)
            elif child.is_file():
                top_files.append(child.name)

        key_names = (
            "README.md",
            "VISION.md",
            "package.json",
            "pyproject.toml",
            "requirements.txt",
            "docker-compose.yml",
            "Dockerfile",
            "main.py",
            "index.html",
            "app.js",
            "styles.css",
        )
        key_files: dict[str, str] = {}
        for name in key_names:
            path = root / name
            if path.is_file():
                try:
                    key_files[name] = path.read_text(encoding="utf-8", errors="ignore")[:2500]
                except OSError:
                    continue

        listed = self.list_files(".", limit=file_limit)
        return {
            "workspace_path": str(self.workspace),
            "root": str(root),
            "project_name": self.project.name,
            "top_dirs": top_dirs[:40],
            "top_files": top_files[:40],
            "files": listed.get("files") or [],
            "file_count_sample": listed.get("count") or 0,
            "key_files": key_files,
        }

    def read_file(self, relative: str, max_chars: int = 12000) -> dict[str, Any]:
        target = assert_path_inside_workspace(self.workspace, (self.root / relative).resolve())
        if not target.exists() or not target.is_file():
            return {"error": "file not found", "path": relative}
        text = target.read_text(encoding="utf-8", errors="ignore")
        truncated = len(text) > max_chars
        return {
            "path": relative,
            "content": text[:max_chars],
            "truncated": truncated,
            "chars": len(text),
        }

    async def search_knowledge(self, query: str, limit: int = 12) -> dict[str, Any]:
        nodes = await KnowledgeGraphService(self.session).list_nodes(
            self.project.id, include_stale=False, limit=200
        )
        q = query.lower()
        hits = []
        for node in nodes:
            blob = f"{node.title} {node.content} {node.category}".lower()
            if q in blob:
                hits.append(
                    {
                        "kind": node.kind.value,
                        "title": node.title,
                        "category": node.category,
                        "confidence": node.confidence,
                        "content": node.content[:400],
                    }
                )
            if len(hits) >= limit:
                break
        return {"query": query, "hits": hits, "count": len(hits)}

    async def get_roadmap_summary(self) -> dict[str, Any]:
        roadmap = await PlanningStore(self.session).get_active_roadmap(self.project.id)
        if not roadmap:
            return {"roadmap": None}
        items = sorted(roadmap.items or [], key=lambda i: i.sort_order)[:15]
        return {
            "roadmap": {
                "version": roadmap.version,
                "title": roadmap.title,
                "vision": roadmap.vision,
                "items": [
                    {
                        "title": i.title,
                        "priority": i.priority,
                        "category": i.category,
                        "status": i.status.value,
                    }
                    for i in items
                ],
            }
        }

    async def draft_change_proposal(
        self,
        *,
        title: str,
        user_request: str,
        plan: str,
        rationale: str,
        affected_parts: list[str] | None = None,
    ) -> dict[str, Any]:
        proposal = await ProposalService(self.session).create_from_user_request(
            self.project.id,
            title=title,
            user_request=user_request,
            rationale=rationale,
            proposal_text=plan,
            affected_parts=affected_parts or [],
        )
        await self.session.commit()
        return {
            "proposal_id": str(proposal.id),
            "status": proposal.status.value,
            "title": proposal.title,
            "note": "Awaiting human approval before any code execution (Cursor-stronger: gated apply).",
        }
