"""Called by start.ps1 — create all SQLAlchemy tables."""

from __future__ import annotations

import asyncio


async def main() -> None:
    from app.db.base import Base
    from app.db.session import engine
    import app.db.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("    schema ok")


if __name__ == "__main__":
    asyncio.run(main())
