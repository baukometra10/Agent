from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.analysis.engine import run_analysis_engine
from app.config import Settings
from app.db.base import Base
from app.intelligence.engine import run_project_intelligence
from app.services.project_service import ProjectService


def test_analysis_engine_flags_missing_purpose_and_api_roles(tmp_path: Path):
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI\napp=FastAPI()\n@app.get('/x')\ndef x():\n return 1\n",
        encoding="utf-8",
    )
    intel = run_project_intelligence(tmp_path).to_dict()
    report = run_analysis_engine(intel)
    cats = {f.category for f in report.findings}
    assert "maintainability" in cats or "security" in cats
    assert report.summary["total"] >= 1


@pytest.mark.asyncio
async def test_understand_persists_findings(tmp_path: Path, monkeypatch):
    sample = tmp_path / "sample"
    sample.mkdir()
    (sample / "main.py").write_text(
        "from fastapi import FastAPI\napp=FastAPI()\n@app.get('/items')\ndef items():\n return []\n",
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
            name="Items API", local_path=str(sample), slug="items-api"
        )
        result = await service.run_understanding(project.id)
        assert "analysis" in result
        findings = await service.list_findings(project.id)
        assert isinstance(findings, list)
        # At minimum analysis summary path ran
        assert result["analysis"]["findings_written"] == len(findings)

    await engine.dispose()
    get_settings.cache_clear()
