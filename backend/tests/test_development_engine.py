from pathlib import Path

import pytest
from git import Repo
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings, get_settings
from app.db.base import Base
from app.db.models import ProposalStatus
from app.development.engine import DevelopmentEngine
from app.proposals.service import ProposalService
from app.services.project_service import ProjectService


@pytest.mark.asyncio
async def test_execute_approved_proposal_on_branch_then_merge(tmp_path: Path, monkeypatch):
    sample = tmp_path / "sample"
    sample.mkdir()
    (sample / "main.py").write_text("print('ok')\n", encoding="utf-8")
    workspaces = tmp_path / "workspaces"
    monkeypatch.setenv("WORKSPACES_ROOT", str(workspaces))
    get_settings.cache_clear()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        service = ProjectService(session, settings=Settings(workspaces_root=workspaces))
        project = await service.create_from_path(
            name="DevEngine", local_path=str(sample), slug="dev-engine-p8"
        )

        proposals = ProposalService(session)
        proposal = await proposals.create_from_user_request(
            project.id,
            title="Document health endpoint plan",
            user_request="Add docs for a health endpoint change",
            rationale="Track intended change before code edits",
            proposal_text="Create docs/evolve note describing the health endpoint work",
            affected_parts=["docs/"],
            category="documentation",
            priority=70,
        )
        await session.commit()

        with pytest.raises(ValueError, match="approved"):
            await DevelopmentEngine(session).execute_proposal(project, proposal.id)

        await proposals.approve(project.id, proposal.id)
        await session.commit()

        result = await DevelopmentEngine(session).execute_proposal(project, proposal.id)
        assert result["merged"] is False
        assert result["status"] == ProposalStatus.awaiting_merge.value
        assert result["branch"].startswith("evolve/")
        assert result["commit"]
        assert result["applied"]["files"]
        assert all(
            f.startswith("docs/") or f.startswith("apps/") for f in result["applied"]["files"]
        )
        assert result["review"]["approved"] is True
        assert result["sandbox"]["allowed"] is False

        repo = Repo(Path(project.workspace_path) / "repo")
        assert result["branch"] in [h.name for h in repo.heads]
        for rel in result["applied"]["files"]:
            assert (Path(project.workspace_path) / "repo" / rel).is_file()

        refreshed = await proposals.get(project.id, proposal.id)
        assert refreshed is not None
        assert refreshed.status == ProposalStatus.awaiting_merge

        merged = await DevelopmentEngine(session).merge_proposal(project, proposal.id)
        assert merged["status"] == "merged"
        refreshed = await proposals.get(project.id, proposal.id)
        assert refreshed is not None
        assert refreshed.status == ProposalStatus.merged

        main = "main" if "main" in [h.name for h in repo.heads] else "master"
        repo.git.checkout(main)
        for rel in result["applied"]["files"]:
            assert (Path(project.workspace_path) / "repo" / rel).is_file()

    await engine.dispose()
    get_settings.cache_clear()
