"""Self-maintenance APIs — platform heals itself; never writes project originals."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.maintain import get_self_maintenance

router = APIRouter(prefix="/system/maintain", tags=["maintain"])


class MaintainRunBody(BaseModel):
    climb_if_low: bool = Field(default=True)


@router.get("")
async def maintain_status():
    return get_self_maintenance().status()


@router.post("/run")
async def maintain_run(body: MaintainRunBody | None = None):
    body = body or MaintainRunBody()
    return await get_self_maintenance().run(climb_if_low=body.climb_if_low)
