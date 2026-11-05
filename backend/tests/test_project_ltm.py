from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.chat.agent import ChatAgentService
from app.config import Settings
from app.db.base import Base
from app.gateway.intelligent_router import default_confidence, IntelligentModelRouter
from app.gateway.types import ModelResponse, ModelRole
from app.memory import ProjectLongTermMemory
from app.services.project_service import ProjectService


@pytest.mark.asyncio
async def test_ltm_retains_every_word_and_isolates_projects(tmp_path: Path, monkeypatch):
    a = tmp_path / "proj-a"
    b = tmp_path / "proj-b"
    a.mkdir()
    b.mkdir()
    (a / "main.py").write_text("print('a')\n", encoding="utf-8")
    (b / "main.py").write_text("print('b')\n", encoding="utf-8")
    workspaces = tmp_path / "workspaces"
    monkeypatch.setenv("WORKSPACES_ROOT", str(workspaces))
    from app.config import get_settings

    get_settings.cache_clear()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        svc = ProjectService(session, settings=Settings(workspaces_root=workspaces))
        pa = await svc.create_from_path(name="Alpha", local_path=str(a), slug="alpha-ltm")
        pb = await svc.create_from_path(name="Beta", local_path=str(b), slug="beta-ltm")

        ltm = ProjectLongTermMemory(session)
        await ltm.remember_utterance(
            pa.id, role="user", content="احفظ دائماً استخدم TypeScript في هذا المشروع"
        )
        await ltm.remember_utterance(pb.id, role="user", content="استخدم Python فقط هنا")
        await session.commit()

        ra = await ltm.recall(pa.id)
        rb = await ltm.recall(pb.id)

        assert ra["binding"]["project_id"] == str(pa.id)
        assert rb["binding"]["project_id"] == str(pb.id)
        assert ra["binding"]["workspace_path"] != rb["binding"]["workspace_path"]
        assert any("TypeScript" in (t.get("content") or "") for t in ra["transcript"])
        assert not any("TypeScript" in (t.get("content") or "") for t in rb["transcript"])
        assert any("Python" in (t.get("content") or "") for t in rb["transcript"])
        assert ra["standing_instructions"]  # "احفظ دائماً" → durable instruction
        assert not any("TypeScript" in (s.get("content") or "") for s in rb["standing_instructions"])

        # Transcript files live under each workspace only
        assert (Path(pa.workspace_path) / "memory" / "transcript.jsonl").exists()
        assert (Path(pb.workspace_path) / "memory" / "transcript.jsonl").exists()

        chat = ChatAgentService(session)
        sess = await chat.create_session(pa.id, title="LTM")
        out = await chat.chat(pa.id, sess.id, "ما هي التعليمات الثابتة؟")
        assert out.get("memory_binding")
        assert out["memory_binding"]["project_id"] == str(pa.id)
        recalled = await ltm.recall(pa.id, session_id=sess.id)
        assert recalled["counts"]["transcript"] >= 2  # user instruction + chat turns

    await engine.dispose()
    get_settings.cache_clear()


def test_promoted_specialty_boosts_confidence_and_blocks_escalate(monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("PREFER_PROMOTED_INTERNAL", "true")
    monkeypatch.setenv("PROMOTED_NO_ESCALATE", "true")
    get_settings.cache_clear()

    def fake_catalog(_settings):
        return [
            {
                "id": "internal/coding",
                "role": "coding",
                "adapter": "lora-coding",
                "description": "x",
                "ready": True,
                "adapter_promoted": True,
            }
        ]

    monkeypatch.setattr("app.gateway.internal.family_catalog", fake_catalog)

    resp = ModelResponse(
        role=ModelRole.coding,
        model_id="internal/coding",
        content="Implement the endpoint with FastAPI and tests.",
        simulated=False,
    )
    conf = default_confidence(resp, {"prefer_promoted": True})
    assert conf >= 0.7

    router = IntelligentModelRouter()
    escalate, score = router.should_escalate(resp, metadata={"prefer_promoted": True})
    assert escalate is False
    assert score >= 0.55
    get_settings.cache_clear()
