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
