"""Background worker — autonomous evolution ticks (project-isolated).

Independence model:
- May re-understand / analyze / plan each project on its own schedule.
- Must NOT execute code, merge, or deploy without human approval flags.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.autonomy import autonomy_of
from app.config import get_settings
from app.db.models import Project, ProjectStatus
from app.db.session import SessionLocal
from app.evolution.cycle import EvolutionCycle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("evolve.worker")


async def evolution_tick() -> None:
    settings = get_settings()
    if not settings.evolution_cron_enabled:
        logger.info("Evolution cron disabled. Autonomy idle this tick.")
        return

    async with SessionLocal() as session:
        result = await session.execute(
            select(Project).where(Project.status.in_([ProjectStatus.ready, ProjectStatus.evolving]))
        )
        projects = list(result.scalars().all())
        cycle = EvolutionCycle(session)

        for project in projects:
            policy = autonomy_of(project.settings if isinstance(project.settings, dict) else {})
            if not policy.get("auto_plan"):
                logger.info("Skip %s — auto_plan disabled", project.slug)
                continue
            if policy.get("auto_execute") or policy.get("auto_merge") or policy.get("auto_deploy"):
                logger.warning(
                    "Project %s has execution autonomy flags; worker still refuses execute/merge/deploy.",
                    project.slug,
                )
            try:
                logger.info("Autonomous evolution cycle for %s", project.slug)
                await cycle.run_project(project.id)
            except Exception:  # noqa: BLE001
                logger.exception("Autonomous cycle failed for %s", project.slug)


async def main() -> None:
    logger.info("Evolve worker started — independent planner, gated executor")
    while True:
        await evolution_tick()
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
