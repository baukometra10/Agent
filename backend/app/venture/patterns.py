"""Engineering Knowledge Network — private KG + curated public patterns."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeKind, KnowledgeNode, Project, SpixaPattern
from app.knowledge.graph import KnowledgeGraphService
from app.learning.experience import get_experience_journal


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s or "pattern")[:100]


class PatternLibrary:
    """Cross-project patterns are abstract only — never store client paths/secrets."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.kg = KnowledgeGraphService(session)

    async def list_patterns(self, *, approved_only: bool = True, limit: int = 50) -> list[dict[str, Any]]:
        await self._ensure_seed_patterns()
        stmt = select(SpixaPattern).order_by(SpixaPattern.updated_at.desc()).limit(limit)
        if approved_only:
            stmt = stmt.where(SpixaPattern.approved.is_(True))
        rows = list((await self.session.execute(stmt)).scalars().all())
        return [self._out(r) for r in rows]

    async def _ensure_seed_patterns(self) -> None:
        existing = await self.session.execute(select(SpixaPattern).limit(1))
        if existing.scalar_one_or_none():
            return
        seeds = [
            {
                "slug": "modular-monolith-first",
                "title": "Modular monolith first",
                "summary": "Start as modular monolith with clear domain boundaries; extract services only when team or scale pressure justifies ops cost.",
                "category": "architecture",
                "tags": ["architecture", "modularity"],
            },
            {
                "slug": "human-gate-before-merge",
                "title": "Human gate before merge",
                "summary": "Agents may plan and draft freely; merge and deploy require explicit human approval with blast-radius review.",
                "category": "process",
                "tags": ["governance", "safety"],
            },
            {
                "slug": "detect-bottlenecks-loop",
                "title": "Bottleneck detection loop",
                "summary": "Instrument core processes, detect queues/latency, propose improvements as gated proposals rather than silent rewrites.",
                "category": "operations",
                "tags": ["monitoring", "evolution"],
            },
        ]
        now = datetime.now(timezone.utc)
        for s in seeds:
            self.session.add(
                SpixaPattern(
                    slug=s["slug"],
                    title=s["title"],
                    summary=s["summary"],
                    category=s["category"],
                    pattern={"doctrine": s["summary"]},
                    tags=s["tags"],
                    confidence=0.8,
                    approved=True,
                    approved_at=now,
                    source_project_count=0,
                )
            )
        await self.session.commit()

    async def suggest_for_brief(self, brief: str, limit: int = 5) -> list[dict[str, Any]]:
        rows = await self.list_patterns(approved_only=True, limit=40)
        tokens = {t for t in re.split(r"\W+", (brief or "").lower()) if len(t) > 3}
        scored: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            hay = " ".join(
                [
                    row.get("title") or "",
                    row.get("summary") or "",
                    " ".join(row.get("tags") or []),
                    row.get("category") or "",
                ]
            ).lower()
            overlap = sum(1 for t in tokens if t in hay)
            scored.append((overlap + float(row.get("confidence") or 0), row))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:limit]]

    async def propose_from_experience(self, *, title: str, summary: str, category: str = "architecture") -> dict[str, Any]:
        """Create an unapproved pattern candidate from sanitized experience."""
        slug = _slugify(title)
        existing = await self.session.execute(select(SpixaPattern).where(SpixaPattern.slug == slug))
        row = existing.scalar_one_or_none()
        if row:
            return self._out(row)
        # Strip path-like tokens
        clean = re.sub(r"[A-Za-z]:\\[^\s]+", "[path]", summary)
        clean = re.sub(r"/Users/[^\s]+|/home/[^\s]+", "[path]", clean)
        clean = re.sub(r"(api[_-]?key|secret|token|password)\s*[:=]\s*\S+", r"\1=[redacted]", clean, flags=re.I)
        row = SpixaPattern(
            slug=slug,
            title=title[:255],
            summary=clean[:4000],
            category=category,
            pattern={"abstract_steps": [s.strip() for s in clean.split(".") if s.strip()][:8]},
            tags=[category],
            confidence=0.55,
            source_project_count=1,
            approved=False,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return self._out(row)

    async def approve_pattern(self, pattern_id: UUID) -> dict[str, Any] | None:
        row = await self.session.get(SpixaPattern, pattern_id)
        if not row:
            return None
        row.approved = True
        row.approved_at = datetime.now(timezone.utc)
        await self.session.commit()
        return self._out(row)

    async def apply_to_project(self, project: Project, pattern_id: UUID) -> dict[str, Any]:
        """Copy an approved public pattern into the project's private knowledge graph."""
        row = await self.session.get(SpixaPattern, pattern_id)
        if not row or not row.approved:
            raise ValueError("Pattern not found or not approved")
        node = KnowledgeNode(
            project_id=project.id,
            memory_layer="architecture",
            category="pattern",
            kind=KnowledgeKind.inference,
            title=f"Pattern:{row.title}",
            content=row.summary,
            confidence=row.confidence,
            source_type="agent",
            evidence={
                "spixa_pattern_id": str(row.id),
                "slug": row.slug,
                "isolation": "copied_abstract_only",
            },
            meta={"pattern": row.pattern},
        )
        self.session.add(node)
        await self.session.commit()
        return {
            "project_id": str(project.id),
            "node_id": str(node.id),
            "pattern_id": str(row.id),
            "isolation_guarantee": "Private copy only; no client artifacts leave the project.",
        }

    async def harvest_candidates_from_journal(self, limit: int = 5) -> list[dict[str, Any]]:
        journal = get_experience_journal()
        created: list[dict[str, Any]] = []
        events = [e for e in journal.recent(limit=limit * 3) if e.get("kind") == "success"][:limit]
        for ev in events:
            title = str(ev.get("title") or ev.get("specialty") or "experience pattern")[:120]
            summary = str(ev.get("detail") or ev.get("summary") or title)[:1500]
            created.append(
                await self.propose_from_experience(title=title, summary=summary, category="experience")
            )
        return created

    @staticmethod
    def _out(row: SpixaPattern) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "slug": row.slug,
            "title": row.title,
            "summary": row.summary,
            "category": row.category,
            "pattern": row.pattern,
            "tags": row.tags,
            "confidence": row.confidence,
            "approved": row.approved,
            "source_project_count": row.source_project_count,
        }
