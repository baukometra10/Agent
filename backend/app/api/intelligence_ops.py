"""Maturity · Ownership Registry · Independence Mode · Evolution Dashboard."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.intelligence.evolution import evolution_dashboard
from app.maturity.scorecard import get_maturity_board
from app.ownership.independence import IndependenceMode
from app.ownership.registry import get_ownership_registry

router = APIRouter(prefix="/system/intelligence", tags=["spixa-intelligence-ops"])


class HumanAcceptBody(BaseModel):
    specialty: str = Field(min_length=2)
    accepted: bool
    note: str = ""
    actor: str = "expert"


class TaskOutcomeBody(BaseModel):
    specialty: str = Field(min_length=2)
    success: bool
    source: str = "runtime"


class SafetyBody(BaseModel):
    specialty: str = Field(min_length=2)
    safe: bool
    detail: str = ""


@router.get("/maturity")
async def maturity_board():
    return get_maturity_board().board()


@router.get("/maturity/{specialty}")
async def maturity_specialty(specialty: str):
    return get_maturity_board().scorecard(specialty)


@router.post("/maturity/human-acceptance")
async def maturity_human_acceptance(body: HumanAcceptBody):
    return get_maturity_board().record_human_acceptance(
        specialty=body.specialty,
        accepted=body.accepted,
        note=body.note,
        actor=body.actor,
    )


@router.post("/maturity/task-outcome")
async def maturity_task_outcome(body: TaskOutcomeBody):
    return get_maturity_board().record_task_outcome(
        specialty=body.specialty, success=body.success, source=body.source
    )


@router.post("/maturity/safety-event")
async def maturity_safety_event(body: SafetyBody):
    return get_maturity_board().record_safety_event(
        specialty=body.specialty, safe=body.safe, detail=body.detail
    )


@router.get("/ownership-registry")
async def ownership_registry_catalog():
    return get_ownership_registry().catalog()


@router.get("/ownership-registry/{specialty}")
async def ownership_registry_specialty(specialty: str):
    return get_ownership_registry().list_specialty(specialty)


@router.post("/independence/probe")
async def independence_probe():
    return await IndependenceMode().run_probe()


@router.get("/independence/latest")
async def independence_latest():
    from pathlib import Path

    from app.config import get_settings

    path = Path(get_settings().learning_data_root) / "independence" / "latest.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="no_probe_yet")
    import json

    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/evolution")
async def intelligence_evolution():
    return evolution_dashboard()
