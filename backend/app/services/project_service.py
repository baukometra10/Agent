from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import run_project_understanding
from app.config import Settings, get_settings
from app.analysis.store import AnalysisStore
from app.autonomy import DEFAULT_AUTONOMY
from app.db.models import AgentTask, AnalysisFinding, KnowledgeNode, Project, ProjectStatus, Roadmap
from app.intelligence.intake import ingest_git_repo, ingest_local_path
from app.knowledge.graph import KnowledgeGraphService
from app.planning.store import PlanningStore
from app.security.isolation import (
    bind_local_folder,
    default_user_projects_root,
    ensure_project_isolation,
)


class ProjectService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    async def list_projects(self) -> list[Project]:
        result = await self.session.execute(select(Project).order_by(Project.created_at.desc()))
        return list(result.scalars().all())

    async def get_project(self, project_id: UUID) -> Project | None:
        result = await self.session.execute(select(Project).where(Project.id == project_id))
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Project | None:
        result = await self.session.execute(select(Project).where(Project.slug == slug))
        return result.scalar_one_or_none()

    async def create_from_git(
        self,
        *,
        name: str,
        git_url: str,
        description: str | None = None,
        owner_email: str | None = None,
        slug: str | None = None,
        branch: str | None = None,
    ) -> Project:
        isolation = ensure_project_isolation(name=name, settings=self.settings, slug=slug)
        if await self.get_by_slug(isolation.project_slug):
            raise ValueError(f"Project slug already exists: {isolation.project_slug}")

        settings: dict = {"autonomy": dict(DEFAULT_AUTONOMY)}
        if branch:
            settings["branch"] = branch
        project = Project(
            slug=isolation.project_slug,
            name=name,
            description=description,
            status=ProjectStatus.ingesting,
            source_type="git",
            source_uri=git_url,
            workspace_path=str(isolation.workspace_path),
            isolation_namespace=isolation.namespace,
            owner_email=owner_email,
            settings=settings,
        )
        self.session.add(project)
        await self.session.flush()

        ingest_git_repo(isolation, git_url, branch=branch)
        project.status = ProjectStatus.created
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def get_by_source_uri(self, source_uri: str) -> Project | None:
        result = await self.session.execute(
            select(Project).where(Project.source_uri == source_uri).order_by(Project.created_at.desc())
        )
        return result.scalars().first()

    async def create_from_path(
        self,
        *,
        name: str,
        local_path: str,
        description: str | None = None,
        owner_email: str | None = None,
        slug: str | None = None,
    ) -> Project:
        """Open a real folder on the user's machine — no copy into Spixa storage."""
        source = Path(local_path).expanduser().resolve()
        existing = await self.get_by_source_uri(str(source))
        if existing and Path(existing.workspace_path).resolve() == source:
            return existing

        isolation = bind_local_folder(
            name=name,
            local_path=source,
            settings=self.settings,
            slug=slug,
        )
        if await self.get_by_slug(isolation.project_slug):
            # Same name, different folder — uniquify slug
            isolation = bind_local_folder(
                name=f"{name}-{isolation.namespace[-6:]}",
                local_path=source,
                settings=self.settings,
                slug=None,
            )

        project = Project(
            slug=isolation.project_slug,
            name=name,
            description=description,
            status=ProjectStatus.ingesting,
            source_type="path",
            source_uri=str(source),
            workspace_path=str(isolation.workspace_path),
            isolation_namespace=isolation.namespace,
            owner_email=owner_email,
            settings={
                "autonomy": dict(DEFAULT_AUTONOMY),
                "bound_local": True,
                "bind_mode": "live_folder",
            },
        )
        self.session.add(project)
        await self.session.flush()

        ingest_local_path(isolation, source, bind=True)
        project.status = ProjectStatus.created
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def create_blank(
        self,
        *,
        name: str,
        description: str | None = None,
        owner_email: str | None = None,
        slug: str | None = None,
        local_path: str | None = None,
    ) -> Project:
        """Create a new project folder on Desktop (local) or WORKSPACES_ROOT (cloud)."""
        from slugify import slugify

        project_slug = slug or slugify(name, max_length=80)
        use_cloud_root = bool(self.settings.cloud_workspaces) or (
            str(self.settings.app_env or "").lower() == "production" and not local_path
        )

        if local_path:
            isolation = bind_local_folder(
                name=name,
                local_path=Path(local_path).expanduser(),
                settings=self.settings,
                slug=project_slug,
                create_if_missing=True,
            )
            bound_local = True
        elif use_cloud_root:
            # Railway/cloud: persist under WORKSPACES_ROOT (/data/workspaces)
            isolation = ensure_project_isolation(
                name=name, settings=self.settings, slug=project_slug
            )
            bound_local = False
        else:
            folder = default_user_projects_root() / project_slug
            isolation = bind_local_folder(
                name=name,
                local_path=folder,
                settings=self.settings,
                slug=project_slug,
                create_if_missing=True,
            )
            bound_local = True

        if await self.get_by_slug(isolation.project_slug):
            raise ValueError(f"Project slug already exists: {isolation.project_slug}")

        root = isolation.workspace_path
        readme = root / "README.md"
        if not readme.exists():
            readme.write_text(
                f"# {name}\n\n"
                "مشروع Spixa — الملفات هنا على جهازك. أي كود يُنشأ من المحرّر يُحفظ في هذا المجلد.\n",
                encoding="utf-8",
            )
        main_py = root / "main.py"
        if not main_py.exists():
            main_py.write_text(
                '"""Starter module — lives on your machine."""\n\n'
                "def health() -> dict:\n"
                '    return {"status": "ok"}\n',
                encoding="utf-8",
            )

        project = Project(
            slug=isolation.project_slug,
            name=name,
            description=description,
            status=ProjectStatus.created,
            source_type="blank",
            source_uri=str(root),
            workspace_path=str(root),
            isolation_namespace=isolation.namespace,
            owner_email=owner_email,
            settings={
                "autonomy": dict(DEFAULT_AUTONOMY),
                "bound_local": bound_local,
                "bind_mode": "live_folder" if bound_local else "cloud_workspace",
            },
        )
        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def list_knowledge(
        self,
        project_id: UUID,
        *,
        memory_layer: str | None = None,
        kind: str | None = None,
        category: str | None = None,
    ) -> list[KnowledgeNode]:
        kg = KnowledgeGraphService(self.session)
        return await kg.list_nodes(
            project_id,
            memory_layer=memory_layer,
            kind=kind,
            category=category,
            include_stale=False,
        )

    async def knowledge_graph(self, project_id: UUID) -> dict:
        kg = KnowledgeGraphService(self.session)
        return await kg.graph_snapshot(project_id)

    async def run_understanding(self, project_id: UUID) -> dict:
        return await run_project_understanding(self.session, project_id)

    async def list_tasks(self, project_id: UUID, limit: int = 100) -> list[AgentTask]:
        result = await self.session.execute(
            select(AgentTask)
            .where(AgentTask.project_id == project_id)
            .order_by(AgentTask.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_findings(
        self,
        project_id: UUID,
        *,
        category: str | None = None,
        kind: str | None = None,
        severity: str | None = None,
    ) -> list[AnalysisFinding]:
        store = AnalysisStore(self.session)
        return await store.list_findings(
            project_id,
            category=category,
            kind=kind,
            severity=severity,
        )

    async def get_active_roadmap(self, project_id: UUID) -> Roadmap | None:
        return await PlanningStore(self.session).get_active_roadmap(project_id)
