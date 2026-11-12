"""Project-isolated embeddings store — Chroma-like durable memory.

Dual write:
1) workspace JSONL (fast local, volume-backed on cloud)
2) Postgres `project_memory_vectors` (survives even if workspace path moves)

Uses a deterministic local hasher as the owned embeddings student by default
(no network). Never cross project boundaries.
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

from app.db.models import Project, ProjectMemoryVector
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
        cleaned = (text or "").strip()
        if not cleaned:
            return {"ok": False, "reason": "empty"}
        try:
            from app.memory.pollution import is_pollution_text, strip_pollution

            cleaned = strip_pollution(cleaned)
            if not cleaned or is_pollution_text(cleaned):
                return {"ok": False, "reason": "prompt_pollution"}
        except Exception:  # noqa: BLE001
            pass
        vec = local_embed(cleaned)
        row_id = uuid4()
        row = {
            "id": str(row_id),
            "project_id": str(project.id),
            "namespace": project.isolation_namespace,
            "text": cleaned[:4000],
            "source": source,
            "meta": meta or {},
            "vector": vec,
            "dims": len(vec),
            "method": "owned_local_hash",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        # 1) workspace JSONL
        path = self._index_path(project)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        # 2) durable DB row
        self.session.add(
            ProjectMemoryVector(
                id=row_id,
                project_id=project.id,
                text=row["text"],
                source=source,
                method="owned_local_hash",
                dims=len(vec),
                vector=vec,
                meta={
                    **(meta or {}),
                    "isolation_namespace": project.isolation_namespace,
                },
            )
        )
        await self.session.flush()
        return {
            "ok": True,
            "id": row["id"],
            "dims": row["dims"],
            "method": row["method"],
            "path": str(path),
            "backend": "jsonl+postgres",
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
        qv = local_embed(query)
        hits: list[dict[str, Any]] = []
        seen: set[str] = set()

        # Prefer DB (durable); merge JSONL for older local-only rows
        db_rows = await self.session.execute(
            select(ProjectMemoryVector)
            .where(ProjectMemoryVector.project_id == project_id)
            .order_by(ProjectMemoryVector.created_at.desc())
            .limit(2000)
        )
        for row in db_rows.scalars().all():
            score = cosine(qv, list(row.vector or []))
            rid = str(row.id)
            seen.add(rid)
            hits.append(
                {
                    "id": rid,
                    "score": round(score, 4),
                    "text": row.text,
                    "source": row.source,
                    "meta": row.meta or {},
                    "backend": "postgres",
                }
            )

        path = self._index_path(project)
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if str(row.get("project_id")) != str(project.id):
                    continue
                if row.get("namespace") and row.get("namespace") != project.isolation_namespace:
                    continue
                rid = str(row.get("id") or "")
                if rid in seen:
                    continue
                score = cosine(qv, list(row.get("vector") or []))
                hits.append(
                    {
                        "id": rid,
                        "score": round(score, 4),
                        "text": row.get("text"),
                        "source": row.get("source"),
                        "meta": row.get("meta") or {},
                        "backend": "jsonl",
                    }
                )

        try:
            from app.memory.pollution import is_pollution_text, strip_pollution

            clean_hits: list[dict[str, Any]] = []
            for h in hits:
                chunk = strip_pollution(str(h.get("text") or ""))
                if not chunk or is_pollution_text(chunk):
                    continue
                h = {**h, "text": chunk}
                clean_hits.append(h)
            hits = clean_hits
        except Exception:  # noqa: BLE001
            pass
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

    async def purge_pollution(self, project_id: UUID) -> dict[str, Any]:
        """Drop scaffold/system-prompt vectors that poison Cursor replies."""
        from app.memory.pollution import is_pollution_text

        project = await self._project(project_id)
        removed_db = 0
        db_rows = await self.session.execute(
            select(ProjectMemoryVector).where(ProjectMemoryVector.project_id == project_id)
        )
        for row in list(db_rows.scalars().all()):
            if is_pollution_text(row.text or ""):
                await self.session.delete(row)
                removed_db += 1
        await self.session.flush()

        path = self._index_path(project)
        removed_jsonl = 0
        kept = 0
        if path.exists():
            lines = path.read_text(encoding="utf-8").splitlines()
            out: list[str] = []
            for line in lines:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if is_pollution_text(str(row.get("text") or "")):
                    removed_jsonl += 1
                    continue
                out.append(json.dumps(row, ensure_ascii=False))
                kept += 1
            path.write_text("\n".join(out) + ("\n" if out else ""), encoding="utf-8")
        return {
            "ok": True,
            "project_id": str(project.id),
            "removed_postgres": removed_db,
            "removed_jsonl": removed_jsonl,
            "kept_jsonl": kept,
        }

    async def stats(self, project_id: UUID) -> dict[str, Any]:
        project = await self._project(project_id)
        path = self._index_path(project)
        file_count = 0
        if path.exists():
            file_count = sum(1 for line in path.open(encoding="utf-8") if line.strip())
        from sqlalchemy import func

        db_n = await self.session.scalar(
            select(func.count())
            .select_from(ProjectMemoryVector)
            .where(ProjectMemoryVector.project_id == project_id)
        )
        return {
            "project_id": str(project.id),
            "vectors_jsonl": file_count,
            "vectors_postgres": int(db_n or 0),
            "path": str(path),
            "method": "owned_local_hash",
            "dims": DIM,
            "backend": "jsonl+postgres",
            "chroma_like": True,
        }
