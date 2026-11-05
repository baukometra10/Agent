from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.control_plane.service import ControlPlaneService
from app.db.session import get_db

router = APIRouter(prefix="/control-plane", tags=["control-plane"])


@router.get("/fleet")
async def fleet_overview(session: AsyncSession = Depends(get_db)):
    return await ControlPlaneService(session).fleet()


@router.post("/evolve-all")
async def evolve_all(
    only_ready: bool = Query(default=True),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    """Sequential isolated evolution cycles across the fleet."""
    return await ControlPlaneService(session).evolve_fleet(only_ready=only_ready, limit=limit)
