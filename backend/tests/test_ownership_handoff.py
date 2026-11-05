from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings, get_settings
from app.db.base import Base
from app.memory import ProjectLongTermMemory
from app.distillation.engine import reset_distillation_engine
from app.ownership.handoff import OwnershipHandoff, reset_ownership_handoff
from app.services.project_service import ProjectService


def test_readiness_map_and_distill_pair(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FAST_HANDOFF_ENABLED", "true")
    monkeypatch.setenv("DISTILLATION_DATA_ROOT", str(tmp_path / "distill"))
    monkeypatch.setenv("LEARNING_DATA_ROOT", str(tmp_path / "learning"))
    get_settings.cache_clear()
    reset_ownership_handoff()
    reset_distillation_engine()

    settings = Settings(
        fast_handoff_enabled=True,
        distillation_data_root=tmp_path / "distill",
        learning_data_root=tmp_path / "learning",
        distillation_enabled=True,
    )
    handoff = OwnershipHandoff(settings=settings)
    status = handoff.readiness_map()
    assert status["specialties_total"] == 5
    assert "specialties" in status
    assert status["next_action"] in {
        "retire_teachers_for_ready_specialties",
        "grow_datasets_and_promote",
    }

    rejected = handoff.distill_pair(
        user_text="hi",
        assistant_text="ok",
    )
    assert rejected["accepted"] is False

    accepted = handoff.distill_pair(
        user_text="أضف endpoint للصحة",
        assistant_text=(
            "خطة: أضف مسار GET /health يعيد status=ok. "
            "المقترح بانتظار موافقة بشرية قبل الدمج."
        ),
        intent="implement",
    )
    assert accepted["accepted"] is True
    assert accepted["specialty"] == "coding"

    full = handoff.status()
    assert full["readiness"]["specialties_total"] == 5
    get_settings.cache_clear()
    reset_ownership_handoff()
    reset_distillation_engine()


@pytest.mark.asyncio
async def test_distill_project_memory_from_ltm(tmp_path: Path, monkeypatch):
    sample = tmp_path / "app"
    sample.mkdir()
    (sample / "main.py").write_text("print(1)\n", encoding="utf-8")
    workspaces = tmp_path / "workspaces"
    monkeypatch.setenv("WORKSPACES_ROOT", str(workspaces))
    get_settings.cache_clear()
    reset_ownership_handoff()
    reset_distillation_engine()

    settings = Settings(
        workspaces_root=workspaces,
        fast_handoff_enabled=True,
        distillation_data_root=tmp_path / "distill",
        learning_data_root=tmp_path / "learning",
        distillation_enabled=True,
    )

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        project = await ProjectService(session, settings=settings).create_from_path(
            name="Handoff", local_path=str(sample), slug="handoff-p22"
        )
        ltm = ProjectLongTermMemory(session)
        await ltm.remember_utterance(
            project.id,
            role="user",
            content="احفظ دائماً استخدم pytest لكل تغيير",
        )
        await ltm.remember_utterance(
            project.id,
            role="user",
            content="اشرح لي الهيكل",
        )
        await ltm.remember_utterance(
            project.id,
            role="assistant",
            content="الهيكل بسيط: main.py نقطة الدخول، والذاكرة معزولة لهذا المشروع فقط.",
        )
        await session.commit()

        report = await OwnershipHandoff(settings=settings).distill_project_memory(
            session, project.id
        )
        assert report["accepted"] >= 1
        assert report["binding"]["project_id"] == str(project.id)

    await engine.dispose()
    get_settings.cache_clear()
    reset_ownership_handoff()
    reset_distillation_engine()
