"""Model Development Factory APIs — gated releases."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.factory.orchestrator import get_model_factory
from app.factory.self_improve import SelfImprovementEngine
from app.factory.synthetic import SyntheticDataFactory

router = APIRouter(prefix="/system/factory", tags=["model-factory"])


class CycleBody(BaseModel):
    specialties: list[str] | None = None
    run_synthetic: bool = True
    seed: bool = True
    train: bool = True


class SyntheticBody(BaseModel):
    specialty: str = "coding"
    max_variants: int = Field(default=8, ge=1, le=64)


class EvaluateBody(BaseModel):
    specialty: str = "coding"


class ApproveBody(BaseModel):
    approver: str = "admin"
    force: bool = False  # staging only — bypass maturity gates


class RejectBody(BaseModel):
    reason: str = ""
    rejector: str = "admin"


@router.get("/blueprint")
async def factory_blueprint():
    return get_model_factory().blueprint()


@router.post("/cycle")
async def factory_cycle(body: CycleBody | None = None):
    body = body or CycleBody()
    return await get_model_factory().run_cycle(
        specialties=body.specialties,
        run_synthetic=body.run_synthetic,
        seed=body.seed,
        train=body.train,
    )


@router.post("/synthetic")
async def factory_synthetic(body: SyntheticBody):
    return SyntheticDataFactory().generate(
        specialty=body.specialty, max_variants=body.max_variants
    )


@router.post("/evaluate")
async def factory_evaluate(body: EvaluateBody | None = None):
    body = body or EvaluateBody()
    return await get_model_factory().evaluate(specialty=body.specialty)


@router.post("/self-improve")
async def factory_self_improve():
    return SelfImprovementEngine().propose()


@router.get("/releases")
async def factory_releases(status: str | None = None):
    return {"releases": get_model_factory().list_releases(status=status)}


@router.post("/releases/{release_id}/approve")
async def factory_approve(release_id: str, body: ApproveBody | None = None):
    body = body or ApproveBody()
    out = get_model_factory().approve_release(
        release_id, approver=body.approver, force=body.force
    )
    if not out.get("ok"):
        raise HTTPException(status_code=400, detail=out)
    return out


@router.post("/releases/{release_id}/reject")
async def factory_reject(release_id: str, body: RejectBody | None = None):
    body = body or RejectBody()
    out = get_model_factory().reject_release(
        release_id, reason=body.reason, rejector=body.rejector
    )
    if not out.get("ok"):
        raise HTTPException(status_code=400, detail=out)
    return out


class ProofBody(BaseModel):
    real_train: bool = True
    approve_if_gates_pass: bool = False
    approver: str = "proof_operator"
    max_steps: int | None = Field(default=20, ge=1, le=200)
    label: str = ""


@router.get("/proof/stack")
async def factory_proof_stack():
    from app.factory.proof import probe_train_stack

    return probe_train_stack()


@router.get("/proof/improvement")
async def factory_proof_improvement(specialty: str = "coding"):
    from app.factory.proof import FactoryProofTrack

    return FactoryProofTrack().improvement_report(specialty=specialty)


@router.post("/proof/coding")
async def factory_proof_coding(body: ProofBody | None = None):
    """Practical proof: real LoRA (if stack ready) → eval → factory proposal."""
    from app.factory.proof import FactoryProofTrack

    body = body or ProofBody()
    return await FactoryProofTrack().run_coding_proof(
        real_train=body.real_train,
        approve_if_gates_pass=body.approve_if_gates_pass,
        approver=body.approver,
        max_steps=body.max_steps,
        label=body.label,
    )
