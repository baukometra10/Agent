from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.chat.agent import ChatAgentService
from app.config import Settings
from app.db.base import Base
from app.db.models import ProposalStatus
from app.proposals.service import ProposalService
from app.services.project_service import ProjectService


@pytest.mark.asyncio
async def test_auto_proposals_and_approve_flow(tmp_path: Path, monkeypatch):
    sample = tmp_path / "sample"
    sample.mkdir()
    (sample / "main.py").write_text(
        "from fastapi import FastAPI\napp=FastAPI()\n@app.get('/x')\ndef x():\n return 1\n",
        encoding="utf-8",
    )
    workspaces = tmp_path / "workspaces"
    monkeypatch.setenv("WORKSPACES_ROOT", str(workspaces))
    from app.config import get_settings

    get_settings.cache_clear()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        service = ProjectService(session, settings=Settings(workspaces_root=workspaces))
        project = await service.create_from_path(
            name="Shop", local_path=str(sample), slug="shop-p7"
        )
        result = await service.run_understanding(project.id)
        assert "proposals" in result

        proposals = await ProposalService(session).list_proposals(project.id)
        # May be zero if no high-priority findings; force draft via chat path below
        chat = ChatAgentService(session)
        sess = await chat.create_session(project.id, title="Dev")
        reply = await chat.chat(project.id, sess.id, "أضف endpoint للصحة في main.py")
        assert reply["proposal"] is not None
        assert "draft_change_proposal" in reply["tools_used"]

        proposal_id = reply["proposal"]["proposal_id"]
        from uuid import UUID

        approved = await ProposalService(session).approve(project.id, UUID(proposal_id))
        await session.commit()
        assert approved.status == ProposalStatus.approved

    await engine.dispose()
    get_settings.cache_clear()
