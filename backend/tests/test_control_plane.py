from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings, get_settings
from app.control_plane.service import ControlPlaneService
from app.db.base import Base
from app.services.project_service import ProjectService


@pytest.mark.asyncio
async def test_fleet_and_blank_project(tmp_path: Path, monkeypatch):
    workspaces = tmp_path / "workspaces"
    monkeypatch.setenv("WORKSPACES_ROOT", str(workspaces))
    get_settings.cache_clear()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        service = ProjectService(session, settings=Settings(workspaces_root=workspaces))
        a = await service.create_blank(name="Alpha Fleet", slug="alpha-fleet")
        b = await service.create_blank(name="Beta Fleet", slug="beta-fleet")
        assert a.isolation_namespace != b.isolation_namespace
        assert a.workspace_path != b.workspace_path

        fleet = await ControlPlaneService(session).fleet()
        assert fleet["totals"]["projects"] == 2
        assert "isolation_guarantee" in fleet
        slugs = {p["slug"] for p in fleet["projects"]}
        assert slugs == {"alpha-fleet", "beta-fleet"}

    await engine.dispose()
    get_settings.cache_clear()
