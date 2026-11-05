from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    activity,
    agent_ui,
    auth_billing,
    autopilot,
    chat,
    chief,
    control_plane,
    desktop,
    health,
    intelligence_ecosystem,
    intelligence_ops,
    learning_lab,
    maintain,
    memory,
    model_factory,
    ownership,
    projects,
    speech,
    ventures,
    workspace,
)
from app.config import get_settings
from app.db.base import Base
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    from app.autopilot import start_autopilot_loop, stop_autopilot_loop

    settings = get_settings()
    settings.workspaces_root.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    start_autopilot_loop()
    try:
        yield
    finally:
        await stop_autopilot_loop()
        await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description="Spixa by Suppix AI — coding agent + autonomous software evolution",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(speech.router)
    app.include_router(ownership.router)
    app.include_router(intelligence_ecosystem.router)
    app.include_router(intelligence_ops.router)
    app.include_router(learning_lab.router)
    app.include_router(model_factory.router)
    app.include_router(maintain.router)
    app.include_router(auth_billing.router)
    app.include_router(desktop.router)
    app.include_router(autopilot.router)
    app.include_router(chief.router)
    app.include_router(activity.router, prefix="/api")
    app.include_router(control_plane.router, prefix="/api")
    app.include_router(projects.router, prefix="/api")
    app.include_router(workspace.router, prefix="/api")
    app.include_router(memory.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(agent_ui.router, prefix="/api")
    app.include_router(agent_ui.share_router, prefix="/api")
    app.include_router(ventures.router, prefix="/api")
    app.include_router(ventures.twin_router, prefix="/api")
    app.include_router(ventures.patterns_router, prefix="/api")
    app.include_router(ventures.research_router, prefix="/api")
    return app


app = create_app()
