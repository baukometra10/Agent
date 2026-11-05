"""مساعد الطيار — enable before leaving; sandbox-only; report via email/queue."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.autopilot import get_autopilot, loop_status
from app.db.session import get_db
from app.learning.experience import get_experience_journal

router = APIRouter(prefix="/system/autopilot", tags=["autopilot"])


class EnableBody(BaseModel):
    notify_email: str | None = None
    project_ids: list[str] | None = None


class RunBody(BaseModel):
    force: bool = True
    notify_email: str | None = None
    project_ids: list[str] | None = None


@router.get("")
async def autopilot_status():
    auto = get_autopilot()
    latest = auto.latest_report()
    return {
        "autopilot": loop_status(),
        "experience": get_experience_journal().stats(),
        "latest_report": (
            {
                "id": latest.get("id"),
                "generated_at": latest.get("generated_at"),
                "summary": latest.get("summary"),
                "projects_scanned": latest.get("projects_scanned"),
            }
            if latest
            else None
        ),
    }


@router.get("/reports")
async def autopilot_reports(limit: int = 20):
    return {"reports": get_autopilot().list_reports(limit=min(limit, 50))}


@router.get("/reports/latest")
async def autopilot_latest_report():
    latest = get_autopilot().latest_report()
    if not latest:
        raise HTTPException(status_code=404, detail="no reports yet")
    return latest


@router.post("/enable")
async def autopilot_enable(body: EnableBody | None = None):
    body = body or EnableBody()
    return get_autopilot().enable(
        notify_email=body.notify_email,
        project_ids=body.project_ids,
    )


@router.post("/disable")
async def autopilot_disable():
    return get_autopilot().disable()


@router.post("/resume")
async def autopilot_resume():
    """Clear manual pause and keep autonomous loop active."""
    return get_autopilot().resume_autonomous()


@router.post("/run")
async def autopilot_run(body: RunBody | None = None, db: AsyncSession = Depends(get_db)):
    body = body or RunBody()
    ids = None
    if body.project_ids:
        try:
            ids = [UUID(x) for x in body.project_ids]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid project_ids") from exc
    return await get_autopilot().run_once(
        db,
        force=body.force,
        notify_email=body.notify_email,
        project_ids=ids,
    )
