from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.activity import get_activity_bus

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("/live")
async def live_state(project_id: str | None = Query(default=None)) -> dict[str, Any]:
    return get_activity_bus().snapshot(project_id=project_id)


@router.get("/events")
async def list_events(
    after_id: int = Query(default=0, ge=0),
    project_id: str | None = Query(default=None),
    limit: int = Query(default=80, ge=1, le=200),
) -> dict[str, Any]:
    bus = get_activity_bus()
    events = bus.since(after_id, project_id=project_id, limit=limit)
    return {"events": events, "focus": bus.focus()}


@router.get("/stream")
async def stream_events(project_id: str | None = Query(default=None)):
    bus = get_activity_bus()

    async def gen():
        last = 0
        while True:
            batch = bus.since(last, project_id=project_id, limit=40)
            if batch:
                last = batch[-1]["id"]
                payload = {"events": batch, "focus": bus.focus()}
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'events': [], 'focus': bus.focus()}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.8)

    return StreamingResponse(gen(), media_type="text/event-stream")
