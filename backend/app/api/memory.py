"""Per-project long-term memory APIs — hard isolation, every retained word."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.knowledge.memory import LAYER_DESCRIPTIONS, MEMORY_LAYERS
from app.memory import ProjectLongTermMemory
from app.memory.embeddings_store import ProjectEmbeddingsStore

router = APIRouter(prefix="/projects/{project_id}/memory", tags=["memory"])


class RememberBody(BaseModel):
    role: str = Field(default="user", pattern="^(user|assistant|system)$")
    content: str = Field(min_length=1)
    session_id: UUID | None = None


class EmbedUpsertBody(BaseModel):
    text: str = Field(min_length=1)
    source: str = "manual"
    meta: dict[str, Any] = Field(default_factory=dict)


class EmbedSearchBody(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


@router.get("/layers")
async def memory_layers(project_id: UUID):
    _ = project_id  # path-scoped for UI consistency
    return {
        "layers": list(MEMORY_LAYERS),
        "descriptions": LAYER_DESCRIPTIONS,
        "isolation": "Each project's memory lives only under its workspace; never shared.",
    }


@router.get("")
async def recall_memory(
    project_id: UUID,
    session_id: UUID | None = Query(default=None),
    transcript_limit: int = Query(default=80, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await ProjectLongTermMemory(db).recall(
            project_id,
            session_id=session_id,
            transcript_limit=transcript_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/remember")
async def remember(
    project_id: UUID,
    body: RememberBody,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await ProjectLongTermMemory(db).remember_utterance(
            project_id,
            role=body.role,
            content=body.content,
            session_id=body.session_id,
        )
        await db.commit()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class PreferencesBody(BaseModel):
    language: str | None = Field(default=None, max_length=16)
    stack: str | None = Field(default=None, max_length=120)
    no_scaffold: bool | None = None
    always_preview: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)


def _prefs_text(prefs: dict[str, Any]) -> str:
    parts = ["Project preferences (always obey for THIS project):"]
    if prefs.get("language"):
        parts.append(f"- UI/chat language preference: {prefs['language']}")
    if prefs.get("stack"):
        parts.append(f"- Preferred stack: {prefs['stack']}")
    if prefs.get("no_scaffold"):
        parts.append("- Never dump canned scaffolds; build from the real ask only.")
    if prefs.get("always_preview"):
        parts.append("- After UI edits, start/remind Live Preview for testing while building.")
    if prefs.get("notes"):
        parts.append(f"- Notes: {prefs['notes']}")
    return "\n".join(parts)


@router.get("/preferences")
async def get_preferences(project_id: UUID, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select

    from app.db.models import KnowledgeNode, Project

    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="project_not_found")
    result = await db.execute(
        select(KnowledgeNode)
        .where(
            KnowledgeNode.project_id == project_id,
            KnowledgeNode.category == "project_preferences",
        )
        .order_by(KnowledgeNode.created_at.desc())
        .limit(1)
    )
    node = result.scalar_one_or_none()
    evidence = (node.evidence if node and isinstance(node.evidence, dict) else {}) or {}
    return {
        "ok": True,
        "preferences": evidence.get("preferences") or {},
        "standing_text": node.content if node else "",
        "node_id": str(node.id) if node else None,
    }


@router.put("/preferences")
async def put_preferences(
    project_id: UUID,
    body: PreferencesBody,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select

    from app.db.models import KnowledgeKind, KnowledgeNode, Project

    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="project_not_found")

    prefs = {k: v for k, v in body.model_dump().items() if v is not None}
    # Merge with existing
    existing = await db.execute(
        select(KnowledgeNode)
        .where(
            KnowledgeNode.project_id == project_id,
            KnowledgeNode.category == "project_preferences",
        )
        .order_by(KnowledgeNode.created_at.desc())
        .limit(1)
    )
    node = existing.scalar_one_or_none()
    prev = {}
    if node and isinstance(node.evidence, dict):
        prev = dict(node.evidence.get("preferences") or {})
    merged = {**prev, **prefs}
    text = _prefs_text(merged)

    if node:
        node.content = text
        node.title = "Project preferences"
        node.evidence = {"preferences": merged, "standing": True}
        node.confidence = 0.99
    else:
        node = KnowledgeNode(
            project_id=project_id,
            memory_layer="decision",
            category="project_preferences",
            kind=KnowledgeKind.fact,
            title="Project preferences",
            content=text,
            confidence=0.99,
            source_type="user",
            source_path="ide_preferences",
            evidence={"preferences": merged, "standing": True},
        )
        db.add(node)

    # Also mirror as standing_instruction so master recall picks it up
    stand = KnowledgeNode(
        project_id=project_id,
        memory_layer="decision",
        category="standing_instruction",
        kind=KnowledgeKind.fact,
        title="Standing preference (IDE)",
        content=text[:2000],
        confidence=0.99,
        source_type="user",
        source_path="ide_preferences",
        evidence={"standing": True, "preferences": merged},
    )
    db.add(stand)
    await db.commit()
    return {"ok": True, "preferences": merged, "standing_text": text}


@router.get("/embeddings")
async def embeddings_stats(project_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        return await ProjectEmbeddingsStore(db).stats(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/embeddings")
async def embeddings_upsert(
    project_id: UUID,
    body: EmbedUpsertBody,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await ProjectEmbeddingsStore(db).upsert(
            project_id, text=body.text, source=body.source, meta=body.meta
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/embeddings/search")
async def embeddings_search(
    project_id: UUID,
    body: EmbedSearchBody,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await ProjectEmbeddingsStore(db).search(
            project_id, query=body.query, top_k=body.top_k
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/embeddings/purge-pollution")
async def embeddings_purge_pollution(project_id: UUID, db: AsyncSession = Depends(get_db)):
    """Remove scaffold/system-prompt junk that causes the teacher to echo instructions."""
    try:
        result = await ProjectEmbeddingsStore(db).purge_pollution(project_id)
        # Also drop polluted standing instructions
        from sqlalchemy import select

        from app.db.models import KnowledgeNode

        nodes = await db.execute(
            select(KnowledgeNode).where(
                KnowledgeNode.project_id == project_id,
                KnowledgeNode.category.in_(["standing_instruction", "utterance"]),
            )
        )
        from app.memory.pollution import is_pollution_text

        removed_nodes = 0
        for node in list(nodes.scalars().all()):
            if is_pollution_text(node.content or "") or is_pollution_text(node.title or ""):
                await db.delete(node)
                removed_nodes += 1
        await db.commit()
        result["removed_knowledge_nodes"] = removed_nodes
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
