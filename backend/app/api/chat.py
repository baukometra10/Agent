from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.agent import ChatAgentService
from app.db.session import get_db
from app.schemas.project import (
    ChatMessageIn,
    ChatMessageOut,
    ChatReplyOut,
    ChatSessionCreate,
    ChatSessionOut,
    ChatSessionUpdate,
)
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects/{project_id}/chat", tags=["chat"])


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _status_lang(text: str) -> str:
    raw = text or ""
    if any("\u0600" <= ch <= "\u06FF" for ch in raw):
        return "ar"
    low = raw.lower()
    if any(
        w in low
        for w in ("ich", "wir", "bitte", "machen", "können", "projekt", "und", "eine", "app", "bau")
    ) or any(ch in low for ch in "äöüß"):
        return "de"
    return "en"


# Cursor/Claude-like progress: understand → plan → implement → reply
_STATUS_PHASES: dict[str, list[tuple[str, str]]] = {
    "ar": [
        ("understand", "يفهم الطلب…"),
        ("reading", "يقرأ المشروع…"),
        ("plan", "يضع خطة…"),
        ("implement", "يجهّز التنفيذ…"),
    ],
    "de": [
        ("understand", "Versteht die Anfrage…"),
        ("reading", "Liest das Projekt…"),
        ("plan", "Plant…"),
        ("implement", "Bereitet Umsetzung vor…"),
    ],
    "en": [
        ("understand", "Understanding…"),
        ("reading", "Reading the project…"),
        ("plan", "Planning…"),
        ("implement", "Preparing implement…"),
    ],
}


def _projects(session: AsyncSession = Depends(get_db)) -> ProjectService:
    return ProjectService(session)


def _chat(session: AsyncSession = Depends(get_db)) -> ChatAgentService:
    return ChatAgentService(session)


@router.post("/sessions", response_model=ChatSessionOut, status_code=201)
async def create_session(
    project_id: UUID,
    title: str | None = Query(default=None),
    payload: ChatSessionCreate | None = None,
    projects: ProjectService = Depends(_projects),
    chat: ChatAgentService = Depends(_chat),
):
    if not await projects.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    chosen = (payload.title if payload and payload.title else None) or title
    session = await chat.create_session(project_id, title=chosen)
    return session


@router.get("/sessions", response_model=list[ChatSessionOut])
async def list_sessions(
    project_id: UUID,
    status: str | None = Query(default="all", description="active | archived | all"),
    projects: ProjectService = Depends(_projects),
    chat: ChatAgentService = Depends(_chat),
):
    if not await projects.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return await chat.list_sessions(project_id, status=status)


@router.post("/sessions/{session_id}/archive", response_model=ChatSessionOut)
async def archive_session(
    project_id: UUID,
    session_id: UUID,
    projects: ProjectService = Depends(_projects),
    chat: ChatAgentService = Depends(_chat),
):
    if not await projects.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        return await chat.archive_session(project_id, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/unarchive", response_model=ChatSessionOut)
async def unarchive_session(
    project_id: UUID,
    session_id: UUID,
    projects: ProjectService = Depends(_projects),
    chat: ChatAgentService = Depends(_chat),
):
    if not await projects.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        return await chat.unarchive_session(project_id, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/sessions/{session_id}", response_model=ChatSessionOut)
async def get_session(
    project_id: UUID,
    session_id: UUID,
    projects: ProjectService = Depends(_projects),
    chat: ChatAgentService = Depends(_chat),
):
    if not await projects.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    session = await chat.get_session(project_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.patch("/sessions/{session_id}", response_model=ChatSessionOut)
async def update_session(
    project_id: UUID,
    session_id: UUID,
    payload: ChatSessionUpdate,
    projects: ProjectService = Depends(_projects),
    chat: ChatAgentService = Depends(_chat),
):
    if not await projects.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        return await chat.update_session(
            project_id,
            session_id,
            title=payload.title,
            status=payload.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    project_id: UUID,
    session_id: UUID,
    hard: bool = Query(default=False, description="Permanent delete when true"),
    projects: ProjectService = Depends(_projects),
    chat: ChatAgentService = Depends(_chat),
):
    if not await projects.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        if hard:
            await chat.purge_session(project_id, session_id)
        else:
            await chat.delete_session(project_id, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/resume")
async def get_resume_checkpoint(
    project_id: UUID,
    session_id: UUID,
    projects: ProjectService = Depends(_projects),
    chat: ChatAgentService = Depends(_chat),
):
    if not await projects.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        cp = await chat.get_resume_checkpoint(project_id, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not cp:
        raise HTTPException(status_code=404, detail="No resume checkpoint")
    return cp


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
async def list_messages(
    project_id: UUID,
    session_id: UUID,
    projects: ProjectService = Depends(_projects),
    chat: ChatAgentService = Depends(_chat),
):
    if not await projects.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        return await chat.list_messages(project_id, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/messages", response_model=ChatReplyOut)
async def send_message(
    project_id: UUID,
    session_id: UUID,
    payload: ChatMessageIn,
    projects: ProjectService = Depends(_projects),
    chat: ChatAgentService = Depends(_chat),
):
    if not await projects.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        result = await chat.chat(
            project_id,
            session_id,
            payload.message,
            preferred_provider=payload.preferred_provider,
            preferred_agent=payload.preferred_agent,
            mode=payload.mode,
            attachments=payload.attachments or [],
            resume=bool(payload.resume),
            max_tokens_budget=payload.max_tokens_budget,
            max_seconds=payload.max_seconds,
            allow_teacher=payload.allow_teacher,
        )
        return ChatReplyOut(
            session_id=UUID(result["session_id"]),
            reply=result["reply"],
            proposal=result.get("proposal"),
            tools_used=result.get("tools_used") or [],
            model=result.get("model"),
            simulated=bool(result.get("simulated")),
            route_tier=result.get("route_tier"),
            conductor=result.get("conductor"),
            intent=result.get("intent"),
            intent_label=result.get("intent_label"),
            specialists=result.get("specialists") or [],
            session_title=result.get("session_title"),
            handoff=result.get("handoff") if isinstance(result.get("handoff"), dict) else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/messages/stream")
async def send_message_stream(
    project_id: UUID,
    session_id: UUID,
    payload: ChatMessageIn,
    request: Request,
    projects: ProjectService = Depends(_projects),
    chat: ChatAgentService = Depends(_chat),
):
    """SSE stream: status → delta chunks → done. Client abort cancels the task."""
    if not await projects.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    async def _save_abort(partial: str = "") -> None:
        topic = payload.message
        if "طلب المستخدم:" in topic:
            topic = topic.split("طلب المستخدم:")[-1].strip()
        try:
            await chat.set_resume_checkpoint(
                project_id,
                session_id,
                user_topic=topic[:2000],
                partial_reply=partial,
                attachments=payload.attachments or [],
                mode=payload.mode,
                preferred_provider=payload.preferred_provider,
                last_status="aborted",
            )
        except Exception:  # noqa: BLE001
            pass

    async def event_gen() -> AsyncIterator[str]:
        from app.gateway.request_context import set_status_sink

        lang = _status_lang(payload.message or "")
        phases = _STATUS_PHASES.get(lang) or _STATUS_PHASES["en"]
        phase0, label0 = phases[0]
        status_q: asyncio.Queue = asyncio.Queue()
        set_status_sink(status_q)
        yield _sse({"type": "status", "phase": phase0, "text": label0, "step": 1, "total": 4})
        limit = int(payload.max_seconds or 90)
        limit = max(15, min(limit, 3600))
        task = asyncio.create_task(
            chat.chat(
                project_id,
                session_id,
                payload.message,
                preferred_provider=payload.preferred_provider,
                preferred_agent=payload.preferred_agent,
                mode=payload.mode,
                attachments=payload.attachments or [],
                resume=bool(payload.resume),
                max_tokens_budget=payload.max_tokens_budget,
                max_seconds=payload.max_seconds,
                allow_teacher=payload.allow_teacher,
            )
        )
        pulse = 0
        fallback_idx = 0
        partial_out = ""
        try:
            while not task.done():
                if await request.is_disconnected():
                    task.cancel()
                    try:
                        await task
                    except (asyncio.CancelledError, Exception):
                        pass
                    await _save_abort(partial_out)
                    yield _sse({"type": "aborted"})
                    return
                # Drain real Cursor/master status ticks first
                drained = False
                while True:
                    try:
                        evt = status_q.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    drained = True
                    if isinstance(evt, dict) and evt.get("type") == "status":
                        yield _sse(evt)
                pulse += 1
                # Soft fallback ticks only when no real status arrived yet
                if not drained and pulse % 10 == 0 and fallback_idx < len(phases) - 1:
                    fallback_idx += 1
                    phase, label = phases[fallback_idx]
                    yield _sse(
                        {
                            "type": "status",
                            "phase": phase,
                            "text": label,
                            "step": fallback_idx + 1,
                            "total": 4,
                        }
                    )
                if pulse * 0.2 >= limit:
                    task.cancel()
                    try:
                        await task
                    except (asyncio.CancelledError, Exception):
                        pass
                    await _save_abort(partial_out)
                    yield _sse(
                        {
                            "type": "error",
                            "detail": f"Zeitlimit ({limit}s) — Modell antwortet nicht.",
                        }
                    )
                    return
                await asyncio.sleep(0.2)
            # Flush any late status events
            while True:
                try:
                    evt = status_q.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if isinstance(evt, dict) and evt.get("type") == "status":
                    yield _sse(evt)
            result = task.result()
        except asyncio.CancelledError:
            await _save_abort(partial_out)
            yield _sse({"type": "aborted"})
            return
        except Exception as exc:  # noqa: BLE001
            yield _sse({"type": "error", "detail": str(exc)[:500]})
            return
        finally:
            set_status_sink(None)

        reply = str(result.get("reply") or "")
        streaming_label = {
            "ar": "يبث الرد…",
            "de": "Antwort kommt…",
            "en": "Streaming reply…",
        }.get(lang, "Streaming reply…")
        yield _sse(
            {
                "type": "status",
                "phase": "streaming",
                "text": streaming_label,
                "step": 4,
                "total": 4,
            }
        )
        # Progressive deltas so the UI can render live
        step = max(12, min(48, len(reply) // 40 or 12))
        for i in range(0, len(reply), step):
            if await request.is_disconnected():
                await _save_abort(reply[: i + step])
                yield _sse({"type": "aborted"})
                return
            chunk = reply[i : i + step]
            partial_out += chunk
            yield _sse({"type": "delta", "text": chunk})
            await asyncio.sleep(0.012)

        yield _sse(
            {
                "type": "done",
                "session_id": result.get("session_id"),
                "reply": reply,
                "model": result.get("model"),
                "simulated": bool(result.get("simulated")),
                "route_tier": result.get("route_tier"),
                "session_title": result.get("session_title"),
                "intent": result.get("intent"),
                "budget_hit": bool(result.get("budget_hit")),
                "usage": result.get("usage"),
                "decision": result.get("decision"),
                "specialists": result.get("specialists") or [],
                "build_phase": result.get("build_phase"),
            }
        )

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
