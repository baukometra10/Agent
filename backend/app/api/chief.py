"""Chief Agent APIs — pool status, assign, spawn, saturate demo."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.chief import get_chief_orchestra
from app.agents.chief.orchestra import reset_chief_orchestra
from app.config import get_settings

router = APIRouter(prefix="/system/chief", tags=["chief"])


class AssignBody(BaseModel):
    objective: str = Field(min_length=2)
    agent_role: str = "Specialist"
    specialty: str | None = None
    intent: str | None = None


class SpawnBody(BaseModel):
    specialty: str = "coding"
    reason: str = "manual_spawn"


@router.get("")
async def chief_status():
    settings = get_settings()
    return {
        "enabled": settings.chief_enabled,
        **get_chief_orchestra().status(),
    }


@router.post("/assign")
async def chief_assign(body: AssignBody):
    if not get_settings().chief_enabled:
        raise HTTPException(status_code=400, detail="Chief disabled (CHIEF_ENABLED=false)")
    return await get_chief_orchestra().assign(
        body.objective,
        agent_role=body.agent_role,
        specialty=body.specialty,
        intent=body.intent,
    )


@router.post("/spawn")
async def chief_spawn(body: SpawnBody):
    if not get_settings().chief_enabled:
        raise HTTPException(status_code=400, detail="Chief disabled")
    try:
        worker = await get_chief_orchestra().spawn_worker(body.specialty, reason=body.reason)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "worker": worker.to_dict(), "pool": get_chief_orchestra().status()["pool"]}


@router.post("/demo/saturate")
async def chief_saturate_demo(n: int = 5):
    """Fire N parallel coding tasks so Chief must spawn when bootstrap workers are busy."""
    if not get_settings().chief_enabled:
        raise HTTPException(status_code=400, detail="Chief disabled")
    n = max(1, min(n, get_settings().chief_max_workers))
    chief = get_chief_orchestra()
    jobs = [
        {
            "agent_role": f"DemoWorker-{i}",
            "objective": f"List {i+1} safe refactoring ideas for a FastAPI service. Be terse.",
            "specialty": "coding",
            "intent": "implement",
        }
        for i in range(n)
    ]
    results = await chief.dispatch_many(jobs)
    spawned = sum(1 for r in results if r.get("spawned_worker"))
    return {
        "ok": True,
        "jobs": n,
        "spawned_workers": spawned,
        "results": results,
        "pool": chief.status()["pool"],
    }


@router.post("/reset")
async def chief_reset():
    reset_chief_orchestra()
    return get_chief_orchestra().status()
