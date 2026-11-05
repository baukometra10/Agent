"""Spixa Proprietary Intelligence Ecosystem blueprint API."""

from __future__ import annotations

from fastapi import APIRouter

from app.intelligence.ecosystem import ecosystem_blueprint

router = APIRouter(prefix="/system/intelligence", tags=["spixa-intelligence"])


@router.get("/ecosystem")
async def intelligence_ecosystem():
    return ecosystem_blueprint()
