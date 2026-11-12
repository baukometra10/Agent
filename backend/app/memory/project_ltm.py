"""Per-project long-term memory — hard isolation, every utterance retained.

Doctrine:
- Each project has its own transcript + durable notes under its workspace.
- Never read/write another project's memory.
- Agent must always know workspace + isolation namespace ("where it works").
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import AgentSession, KnowledgeKind, KnowledgeNode, Project
from app.knowledge.memory import MEMORY_LAYERS
from app.security.isolation import assert_path_inside_workspace

REMEMBER_HINT = re.compile(
    r"("
    r"\b(remember|always|must|never forget|goal|ziel|target|destination|roadmap)\b|"
    r"احفظ|تذكّر|تذكر|دائمًا|دائما|لا تنسَ|لا تنس|"
    r"أريد أن|اريد ان|هدفي|الهدف|أوصل إلى|اوصل الى|نصل إلى|نصل الى|"
    r"\b(ich will|ich möchte|ziel ist|wir sollen)\b"
    r")",
    re.IGNORECASE,
)


class ProjectLongTermMemory:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _project(self, project_id: UUID) -> Project:
        project = await self.session.get(Project, project_id)
        if not project:
            raise ValueError("Project not found")
        return project

    def _memory_dir(self, project: Project) -> Path:
        workspace = Path(project.workspace_path)
        mem = workspace / "memory"
        # Isolation: memory must live inside the project workspace only
        assert_path_inside_workspace(workspace, mem)
        mem.mkdir(parents=True, exist_ok=True)
        return mem

    def _transcript_path(self, project: Project) -> Path:
        return self._memory_dir(project) / "transcript.jsonl"

    def _append_transcript(
        self,
        project: Project,
        *,
        role: str,
        content: str,
        session_id: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        row = {
            "at": datetime.now(timezone.utc).isoformat(),
            "project_id": str(project.id),
            "project_slug": project.slug,
            "isolation_namespace": project.isolation_namespace,
            "workspace_path": project.workspace_path,
            "session_id": session_id,
            "role": role,
            "content": content,
            "meta": meta or {},
        }
        path = self._transcript_path(project)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    async def remember_utterance(
        self,
        project_id: UUID,
        *,
        role: str,
        content: str,
        session_id: UUID | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist every word into project-isolated long-term memory."""
        project = await self._project(project_id)
        text = (content or "").strip()
        if not text:
            return {"stored": False, "reason": "empty"}
        try:
            from app.memory.pollution import is_pollution_text, strip_pollution

            text = strip_pollution(text)
            if not text or is_pollution_text(text):
                return {"stored": False, "reason": "prompt_pollution"}
        except Exception:  # noqa: BLE001
            pass

        self._append_transcript(
            project,
            role=role,
            content=text,
            session_id=str(session_id) if session_id else None,
            meta=meta,
        )

        # Durable knowledge atom (conversation layer) — always project-scoped
        layer = "conversation" if "conversation" in MEMORY_LAYERS else "execution"
        node = KnowledgeNode(
            project_id=project.id,
            memory_layer=layer,
            category="utterance",
            kind=KnowledgeKind.fact if role == "user" else KnowledgeKind.inference,
            title=f"{role}: {text[:80]}",
            content=text,
            confidence=0.95 if role == "user" else 0.7,
            source_type="user" if role == "user" else "agent",
            source_path=f"session:{session_id}" if session_id else "ltm",
            evidence={
                "isolation_namespace": project.isolation_namespace,
                "workspace_path": project.workspace_path,
                **(meta or {}),
            },
        )
        self.session.add(node)

        durable = None
        if role == "user" and REMEMBER_HINT.search(text):
            durable = KnowledgeNode(
                project_id=project.id,
                memory_layer="decision",
                category="standing_instruction",
                kind=KnowledgeKind.fact,
                title="Standing instruction from user",
                content=text,
                confidence=0.99,
                source_type="user",
                source_path=f"session:{session_id}" if session_id else "ltm",
                evidence={"standing": True, "isolation_namespace": project.isolation_namespace},
            )
            self.session.add(durable)

        await self.session.flush()

        # Auto-index into durable vector memory (Chroma-like) for semantic recall
        embed_info: dict[str, Any] | None = None
        try:
            from app.memory.embeddings_store import ProjectEmbeddingsStore

            embed_info = await ProjectEmbeddingsStore(self.session).upsert(
                project_id,
                text=text,
                source=f"ltm_{role}",
                meta={"session_id": str(session_id) if session_id else None},
            )
        except Exception:  # noqa: BLE001 — never fail the primary memory write
            embed_info = None

        return {
            "stored": True,
            "utterance_node_id": str(node.id),
            "standing_instruction_id": str(durable.id) if durable else None,
            "workspace_path": project.workspace_path,
            "isolation_namespace": project.isolation_namespace,
            "embedding": embed_info,
        }

    def read_transcript(self, project: Project, *, limit: int = 200) -> list[dict[str, Any]]:
        path = self._transcript_path(project)
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        rows: list[dict[str, Any]] = []
        for line in lines[-limit:]:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Hard guard: drop any corrupted cross-project line
            if row.get("project_id") and row.get("project_id") != str(project.id):
                continue
            rows.append(row)
        return rows

    async def session_history(
        self,
        project_id: UUID,
        session_id: UUID | None,
        *,
        limit: int = 100,
    ) -> list[dict[str, str]]:
        if not session_id:
            return []
        result = await self.session.execute(
            select(AgentSession)
            .where(AgentSession.id == session_id, AgentSession.project_id == project_id)
            .options(selectinload(AgentSession.messages))
        )
        sess = result.scalar_one_or_none()
        if not sess:
            return []
        msgs = sorted(sess.messages, key=lambda m: m.created_at)[-limit:]
        return [{"role": m.role, "content": m.content} for m in msgs]

    async def recall(
        self,
        project_id: UUID,
        *,
        session_id: UUID | None = None,
        transcript_limit: int = 80,
        instruction_limit: int = 20,
    ) -> dict[str, Any]:
        """Bundle everything the agent needs: where it works + every retained word."""
        project = await self._project(project_id)
        transcript = self.read_transcript(project, limit=transcript_limit)
        history = await self.session_history(project_id, session_id, limit=transcript_limit)

        standing = await self.session.execute(
            select(KnowledgeNode)
            .where(
                KnowledgeNode.project_id == project_id,
                KnowledgeNode.category == "standing_instruction",
            )
            .order_by(KnowledgeNode.created_at.desc())
            .limit(instruction_limit)
        )
        instructions = [
            {"id": str(n.id), "content": n.content, "created_at": n.created_at.isoformat() if n.created_at else None}
            for n in standing.scalars().all()
        ]

        semantic: dict[str, Any] = {"hits": [], "indexed": 0}
        try:
            from app.memory.embeddings_store import ProjectEmbeddingsStore

            # Query from latest user turn or standing instructions
            seed = ""
            for row in reversed(transcript):
                if row.get("role") == "user" and row.get("content"):
                    seed = str(row["content"])
                    break
            if not seed and instructions:
                seed = str(instructions[0].get("content") or "")
            if seed:
                semantic = await ProjectEmbeddingsStore(self.session).search(
                    project_id, query=seed[:500], top_k=6
                )
        except Exception:  # noqa: BLE001
            semantic = {"hits": [], "indexed": 0, "error": "semantic_unavailable"}

        return {
            "binding": {
                "project_id": str(project.id),
                "project_slug": project.slug,
                "project_name": project.name,
                "workspace_path": project.workspace_path,
                "isolation_namespace": project.isolation_namespace,
                "rule": "Never mix memory, workspace, or decisions with any other project.",
            },
            "standing_instructions": instructions,
            "transcript": transcript,
            "session_history": history,
            "semantic": semantic,
            "counts": {
                "transcript": len(transcript),
                "session_history": len(history),
                "standing_instructions": len(instructions),
                "semantic_hits": len(semantic.get("hits") or []),
            },
        }
