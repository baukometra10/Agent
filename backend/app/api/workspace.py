"""HTTP API for Spixa web IDE — list / open / save project files."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.project_service import ProjectService
from app.workspace.edits import apply_edits_to_workspace, parse_agent_edits
from app.workspace.complete import suggest_completions
from app.workspace.files import (
    build_tree,
    create_entry,
    mime_for_path,
    read_text_file,
    resolve_workspace_file,
    write_text_file,
)
from app.workspace.preview import preview_status, start_preview, stop_preview, verify_preview
from app.workspace.terminal import run_workspace_command

router = APIRouter(prefix="/projects", tags=["workspace"])


class FileWriteIn(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    content: str = ""


class FileCreateIn(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    kind: str = "file"  # file | dir
    content: str = ""


class AgentApplyIn(BaseModel):
    reply: str = ""
    edits: list[dict] | None = None


class TerminalIn(BaseModel):
    command: str = Field(min_length=1, max_length=4000)
    cwd: str | None = None
    timeout: int = 45


class CompleteIn(BaseModel):
    path: str = ""
    language: str = "plaintext"
    prefix: str = ""
    suffix: str = ""


async def _project(project_id: UUID, session: AsyncSession):
    project = await ProjectService(session).get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/{project_id}/workspace/tree")
async def workspace_tree(project_id: UUID, session: AsyncSession = Depends(get_db)):
    project = await _project(project_id, session)
    try:
        return build_tree(project.workspace_path)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/{project_id}/workspace/file")
async def workspace_read_file(
    project_id: UUID,
    path: str,
    session: AsyncSession = Depends(get_db),
):
    project = await _project(project_id, session)
    try:
        result = read_text_file(project.workspace_path, path)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error") or "not found")
    return result


@router.get("/{project_id}/workspace/raw")
async def workspace_raw_file(
    project_id: UUID,
    path: str,
    session: AsyncSession = Depends(get_db),
):
    """Stream original bytes (images, PDF, audio, video, other binaries)."""
    project = await _project(project_id, session)
    try:
        target = resolve_workspace_file(project.workspace_path, path)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="file_not_found")
    return FileResponse(
        path=str(target),
        media_type=mime_for_path(target),
        filename=target.name,
        content_disposition_type="inline",
    )


@router.put("/{project_id}/workspace/file")
async def workspace_write_file(
    project_id: UUID,
    payload: FileWriteIn,
    session: AsyncSession = Depends(get_db),
):
    project = await _project(project_id, session)
    try:
        result = write_text_file(project.workspace_path, payload.path, payload.content)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "write failed")
    return result


@router.post("/{project_id}/workspace/file")
async def workspace_create(
    project_id: UUID,
    payload: FileCreateIn,
    session: AsyncSession = Depends(get_db),
):
    project = await _project(project_id, session)
    kind = "dir" if payload.kind == "dir" else "file"
    try:
        result = create_entry(
            project.workspace_path,
            payload.path,
            kind=kind,
            content=payload.content,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "create failed")
    return result


@router.post("/{project_id}/workspace/apply-edits")
async def workspace_apply_edits(
    project_id: UUID,
    payload: AgentApplyIn,
    session: AsyncSession = Depends(get_db),
):
    """Apply file edits parsed from an agent reply (or explicit edits list)."""
    project = await _project(project_id, session)
    edits = payload.edits or parse_agent_edits(payload.reply or "")
    if not edits:
        return {"ok": True, "applied": [], "errors": [], "note": "no_edits_found"}
    try:
        return apply_edits_to_workspace(project.workspace_path, edits)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/{project_id}/workspace/terminal")
async def workspace_terminal(
    project_id: UUID,
    payload: TerminalIn,
    session: AsyncSession = Depends(get_db),
):
    project = await _project(project_id, session)
    try:
        return run_workspace_command(
            project.workspace_path,
            payload.command,
            cwd_rel=payload.cwd,
            timeout=payload.timeout,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/{project_id}/workspace/complete")
async def workspace_complete(
    project_id: UUID,
    payload: CompleteIn,
    session: AsyncSession = Depends(get_db),
):
    await _project(project_id, session)
    return await suggest_completions(
        language=payload.language,
        prefix=payload.prefix or "",
        suffix=payload.suffix or "",
        path=payload.path or "",
    )


@router.get("/{project_id}/workspace/preview")
async def workspace_preview_status(
    project_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    await _project(project_id, session)
    return preview_status(project_id)


@router.post("/{project_id}/workspace/preview/start")
async def workspace_preview_start(
    project_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    project = await _project(project_id, session)
    result = start_preview(project_id, project.workspace_path)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "preview_failed")
    return result


@router.post("/{project_id}/workspace/preview/stop")
async def workspace_preview_stop(
    project_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    await _project(project_id, session)
    return stop_preview(project_id)


@router.post("/{project_id}/workspace/preview/verify")
async def workspace_preview_verify(
    project_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Post-build check: HTTP probe the live preview and learn from the outcome."""
    await _project(project_id, session)
    result = verify_preview(project_id)
    try:
        from app.learning.operation_outcome import learn_from_operation

        learn_from_operation(
            kind="build_ok" if result.get("ok") else "build_fail",
            title="Preview verify",
            detail=str(result.get("url") or result.get("error") or "verify"),
            project_id=str(project_id),
            intent="implement",
            human_verified=bool(result.get("ok")),
        )
    except Exception:  # noqa: BLE001
        pass
    return result
