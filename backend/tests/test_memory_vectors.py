import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Project, ProjectStatus
from app.memory.embeddings_store import ProjectEmbeddingsStore, local_embed
from app.memory.project_ltm import ProjectLongTermMemory
from app.security.isolation import make_namespace


@pytest.fixture
async def session(tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.mark.asyncio
async def test_local_embed_stable():
    a = local_embed("hello spixa memory")
    b = local_embed("hello spixa memory")
    assert a == b
    assert len(a) == 128


@pytest.mark.asyncio
async def test_remember_indexes_and_semantic_recall(session, tmp_path):
    ws = tmp_path / "proj"
    ws.mkdir()
    project = Project(
        slug="mem-test",
        name="Mem Test",
        status=ProjectStatus.created,
        source_type="blank",
        source_uri=str(ws),
        workspace_path=str(ws),
        isolation_namespace=make_namespace("mem-test"),
    )
    session.add(project)
    await session.flush()

    ltm = ProjectLongTermMemory(session)
    stored = await ltm.remember_utterance(
        project.id,
        role="user",
        content="Always use TypeScript strict mode in this project.",
    )
    assert stored["stored"] is True
    assert stored.get("embedding", {}).get("ok") is True

    recall = await ltm.recall(project.id)
    assert recall["counts"]["transcript"] >= 1
    assert recall["counts"]["semantic_hits"] >= 1

    stats = await ProjectEmbeddingsStore(session).stats(project.id)
    assert stats["vectors_postgres"] >= 1
    assert stats["chroma_like"] is True
