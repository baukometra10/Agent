"""Project-isolated embeddings store — never cross workspace boundaries.

Uses a deterministic local hasher as the owned embeddings student by default
(no network). Optional gateway teacher/student vectors can be attached later.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Project
from app.security.isolation import assert_path_inside_workspace

DIM = 128
TOKEN_RE = re.compile(r"[A-Za-z0-9_\u0600-\u06FF]{2,}")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "")]


def local_embed(text: str, *, dim: int = DIM) -> list[float]:
    """Owned local embedding: hashed bag-of-words → unit vector."""
    vec = [0.0] * dim
    toks = _tokenize(text)
    if not toks:
        return vec
    for tok in toks:
        h = int(hashlib.sha256(tok.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 8) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    return sum(a[i] * b[i] for i in range(n))


class ProjectEmbeddingsStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _project(self, project_id: UUID) -> Project:
        project = await self.session.scalar(select(Project).where(Project.id == project_id))
        if not project:
            raise ValueError("project not found")
        return project

    def _store_dir(self, project: Project) -> Path:
        workspace = Path(project.workspace_path)
        root = workspace / "memory" / "embeddings"
        assert_path_inside_workspace(workspace, root)
        root.mkdir(parents=True, exist_ok=True)
        marker = root / ".evolve-embeddings"
        if not marker.exists():
            marker.write_text(
                json.dumps(
                    {
                        "project_id": str(project.id),
                        "isolation_namespace": project.isolation_namespace,
                        "doctrine": "hard isolation — never share vectors across projects",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        return root

    def _index_path(self, project: Project) -> Path:
        return self._store_dir(project) / "index.jsonl"

    async def upsert(
        self,
        project_id: UUID,
        *,
        text: str,
        source: str = "manual",
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        project = await self._project(project_id)
        vec = local_embed(text)
        row = {
            "id": str(uuid4()),
            "project_id": str(project.id),
            "namespace": project.isolation_namespace,
            "text": text[:4000],
            "source": source,
            "meta": meta or {},
            "vector": vec,
            "dims": len(vec),
            "method": "owned_local_hash",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        path = self._index_path(project)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return {
            "ok": True,
            "id": row["id"],
            "dims": row["dims"],
            "method": row["method"],
            "path": str(path),
            "isolation_namespace": project.isolation_namespace,
        }

    async def search(
        self,
        project_id: UUID,
        *,
        query: str,
        top_k: int = 5,
    ) -> dict[str, Any]:
        project = await self._project(project_id)
        path = self._index_path(project)
        qv = local_embed(query)
        hits: list[dict[str, Any]] = []
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # Hard isolation guard
                if str(row.get("project_id")) != str(project.id):
                    continue
                if row.get("namespace") and row.get("namespace") != project.isolation_namespace:
                    continue
                score = cosine(qv, list(row.get("vector") or []))
                hits.append(
                    {
                        "id": row.get("id"),
                        "score": round(score, 4),
                        "text": row.get("text"),
                        "source": row.get("source"),
                        "meta": row.get("meta") or {},
                    }
                )
        hits.sort(key=lambda r: float(r["score"]), reverse=True)
        return {
            "project_id": str(project.id),
            "namespace": project.isolation_namespace,
            "query": query,
            "top_k": top_k,
            "method": "owned_local_hash",
            "hits": hits[: max(1, min(top_k, 50))],
            "indexed": len(hits),
        }

    async def stats(self, project_id: UUID) -> dict[str, Any]:
        project = await self._project(project_id)
        path = self._index_path(project)
        count = 0
        if path.exists():
            count = sum(1 for line in path.open(encoding="utf-8") if line.strip())
        return {
            "project_id": str(project.id),
            "vectors": count,
            "path": str(path),
            "method": "owned_local_hash",
            "dims": DIM,
        }
