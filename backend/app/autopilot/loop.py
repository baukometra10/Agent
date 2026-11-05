"""Background loop for مساعد الطيار — runs while enabled, sandbox-only cycles."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from app.autopilot.engine import get_autopilot
from app.config import get_settings
from app.db.session import SessionLocal

logger = logging.getLogger("evolve.autopilot")

_task: asyncio.Task[None] | None = None
_stop = asyncio.Event()


async def _tick_once() -> dict[str, Any]:
    auto = get_autopilot()
    status = auto.status()
    if not status.get("enabled"):
        return {"skipped": True, "reason": "disabled"}
    if status.get("paused_for_manual"):
        return {"skipped": True, "reason": "paused_for_manual"}
    async with SessionLocal() as session:
        return await auto.run_once(session, force=False)


async def _runner() -> None:
    settings = get_settings()
    interval = max(30, int(settings.autopilot_interval_seconds))
    logger.info("autopilot loop started interval=%ss", interval)
    # Small delay so API finishes booting
    await asyncio.sleep(2)
    cycles = 0
    while not _stop.is_set():
        try:
            result = await _tick_once()
            if not result.get("skipped"):
                logger.info(
                    "autopilot cycle ok projects=%s",
                    (result.get("report") or {}).get("projects_scanned"),
                )
            cycles += 1
            # Self-maintenance every ~3 intervals (platform-only; never touches project originals)
            if cycles % 3 == 0:
                from app.maintain import get_self_maintenance

                maint = await get_self_maintenance().run(climb_if_low=True)
                logger.info("self-maintenance ok path=%s", maint.get("path"))
        except Exception:  # noqa: BLE001
            logger.exception("autopilot cycle failed")
        try:
            await asyncio.wait_for(_stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue
    logger.info("autopilot loop stopped")


def start_autopilot_loop() -> None:
    global _task
    if _task and not _task.done():
        return
    _stop.clear()
    _task = asyncio.create_task(_runner(), name="evolve-autopilot-loop")


async def stop_autopilot_loop() -> None:
    global _task
    _stop.set()
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None


def is_loop_running() -> bool:
    return bool(_task and not _task.done())


def loop_status() -> dict[str, Any]:
    auto = get_autopilot().status()
    interval = max(30, int(get_settings().autopilot_interval_seconds))
    return {
        **auto,
        "loop_running": is_loop_running(),
        "interval_seconds": interval,
        "server_time": datetime.now(timezone.utc).isoformat(),
    }
