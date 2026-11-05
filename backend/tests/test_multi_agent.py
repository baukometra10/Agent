from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.base import AgentSpec
from app.agents.critic import IndependentCriticAgent
from app.agents.runtime import AgentRuntime, PermissionError
from app.config import Settings
from app.db.base import Base
from app.db.models import AgentDepartment
from app.gateway.router import ModelRole
from app.services.project_service import ProjectService


@pytest.mark.asyncio
async def test_runtime_permission_blocks_self_approve():
    runtime = AgentRuntime()
    bad = AgentSpec(
        name="BadAgent",
        department=AgentDepartment.development,
        description="should fail",
        model_role=ModelRole.coding,
        can_self_approve=True,
    )
    with pytest.raises(PermissionError):
        runtime.assert_allowed(bad)


@pytest.mark.asyncio
async def test_critic_flags_unverified_heavy_package():
    critic = IndependentCriticAgent()
    result = await critic.run(
        {
            "knowledge": [
                {"kind": "unverified", "title": "a", "confidence": 0.2},
                {"kind": "unverified", "title": "b", "confidence": 0.2},
                {"kind": "unverified", "title": "c", "confidence": 0.2},
                {"kind": "unverified", "title": "d", "confidence": 0.2},
                {"kind": "fact", "title": "e", "confidence": 0.9, "evidence": {}},
            ],
            "specialist_reports": [],
            "intelligence": {"business": {}},
        }
    )
    assert result.success
    assert result.needs_human is True
    assert result.evidence.get("approved") is False


@pytest.mark.asyncio
async def test_multi_agent_understanding_creates_specialist_tasks(tmp_path: Path, monkeypatch):
    sample = tmp_path / "sample"
    sample.mkdir()
    (sample / "README.md").write_text("# Shop\n\nOrders for customers.\n", encoding="utf-8")
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
            name="Shop", local_path=str(sample), slug="shop"
        )
        result = await service.run_understanding(project.id)
        assert "multi_agent" in result
        assert len(result["multi_agent"]["specialists"]) >= 5
        tasks = await service.list_tasks(project.id)
        names = {t.agent_name for t in tasks}
        assert "MasterOrchestrator" in names
        assert "IndependentCritic" in names
        assert "SoftwareArchitect" in names
        assert any(t.department == AgentDepartment.critic for t in tasks)

    await engine.dispose()
    get_settings.cache_clear()
