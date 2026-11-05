from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings, get_settings
from app.db.base import Base
from app.design.engine import DesignEngine
from app.quality.engine import QualityEngine
from app.services.project_service import ProjectService


@pytest.mark.asyncio
async def test_design_and_quality_engines(tmp_path: Path, monkeypatch):
    sample = tmp_path / "sample"
    sample.mkdir()
    (sample / "main.py").write_text("print('x')\n", encoding="utf-8")
    (sample / "app.tsx").write_text("export default function App(){return null}\n", encoding="utf-8")
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
            name="DesignQA", local_path=str(sample), slug="design-qa"
        )

        design = await DesignEngine(session).run(project, brief="حسّن الواجهة", draft_proposal=True)
        assert design["status"] == "drafted"
        assert design["files"]
        assert design["proposal_id"]
        repo = Path(project.workspace_path) / "repo"
        for rel in design["files"]:
            assert (repo / rel).is_file()

        quality = await QualityEngine(session).run(project, focus="full", draft_proposal=True)
        assert quality["status"] == "completed"
        assert quality["findings"]
        assert quality["report"]

    await engine.dispose()
    get_settings.cache_clear()
