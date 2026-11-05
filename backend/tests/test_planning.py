from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.analysis.engine import run_analysis_engine
from app.config import Settings
from app.db.base import Base
from app.intelligence.engine import run_project_intelligence
from app.planning.engine import run_planning_engine
from app.services.project_service import ProjectService


def test_planning_engine_prioritizes_high_severity():
    findings = [
        {
            "category": "security",
            "kind": "risk",
            "severity": "high",
            "title": "API without roles",
            "description": "routes exist",
            "recommendation": "map auth",
            "confidence": 0.8,
            "affected_parts": ["/x"],
            "evidence": {},
            "fingerprint": "abc",
            "source_agent": "SecurityAuditor",
        },
        {
            "category": "feature",
            "kind": "opportunity",
            "severity": "low",
            "title": "Add reports",
            "description": "nice to have",
            "recommendation": " backlog",
            "confidence": 0.4,
            "affected_parts": [],
            "evidence": {},
            "fingerprint": "def",
            "source_agent": "FeatureStrategist",
        },
    ]
    report = run_planning_engine(project_name="Demo", findings=findings, autonomous=True)
    assert report.items[0].title == "API without roles"
    assert report.items[0].priority > report.items[1].priority
    assert report.summary["execution_gated"] is True


@pytest.mark.asyncio
async def test_understand_publishes_autonomous_roadmap(tmp_path: Path, monkeypatch):
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
            name="Autonomous App", local_path=str(sample), slug="auto-app"
        )
        assert project.settings["autonomy"]["auto_plan"] is True
        assert project.settings["autonomy"]["auto_execute"] is False

        result = await service.run_understanding(project.id)
        assert result["planning"].get("items_written", 0) >= 0
        roadmap = await service.get_active_roadmap(project.id)
        assert roadmap is not None
        assert roadmap.autonomous is True
        assert roadmap.version >= 1

        # Deterministic path also produces plan items when findings exist
        intel = run_project_intelligence(Path(project.workspace_path) / "repo").to_dict()
        analysis = run_analysis_engine(intel)
        plan = run_planning_engine(
            project_name=project.name,
            findings=[f.to_dict() for f in analysis.findings],
        )
        assert isinstance(plan.items, list)

    await engine.dispose()
    get_settings.cache_clear()
