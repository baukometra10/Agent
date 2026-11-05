from __future__ import annotations

import os
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Force sqlite for isolated unit tests when Postgres is unavailable.
_TEST_DB_PATH = Path.cwd() / "data" / "test-evolve.db"
_TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
TEST_DB = os.getenv("EVOLVE_TEST_DATABASE_URL", f"sqlite+aiosqlite:///{_TEST_DB_PATH.as_posix()}")
os.environ["DATABASE_URL"] = TEST_DB
os.environ.setdefault("WORKSPACES_ROOT", str(Path.cwd() / "data" / "test-workspaces"))
# Never hit live Ollama/OpenAI during unit tests (even if developer .env is wired).
os.environ["INTERNAL_MODEL_BASE_URL"] = ""
os.environ["INTERNAL_MODEL_NAME"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["MODEL_CACHE_ENABLED"] = "false"

from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.gateway.router import reset_model_gateway  # noqa: E402
from app.gateway.intelligent_router import reset_intelligent_router  # noqa: E402

get_settings.cache_clear()
reset_model_gateway()
reset_intelligent_router()


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(TEST_DB, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACES_ROOT", str(tmp_path / "workspaces"))
    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    settings.workspaces_root.mkdir(parents=True, exist_ok=True)

    engine = create_async_engine(TEST_DB, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    app = create_app()

    async def override_get_db():
        async with Session() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    await engine.dispose()
    get_settings.cache_clear()
