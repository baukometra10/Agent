from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings, get_settings
from app.db.base import Base
from app.deployment.engine import DeploymentEngine
from app.evolution.cycle import EvolutionCycle
from app.services.project_service import ProjectService


@pytest.mark.asyncio
async def test_deploy_plan_confirm_and_evolve_cycle(tmp_path: Path, monkeypatch):
    sample = tmp_path / "sample"
    sample.mkdir()
    (sample / "main.py").write_text("print(1)\n", encoding="utf-8")
    (sample / "Dockerfile").write_text("FROM python:3.12\n", encoding="utf-8")
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
            name="ShipIt", local_path=str(sample), slug="ship-it"
        )

        planned = await DeploymentEngine(session).plan(project, target="staging")
        assert planned["status"] == "planned"
        assert planned["confirm_required"] is True
        repo = Path(project.workspace_path) / "repo"
        for rel in planned["files"]:
            assert (repo / rel).is_file()

        confirmed = await DeploymentEngine(session).confirm(
            project, target="staging", force_simulate=True
        )
        assert confirmed["status"] == "simulated_success"
        assert (repo / confirmed["file"]).is_file()

        cycle = await EvolutionCycle(session).run_project(project.id)
        assert cycle["status"] == "completed"
        assert "auto_deploy" in cycle["refused"]

    await engine.dispose()
    get_settings.cache_clear()
