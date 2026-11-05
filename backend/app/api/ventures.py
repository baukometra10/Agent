"""Venture API — multi-phase business→system pipeline + twin/patterns/research hooks."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.project_service import ProjectService
from app.venture.adversarial import AdversarialLab
from app.venture.orchestrator import VentureOrchestrator
from app.venture.patterns import PatternLibrary
from app.venture.research import ResearchLabService
from app.venture.twin import DigitalTwinService

router = APIRouter(prefix="/projects/{project_id}/ventures", tags=["ventures"])
patterns_router = APIRouter(prefix="/patterns", tags=["knowledge-network"])
research_router = APIRouter(prefix="/system/research", tags=["research-lab"])
twin_router = APIRouter(prefix="/projects/{project_id}/twin", tags=["digital-twin"])


class VentureCreateIn(BaseModel):
    brief: str = Field(min_length=8, max_length=8000)
    title: str | None = Field(default=None, max_length=255)


class VentureApproveIn(BaseModel):
    actor: str = "human"
    selected_architecture_id: str | None = None
    acknowledge_adversarial: bool = False


class VentureRejectIn(BaseModel):
    reason: str = ""
    actor: str = "human"


class SimulateIn(BaseModel):
    change_summary: str = Field(min_length=3, max_length=4000)
    affected_paths: list[str] = Field(default_factory=list)


class PatternApplyIn(BaseModel):
    pattern_id: UUID


class PatternProposeIn(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    summary: str = Field(min_length=8, max_length=4000)
    category: str = "architecture"


class ResearchCreateIn(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    hypothesis: str = Field(min_length=8, max_length=4000)
    kind: str = "routing"
    config: dict[str, Any] = Field(default_factory=dict)


class ResearchPromoteDecideIn(BaseModel):
    approve: bool
    actor: str = "human"


def _orch(session: AsyncSession = Depends(get_db)) -> VentureOrchestrator:
    return VentureOrchestrator(session)


def _projects(session: AsyncSession = Depends(get_db)) -> ProjectService:
    return ProjectService(session)


@router.get("")
async def list_ventures(project_id: UUID, orch: VentureOrchestrator = Depends(_orch)):
    return await orch.list_ventures(project_id)


@router.post("", status_code=201)
async def create_venture(
    project_id: UUID,
    body: VentureCreateIn,
    orch: VentureOrchestrator = Depends(_orch),
):
    try:
        return await orch.create(project_id, brief=body.brief, title=body.title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/demo/company-os", status_code=201)
async def demo_company_os(project_id: UUID, orch: VentureOrchestrator = Depends(_orch)):
    """Golden Path: Firmen-OS Venture with fixed Arabic brief and human gates."""
    try:
        return await orch.start_demo_company_os(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{venture_id}")
async def get_venture(
    project_id: UUID,
    venture_id: UUID,
    orch: VentureOrchestrator = Depends(_orch),
):
    venture = await orch.get(project_id, venture_id)
    if not venture:
        raise HTTPException(status_code=404, detail="Venture not found")
    return orch.serialize(venture)


@router.post("/{venture_id}/advance")
async def advance_venture(
    project_id: UUID,
    venture_id: UUID,
    orch: VentureOrchestrator = Depends(_orch),
):
    try:
        return await orch.advance(project_id, venture_id, auto=False)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{venture_id}/approve")
async def approve_venture(
    project_id: UUID,
    venture_id: UUID,
    body: VentureApproveIn,
    orch: VentureOrchestrator = Depends(_orch),
):
    try:
        return await orch.approve(
            project_id,
            venture_id,
            actor=body.actor,
            selected_architecture_id=body.selected_architecture_id,
            acknowledge_adversarial=body.acknowledge_adversarial,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{venture_id}/reject")
async def reject_venture(
    project_id: UUID,
    venture_id: UUID,
    body: VentureRejectIn,
    orch: VentureOrchestrator = Depends(_orch),
):
    try:
        return await orch.reject(project_id, venture_id, reason=body.reason, actor=body.actor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{venture_id}/stream")
async def stream_venture_create(
    project_id: UUID,
    body: VentureCreateIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """Create venture and stream phase status events (SSE)."""

    def _sse(payload: dict[str, Any]) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    orch = VentureOrchestrator(session)

    async def event_gen():
        yield _sse({"type": "status", "text": "starting"})
        try:
            task = asyncio.create_task(
                orch.create(project_id, brief=body.brief, title=body.title)
            )
            while not task.done():
                if await request.is_disconnected():
                    task.cancel()
                    return
                yield _sse({"type": "status", "text": "working"})
                await asyncio.sleep(0.4)
            result = task.result()
            yield _sse({"type": "done", "venture": result})
        except Exception as exc:  # noqa: BLE001
            yield _sse({"type": "error", "detail": str(exc)[:500]})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@twin_router.get("")
async def get_twin(project_id: UUID, session: AsyncSession = Depends(get_db), projects: ProjectService = Depends(_projects)):
    project = await projects.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return dict((project.settings or {}).get("digital_twin") or {})


@twin_router.post("/rebuild")
async def rebuild_twin(
    project_id: UUID,
    session: AsyncSession = Depends(get_db),
    projects: ProjectService = Depends(_projects),
):
    project = await projects.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return await DigitalTwinService(session).rebuild(project)


@twin_router.post("/simulate")
async def simulate_twin(
    project_id: UUID,
    body: SimulateIn,
    session: AsyncSession = Depends(get_db),
    projects: ProjectService = Depends(_projects),
):
    project = await projects.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return await DigitalTwinService(session).simulate_change(
        project,
        change_summary=body.change_summary,
        affected_paths=body.affected_paths,
    )


@twin_router.post("/adversarial")
async def adversarial_on_text(
    project_id: UUID,
    body: SimulateIn,
    session: AsyncSession = Depends(get_db),
    projects: ProjectService = Depends(_projects),
):
    project = await projects.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    twin = dict((project.settings or {}).get("digital_twin") or {})
    return await AdversarialLab(session).critique(
        project,
        artifact_title="manual critique",
        artifact_text=body.change_summary,
        twin_context=twin,
    )


@patterns_router.get("")
async def list_patterns(session: AsyncSession = Depends(get_db)):
    return {"patterns": await PatternLibrary(session).list_patterns(approved_only=False)}


@patterns_router.post("/propose", status_code=201)
async def propose_pattern(body: PatternProposeIn, session: AsyncSession = Depends(get_db)):
    return await PatternLibrary(session).propose_from_experience(
        title=body.title, summary=body.summary, category=body.category
    )


@patterns_router.post("/{pattern_id}/approve")
async def approve_pattern(pattern_id: UUID, session: AsyncSession = Depends(get_db)):
    row = await PatternLibrary(session).approve_pattern(pattern_id)
    if not row:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return row


@patterns_router.post("/projects/{project_id}/apply")
async def apply_pattern(
    project_id: UUID,
    body: PatternApplyIn,
    session: AsyncSession = Depends(get_db),
    projects: ProjectService = Depends(_projects),
):
    project = await projects.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        return await PatternLibrary(session).apply_to_project(project, body.pattern_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@research_router.get("/experiments")
async def list_experiments(session: AsyncSession = Depends(get_db)):
    return {"experiments": await ResearchLabService(session).list_experiments()}


@research_router.post("/experiments", status_code=201)
async def create_experiment(body: ResearchCreateIn, session: AsyncSession = Depends(get_db)):
    return await ResearchLabService(session).create(
        title=body.title, hypothesis=body.hypothesis, kind=body.kind, config=body.config
    )


@research_router.post("/experiments/{experiment_id}/run")
async def run_experiment(experiment_id: UUID, session: AsyncSession = Depends(get_db)):
    try:
        return await ResearchLabService(session).run(experiment_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@research_router.post("/experiments/{experiment_id}/request-promote")
async def request_promote(experiment_id: UUID, session: AsyncSession = Depends(get_db)):
    try:
        return await ResearchLabService(session).request_promote(experiment_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@research_router.post("/experiments/{experiment_id}/decide-promote")
async def decide_promote(
    experiment_id: UUID,
    body: ResearchPromoteDecideIn,
    session: AsyncSession = Depends(get_db),
):
    try:
        return await ResearchLabService(session).decide_promote(
            experiment_id, approve=body.approve, actor=body.actor
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
