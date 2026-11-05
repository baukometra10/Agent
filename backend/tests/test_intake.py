from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.db.base import Base
from app.services.project_service import ProjectService


@pytest.mark.asyncio
async def test_create_from_path_and_understand(tmp_path: Path, monkeypatch):
    sample = tmp_path / "sample"
    sample.mkdir()
    (sample / "main.py").write_text("def hello():\n    return 1\n", encoding="utf-8")
    (sample / "requirements.txt").write_text("fastapi\n", encoding="utf-8")

    workspaces = tmp_path / "workspaces"
    monkeypatch.setenv("WORKSPACES_ROOT", str(workspaces))
    from app.config import get_settings

    get_settings.cache_clear()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        settings = Settings(workspaces_root=workspaces)
        service = ProjectService(session, settings=settings)
        project = await service.create_from_path(
            name="Sample App",
            local_path=str(sample),
            slug="sample-app",
            owner_email="owner@example.com",
        )
        assert "sample-app" in project.isolation_namespace
        # Live bind: workspace_path IS the user's folder (no copy under workspaces/repo)
        assert Path(project.workspace_path).resolve() == sample.resolve()
        assert (Path(project.workspace_path) / "main.py").exists()

        result = await service.run_understanding(project.id)
        assert result["knowledge_written"] >= 1
        assert result["status"] == "ready"

        knowledge = await service.list_knowledge(project.id)
        kinds = {k.kind.value for k in knowledge}
        assert "fact" in kinds or "inference" in kinds

    await engine.dispose()
    get_settings.cache_clear()
