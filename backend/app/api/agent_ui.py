"""Agent panel workspace state: templates, tab sync, share links."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.agent import ChatAgentService
from app.db.models import AgentSession, Project
from app.db.session import get_db
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects/{project_id}/agent-ui", tags=["agent-ui"])
share_router = APIRouter(prefix="/agent-share", tags=["agent-ui"])


def _projects(session: AsyncSession = Depends(get_db)) -> ProjectService:
    return ProjectService(session)


def _chat(session: AsyncSession = Depends(get_db)) -> ChatAgentService:
    return ChatAgentService(session)


class CommandTemplate(BaseModel):
    id: str
    title: str = Field(min_length=1, max_length=120)
    prompt: str = Field(min_length=1, max_length=4000)
    created_at: str | None = None


class TemplatesOut(BaseModel):
    templates: list[CommandTemplate] = Field(default_factory=list)


class TemplateCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    prompt: str = Field(min_length=1, max_length=4000)


class TabsState(BaseModel):
    open_ids: list[str] = Field(default_factory=list)
    active_id: str | None = None
    pinned_ids: list[str] = Field(default_factory=list)
    updated_at: str | None = None


class ShareOut(BaseModel):
    token: str
    path: str
    session_id: str
    project_id: str


class ShareResolveOut(BaseModel):
    project_id: str
    session_id: str
    title: str
    status: str


async def _load_project(db: AsyncSession, project_id: UUID) -> Project:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _save_settings(db: AsyncSession, project: Project, settings: dict[str, Any]) -> None:
    project.settings = settings
    await db.commit()
    await db.refresh(project)


@router.get("/templates", response_model=TemplatesOut)
async def list_templates(project_id: UUID, db: AsyncSession = Depends(get_db)):
    project = await _load_project(db, project_id)
    raw = list((project.settings or {}).get("agent_templates") or [])
    rows = [CommandTemplate.model_validate(x) for x in raw if isinstance(x, dict)]
    return TemplatesOut(templates=rows)


@router.post("/templates", response_model=CommandTemplate, status_code=201)
async def create_template(
    project_id: UUID,
    payload: TemplateCreate,
    db: AsyncSession = Depends(get_db),
):
    project = await _load_project(db, project_id)
    settings = dict(project.settings or {})
    rows = list(settings.get("agent_templates") or [])
    item = {
        "id": secrets.token_urlsafe(8),
        "title": payload.title.strip(),
        "prompt": payload.prompt.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    rows.insert(0, item)
    settings["agent_templates"] = rows[:60]
    await _save_settings(db, project, settings)
    return CommandTemplate.model_validate(item)


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(project_id: UUID, template_id: str, db: AsyncSession = Depends(get_db)):
    project = await _load_project(db, project_id)
    settings = dict(project.settings or {})
    rows = [r for r in list(settings.get("agent_templates") or []) if str(r.get("id")) != template_id]
    settings["agent_templates"] = rows
    await _save_settings(db, project, settings)
    return None


@router.get("/tabs-state", response_model=TabsState)
async def get_tabs_state(project_id: UUID, db: AsyncSession = Depends(get_db)):
    project = await _load_project(db, project_id)
    raw = dict((project.settings or {}).get("ide_tabs_state") or {})
    return TabsState(
        open_ids=[str(x) for x in (raw.get("open_ids") or [])],
        active_id=str(raw["active_id"]) if raw.get("active_id") else None,
        pinned_ids=[str(x) for x in (raw.get("pinned_ids") or [])],
        updated_at=raw.get("updated_at"),
    )


@router.put("/tabs-state", response_model=TabsState)
async def put_tabs_state(project_id: UUID, payload: TabsState, db: AsyncSession = Depends(get_db)):
    project = await _load_project(db, project_id)
    settings = dict(project.settings or {})
    incoming_ts = payload.updated_at or datetime.now(timezone.utc).isoformat()
    current = dict(settings.get("ide_tabs_state") or {})
    current_ts = str(current.get("updated_at") or "")
    # Last-write-wins by ISO timestamp
    if current_ts and incoming_ts < current_ts:
        return TabsState(
            open_ids=[str(x) for x in (current.get("open_ids") or [])],
            active_id=str(current["active_id"]) if current.get("active_id") else None,
            pinned_ids=[str(x) for x in (current.get("pinned_ids") or [])],
            updated_at=current_ts,
        )
    state = {
        "open_ids": payload.open_ids[:40],
        "active_id": payload.active_id,
        "pinned_ids": payload.pinned_ids[:40],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    settings["ide_tabs_state"] = state
    await _save_settings(db, project, settings)
    return TabsState(**state)


@router.post("/sessions/{session_id}/share", response_model=ShareOut)
async def create_share_link(
    project_id: UUID,
    session_id: UUID,
    projects: ProjectService = Depends(_projects),
    chat: ChatAgentService = Depends(_chat),
    db: AsyncSession = Depends(get_db),
):
    project = await projects.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    session = await chat.get_session(project_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    meta = dict(session.meta or {})
    token = str((meta.get("share") or {}).get("token") or "") or secrets.token_urlsafe(16)
    meta["share"] = {
        "token": token,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "access": "readwrite",
    }
    session.meta = meta
    settings = dict(project.settings or {})
    index = dict(settings.get("share_index") or {})
    index[token] = {"session_id": str(session_id), "project_id": str(project_id)}
    settings["share_index"] = index
    project.settings = settings
    await db.commit()
    return ShareOut(
        token=token,
        path=f"/ide?share={token}",
        session_id=str(session_id),
        project_id=str(project_id),
    )


@share_router.get("/{token}", response_model=ShareResolveOut)
async def resolve_share(token: str, db: AsyncSession = Depends(get_db)):
    cleaned = (token or "").strip()
    if not cleaned:
        raise HTTPException(status_code=404, detail="Invalid share token")
    # Prefer project share_index (O(projects) small); fallback scan sessions
    projects = (await db.execute(select(Project))).scalars().all()
    for project in projects:
        hit = dict((project.settings or {}).get("share_index") or {}).get(cleaned)
        if isinstance(hit, dict) and hit.get("session_id"):
            try:
                sid = UUID(str(hit["session_id"]))
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(status_code=404, detail="Broken share index") from exc
            session = await db.get(AgentSession, sid)
            if session:
                return ShareResolveOut(
                    project_id=str(session.project_id),
                    session_id=str(session.id),
                    title=session.title or "أمر جديد",
                    status=session.status,
                )
    result = await db.execute(select(AgentSession))
    for session in result.scalars().all():
        share = dict((session.meta or {}).get("share") or {})
        if share.get("token") == cleaned:
            return ShareResolveOut(
                project_id=str(session.project_id),
                session_id=str(session.id),
                title=session.title or "أمر جديد",
                status=session.status,
            )
    raise HTTPException(status_code=404, detail="Share link not found")
