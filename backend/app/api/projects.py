from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deployment.engine import DeploymentEngine
from app.design.engine import DesignEngine
from app.development.engine import DevelopmentEngine
from app.evolution.cycle import EvolutionCycle
from app.proposals.service import ProposalService
from app.quality.engine import QualityEngine
from app.schemas.project import (
    AgentTaskOut,
    ExecutionResultOut,
    FindingOut,
    KnowledgeGraphOut,
    KnowledgeNodeOut,
    ProjectCreate,
    ProjectCreateGit,
    ProjectCreatePath,
    ProjectOut,
    ProposalActionIn,
    ProposalOut,
    RoadmapItemOut,
    RoadmapOut,
    UnderstandingRunOut,
)
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


def _service(session: AsyncSession = Depends(get_db)) -> ProjectService:
    return ProjectService(session)


def _safe_under_home(target: Path) -> Path:
    home = Path.home().resolve()
    resolved = target.expanduser().resolve()
    if home not in resolved.parents and resolved != home:
        raise HTTPException(status_code=400, detail="path_outside_home_forbidden")
    return resolved


@router.get("", response_model=list[ProjectOut])
async def list_projects(service: ProjectService = Depends(_service)):
    return await service.list_projects()


_ROOT_LABELS_AR = {
    "desktop": "سطح المكتب",
    "desktop_onedrive": "سطح المكتب (OneDrive)",
    "documents": "المستندات",
    "downloads": "التنزيلات",
    "home": "المجلد الشخصي",
}


@router.get("/local-roots")
async def local_roots():
    """Suggest common folders on this machine (same host as API) for Open Folder UX."""
    home = Path.home()
    candidates = {
        "desktop": home / "Desktop",
        "desktop_onedrive": home / "OneDrive" / "Desktop",
        "documents": home / "Documents",
        "downloads": home / "Downloads",
        "home": home,
    }
    roots = []
    for key, path in candidates.items():
        if path.exists() and path.is_dir():
            roots.append(
                {
                    "id": key,
                    "path": str(path.resolve()),
                    "label": key,
                    "label_ar": _ROOT_LABELS_AR.get(key, key),
                }
            )
    return {"home": str(home), "roots": roots}


@router.get("/local-list")
async def local_list(path: str = Query(min_length=2)):
    """List folders and files under a path inside the user home (Desktop browser)."""
    try:
        root = _safe_under_home(Path(path))
    except HTTPException:
        raise
    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=404, detail="path_not_found")
    folders: list[dict] = []
    files: list[dict] = []
    try:
        children = sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        for child in children:
            if child.name.startswith("."):
                continue
            if child.is_dir():
                folders.append(
                    {
                        "name": child.name,
                        "path": str(child.resolve()),
                        "type": "dir",
                        "has_git": (child / ".git").exists(),
                        "has_package_json": (child / "package.json").exists(),
                        "has_pyproject": (child / "pyproject.toml").exists(),
                    }
                )
            elif child.is_file():
                try:
                    size = child.stat().st_size
                except OSError:
                    size = 0
                files.append(
                    {
                        "name": child.name,
                        "path": str(child.resolve()),
                        "type": "file",
                        "size": size,
                    }
                )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=f"permission_denied: {exc}") from exc
    parent = root.parent if root != Path.home().resolve() else None
    parent_path = None
    if parent is not None:
        try:
            parent_path = str(_safe_under_home(parent))
        except HTTPException:
            parent_path = None
    return {
        "path": str(root),
        "name": root.name or str(root),
        "parent": parent_path,
        "folders": folders,
        "files": files,
        "entries": folders + files,
    }


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: UUID, service: ProjectService = Depends(_service)):
    project = await service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/from-git", response_model=ProjectOut, status_code=201)
async def create_from_git(payload: ProjectCreateGit, service: ProjectService = Depends(_service)):
    try:
        return await service.create_from_git(
            name=payload.name,
            git_url=str(payload.git_url),
            description=payload.description,
            owner_email=str(payload.owner_email) if payload.owner_email else None,
            slug=payload.slug,
            branch=payload.branch,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Git intake failed: {exc}") from exc


@router.post("/from-path", response_model=ProjectOut, status_code=201)
async def create_from_path(payload: ProjectCreatePath, service: ProjectService = Depends(_service)):
    try:
        return await service.create_from_path(
            name=payload.name,
            local_path=payload.local_path,
            description=payload.description,
            owner_email=str(payload.owner_email) if payload.owner_email else None,
            slug=payload.slug,
        )
    except (ValueError, FileNotFoundError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/blank", response_model=ProjectOut, status_code=201)
async def create_blank(payload: ProjectCreate, service: ProjectService = Depends(_service)):
    try:
        return await service.create_blank(
            name=payload.name,
            description=payload.description,
            owner_email=str(payload.owner_email) if payload.owner_email else None,
            slug=payload.slug,
            local_path=payload.local_path,
        )
    except (ValueError, FileNotFoundError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{project_id}/understand", response_model=UnderstandingRunOut)
async def understand_project(project_id: UUID, service: ProjectService = Depends(_service)):
    project = await service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        result = await service.run_understanding(project_id)
        return UnderstandingRunOut(**result)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{project_id}/knowledge", response_model=list[KnowledgeNodeOut])
async def project_knowledge(
    project_id: UUID,
    memory_layer: str | None = Query(default=None),
    kind: str | None = Query(default=None),
    category: str | None = Query(default=None),
    service: ProjectService = Depends(_service),
):
    project = await service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    nodes = await service.list_knowledge(
        project_id,
        memory_layer=memory_layer,
        kind=kind,
        category=category,
    )
    return [
        KnowledgeNodeOut(
            id=n.id,
            memory_layer=n.memory_layer,
            category=n.category,
            kind=n.kind.value,
            title=n.title,
            content=n.content,
            confidence=n.confidence,
            source_type=n.source_type,
            source_path=n.source_path,
            evidence=n.evidence,
            is_stale=n.is_stale,
            created_at=n.created_at,
        )
        for n in nodes
    ]


@router.get("/{project_id}/knowledge-graph", response_model=KnowledgeGraphOut)
async def project_knowledge_graph(project_id: UUID, service: ProjectService = Depends(_service)):
    project = await service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    snapshot = await service.knowledge_graph(project_id)
    return KnowledgeGraphOut(**snapshot)


@router.get("/{project_id}/tasks", response_model=list[AgentTaskOut])
async def project_tasks(project_id: UUID, service: ProjectService = Depends(_service)):
    project = await service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    tasks = await service.list_tasks(project_id)
    return [
        AgentTaskOut(
            id=t.id,
            department=t.department.value,
            agent_name=t.agent_name,
            objective=t.objective,
            status=t.status.value,
            model_used=t.model_used,
            parent_task_id=t.parent_task_id,
            output_payload=t.output_payload or {},
            error_message=t.error_message,
            started_at=t.started_at,
            finished_at=t.finished_at,
            created_at=t.created_at,
        )
        for t in tasks
    ]


@router.get("/{project_id}/roadmap", response_model=RoadmapOut)
async def project_roadmap(project_id: UUID, service: ProjectService = Depends(_service)):
    project = await service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    roadmap = await service.get_active_roadmap(project_id)
    if not roadmap:
        raise HTTPException(status_code=404, detail="No active roadmap yet — run understanding first")
    items = sorted(roadmap.items or [], key=lambda i: i.sort_order)
    return RoadmapOut(
        id=roadmap.id,
        version=roadmap.version,
        title=roadmap.title,
        vision=roadmap.vision,
        status=roadmap.status.value,
        summary=roadmap.summary or {},
        autonomous=roadmap.autonomous,
        generated_by=roadmap.generated_by,
        created_at=roadmap.created_at,
        items=[
            RoadmapItemOut(
                id=i.id,
                title=i.title,
                description=i.description,
                rationale=i.rationale,
                goal=i.goal,
                category=i.category,
                priority=i.priority,
                complexity=i.complexity,
                impact_score=i.impact_score,
                risk_score=i.risk_score,
                status=i.status.value,
                affected_parts=i.affected_parts or [],
                dependencies=i.dependencies or [],
                risks=i.risks,
                acceptance_criteria=i.acceptance_criteria,
                sort_order=i.sort_order,
            )
            for i in items
        ],
    )


def _proposal_out(p) -> ProposalOut:
    return ProposalOut(
        id=p.id,
        title=p.title,
        problem=p.problem,
        proposal=p.proposal,
        rationale=p.rationale,
        impact=p.impact,
        risks=p.risks,
        acceptance_criteria=p.acceptance_criteria,
        priority=p.priority,
        complexity=p.complexity,
        status=p.status.value,
        category=p.category,
        affected_parts=p.affected_parts or [],
        dependencies=p.dependencies or [],
        origin=p.origin,
        revision_notes=p.revision_notes,
        user_request=p.user_request,
        roadmap_item_id=p.roadmap_item_id,
        created_at=p.created_at,
        approved_at=p.approved_at,
    )


@router.get("/{project_id}/proposals", response_model=list[ProposalOut])
async def list_proposals(
    project_id: UUID,
    status: str | None = Query(default=None),
    service: ProjectService = Depends(_service),
    session: AsyncSession = Depends(get_db),
):
    if not await service.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    rows = await ProposalService(session).list_proposals(project_id, status=status)
    return [_proposal_out(p) for p in rows]


@router.post("/{project_id}/proposals/{proposal_id}/approve", response_model=ProposalOut)
async def approve_proposal(
    project_id: UUID,
    proposal_id: UUID,
    service: ProjectService = Depends(_service),
    session: AsyncSession = Depends(get_db),
):
    if not await service.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        proposal = await ProposalService(session).approve(project_id, proposal_id)
        await session.commit()
        return _proposal_out(proposal)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{project_id}/proposals/{proposal_id}/reject", response_model=ProposalOut)
async def reject_proposal(
    project_id: UUID,
    proposal_id: UUID,
    payload: ProposalActionIn,
    service: ProjectService = Depends(_service),
    session: AsyncSession = Depends(get_db),
):
    if not await service.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        proposal = await ProposalService(session).reject(project_id, proposal_id, payload.notes)
        await session.commit()
        return _proposal_out(proposal)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{project_id}/proposals/{proposal_id}/revise", response_model=ProposalOut)
async def revise_proposal(
    project_id: UUID,
    proposal_id: UUID,
    payload: ProposalActionIn,
    service: ProjectService = Depends(_service),
    session: AsyncSession = Depends(get_db),
):
    if not await service.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        proposal = await ProposalService(session).request_revision(
            project_id, proposal_id, payload.notes or "Revision requested"
        )
        await session.commit()
        return _proposal_out(proposal)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{project_id}/proposals/{proposal_id}/execute",
    response_model=ExecutionResultOut,
)
async def execute_proposal(
    project_id: UUID,
    proposal_id: UUID,
    service: ProjectService = Depends(_service),
    session: AsyncSession = Depends(get_db),
):
    """Apply an approved proposal on an isolated Git branch. Never merges."""
    project = await service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        result = await DevelopmentEngine(session).execute_proposal(project, proposal_id)
        return ExecutionResultOut(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post(
    "/{project_id}/proposals/{proposal_id}/merge",
    response_model=ExecutionResultOut,
)
async def merge_proposal(
    project_id: UUID,
    proposal_id: UUID,
    service: ProjectService = Depends(_service),
    session: AsyncSession = Depends(get_db),
):
    """Human-gated merge of an executed proposal branch into main."""
    project = await service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        result = await DevelopmentEngine(session).merge_proposal(project, proposal_id)
        twin_meta = None
        try:
            from app.venture.twin import DigitalTwinService

            twin_meta = await DigitalTwinService(session).rebuild(project)
        except Exception:  # noqa: BLE001
            twin_meta = None
        return ExecutionResultOut(
            status=result["status"],
            branch=result.get("branch"),
            merged=True,
            next_step="Merged. Digital twin refresh attempted; continuous evolution may draft follow-ups.",
            applied={"main": result.get("main"), "twin": twin_meta},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/{project_id}/design/run")
async def run_design_engine(
    project_id: UUID,
    brief: str = Query(default=""),
    service: ProjectService = Depends(_service),
    session: AsyncSession = Depends(get_db),
):
    project = await service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        return await DesignEngine(session).run(project, brief=brief, draft_proposal=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/{project_id}/quality/run")
async def run_quality_engine(
    project_id: UUID,
    focus: str = Query(default="full"),
    service: ProjectService = Depends(_service),
    session: AsyncSession = Depends(get_db),
):
    project = await service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        return await QualityEngine(session).run(project, focus=focus, draft_proposal=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/{project_id}/deploy/plan")
async def plan_deploy(
    project_id: UUID,
    target: str = Query(default="staging"),
    service: ProjectService = Depends(_service),
    session: AsyncSession = Depends(get_db),
):
    project = await service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        return await DeploymentEngine(session).plan(project, target=target, draft_proposal=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{project_id}/deploy/confirm")
async def confirm_deploy(
    project_id: UUID,
    target: str = Query(default="staging"),
    proposal_id: UUID | None = Query(default=None),
    provider: str | None = Query(default=None),
    force_simulate: bool = Query(default=True),
    service: ProjectService = Depends(_service),
    session: AsyncSession = Depends(get_db),
):
    project = await service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        return await DeploymentEngine(session).confirm(
            project,
            target=target,
            proposal_id=proposal_id,
            force_simulate=force_simulate,
            provider=provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{project_id}/evolve")
async def run_evolution_cycle(
    project_id: UUID,
    service: ProjectService = Depends(_service),
    session: AsyncSession = Depends(get_db),
):
    """Autonomous understand/quality/draft cycle — never execute/merge/deploy."""
    if not await service.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        return await EvolutionCycle(session).run_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{project_id}/findings", response_model=list[FindingOut])
async def project_findings(
    project_id: UUID,
    category: str | None = Query(default=None),
    kind: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    service: ProjectService = Depends(_service),
):
    project = await service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    findings = await service.list_findings(
        project_id,
        category=category,
        kind=kind,
        severity=severity,
    )
    return [
        FindingOut(
            id=f.id,
            category=f.category,
            kind=f.kind.value,
            severity=f.severity.value,
            status=f.status.value,
            title=f.title,
            description=f.description,
            recommendation=f.recommendation,
            confidence=f.confidence,
            affected_parts=f.affected_parts or [],
            evidence=f.evidence or {},
            source_agent=f.source_agent,
            fingerprint=f.fingerprint,
            created_at=f.created_at,
        )
        for f in findings
    ]
