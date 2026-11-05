"""Rapid Learning System + Multi-Agent Learning Lab APIs."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.learning.rapid_system import get_rapid_learning_system

router = APIRouter(prefix="/system/learning", tags=["rapid-learning"])


class DisagreementBody(BaseModel):
    prompt: str = ""
    answers: list[dict] = Field(default_factory=list)
    winner: dict | None = None
    evidence: dict | None = None


class MultiAgentBody(BaseModel):
    task: str = Field(min_length=3)
    artifacts: dict | None = None


class ExecutionVerifiedBody(BaseModel):
    patch_summary: str = Field(min_length=3)
    tests_ok: bool = False
    sandbox_ok: bool = False
    error_log: str = ""
    repair_notes: str = ""
    promote: bool = True


@router.get("/rapid")
async def rapid_blueprint():
    return get_rapid_learning_system().blueprint()


@router.post("/rapid/cycle")
async def rapid_cycle():
    return await get_rapid_learning_system().run_full_cycle()


@router.post("/rapid/competitive")
async def rapid_competitive():
    return await get_rapid_learning_system().run_competitive_snapshot()


@router.post("/rapid/disagreement")
async def rapid_disagreement(body: DisagreementBody):
    return get_rapid_learning_system().record_teacher_disagreement(
        prompt=body.prompt,
        answers=body.answers,
        winner=body.winner,
        evidence=body.evidence,
    )


@router.post("/lab/multi-agent")
async def multi_agent_lab(body: MultiAgentBody):
    return get_rapid_learning_system().run_multi_agent_lab(
        task=body.task, artifacts=body.artifacts
    )


@router.post("/lab/execution-verified")
async def execution_verified(body: ExecutionVerifiedBody):
    return get_rapid_learning_system().record_execution_verified(
        patch_summary=body.patch_summary,
        tests_ok=body.tests_ok,
        sandbox_ok=body.sandbox_ok,
        error_log=body.error_log,
        repair_notes=body.repair_notes,
        promote=body.promote,
    )
