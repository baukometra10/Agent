from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.db.base import Base
from app.services.project_service import ProjectService


@pytest.mark.asyncio
async def test_understanding_builds_knowledge_graph(tmp_path: Path, monkeypatch):
    sample = tmp_path / "sample"
    sample.mkdir()
    (sample / "README.md").write_text(
        "# Inventory API\n\nManage stock for warehouse managers.\n",
        encoding="utf-8",
    )
    (sample / "main.py").write_text(
        """
from fastapi import FastAPI
app = FastAPI()

@app.get("/items")
def list_items():
    return []
""",
        encoding="utf-8",
    )
    (sample / "Service.java").write_text(
        "public class Service { public void run() {} }\n",
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
            name="Inventory",
            local_path=str(sample),
            slug="inventory",
        )
        result = await service.run_understanding(project.id)
        assert result["knowledge_written"] >= 1
        assert result["knowledge_graph"]["nodes_written"] >= 1

        graph = await service.knowledge_graph(project.id)
        assert graph["layers"]["architecture"] >= 1 or graph["layers"]["project"] >= 1
        assert isinstance(graph["edges"], list)

        facts = await service.list_knowledge(project.id, kind="fact")
        assert facts

    await engine.dispose()
    get_settings.cache_clear()
