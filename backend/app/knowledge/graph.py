"""Knowledge Graph service — project-scoped nodes & edges with provenance."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeEdge, KnowledgeKind, KnowledgeNode
from app.knowledge.memory import MEMORY_LAYERS


class KnowledgeGraphService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_nodes(
        self,
        project_id: UUID,
        *,
        memory_layer: str | None = None,
        kind: str | None = None,
        category: str | None = None,
        include_stale: bool = True,
        limit: int = 500,
    ) -> list[KnowledgeNode]:
        stmt = select(KnowledgeNode).where(KnowledgeNode.project_id == project_id)
        if memory_layer:
            stmt = stmt.where(KnowledgeNode.memory_layer == memory_layer)
        if kind:
            stmt = stmt.where(KnowledgeNode.kind == KnowledgeKind(kind))
        if category:
            stmt = stmt.where(KnowledgeNode.category == category)
        if not include_stale:
            stmt = stmt.where(KnowledgeNode.is_stale.is_(False))
        stmt = stmt.order_by(KnowledgeNode.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_edges(self, project_id: UUID, limit: int = 1000) -> list[KnowledgeEdge]:
        result = await self.session.execute(
            select(KnowledgeEdge)
            .where(KnowledgeEdge.project_id == project_id)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def replace_auto_knowledge(
        self,
        project_id: UUID,
        items: list[dict[str, Any]],
        *,
        categories: set[str] | None = None,
        project_revision: str | None = None,
    ) -> dict[str, Any]:
        """Replace auto-generated nodes for selected categories; rebuild simple edges."""
        # Mark previous auto nodes stale first (audit-friendly), then delete category set.
        existing = await self.session.execute(
            select(KnowledgeNode).where(
                KnowledgeNode.project_id == project_id,
                KnowledgeNode.source_type.in_(["file", "agent", "doc"]),
            )
        )
        old_nodes = list(existing.scalars().all())
        now = datetime.now(timezone.utc)
        for node in old_nodes:
            if categories is None or node.category in categories:
                node.is_stale = True

        await self.session.execute(
            delete(KnowledgeEdge).where(KnowledgeEdge.project_id == project_id)
        )
        if categories:
            to_delete = [n for n in old_nodes if n.category in categories]
        else:
            to_delete = [
                n for n in old_nodes if n.source_type in {"file", "agent", "doc"}
            ]
        for node in to_delete:
            await self.session.delete(node)
        await self.session.flush()

        created: list[KnowledgeNode] = []
        by_key: dict[str, KnowledgeNode] = {}
        for item in items:
            layer = item.get("memory_layer", "project")
            if layer not in MEMORY_LAYERS:
                layer = "project"
            kind = KnowledgeKind(item.get("kind", "unverified"))
            node = KnowledgeNode(
                project_id=project_id,
                memory_layer=layer,
                category=item.get("category", "general"),
                kind=kind,
                title=item.get("title", "Untitled"),
                content=item.get("content", ""),
                confidence=float(item.get("confidence", 0.5)),
                source_type=item.get("source_type", "agent"),
                source_path=item.get("source_path"),
                source_ref=item.get("source_ref"),
                evidence=item.get("evidence") or {},
                project_revision=project_revision,
                verified_at=now if kind == KnowledgeKind.fact else None,
                is_stale=False,
                meta=item.get("meta") or {},
            )
            self.session.add(node)
            created.append(node)
            key = f"{layer}:{node.category}:{node.title}"
            by_key[key] = node

        await self.session.flush()

        edges_written = await self._link_related(project_id, created)
        counts = {"fact": 0, "inference": 0, "unverified": 0}
        by_layer = {layer: 0 for layer in MEMORY_LAYERS}
        for node in created:
            counts[node.kind.value] = counts.get(node.kind.value, 0) + 1
            by_layer[node.memory_layer] = by_layer.get(node.memory_layer, 0) + 1

        return {
            "nodes_written": len(created),
            "edges_written": edges_written,
            "counts_by_kind": counts,
            "counts_by_layer": by_layer,
        }

    async def _link_related(self, project_id: UUID, nodes: list[KnowledgeNode]) -> int:
        """Create useful graph edges from co-located evidence / categories."""
        written = 0
        by_path: dict[str, list[KnowledgeNode]] = {}
        by_category: dict[str, list[KnowledgeNode]] = {}
        purpose = [n for n in nodes if n.category == "purpose"]
        layers = [n for n in nodes if n.category == "layer"]
        apis = [n for n in nodes if n.category == "api"]
        risks = [n for n in nodes if n.category == "risk"]

        for node in nodes:
            if node.source_path:
                by_path.setdefault(node.source_path, []).append(node)
            by_category.setdefault(node.category, []).append(node)

        async def add_edge(a: KnowledgeNode, b: KnowledgeNode, relation: str, confidence: float):
            nonlocal written
            if a.id == b.id:
                return
            self.session.add(
                KnowledgeEdge(
                    project_id=project_id,
                    from_node_id=a.id,
                    to_node_id=b.id,
                    relation=relation,
                    confidence=confidence,
                    meta={},
                )
            )
            written += 1

        # Same-file relatedness
        for group in by_path.values():
            if len(group) < 2:
                continue
            anchor = group[0]
            for other in group[1:6]:
                await add_edge(anchor, other, "co_located", 0.7)

        # Purpose informs capabilities / actors
        for p in purpose[:1]:
            for cap in by_category.get("capability", [])[:8]:
                await add_edge(p, cap, "supports", 0.65)
            for actor in by_category.get("actor", [])[:8]:
                await add_edge(p, actor, "involves", 0.6)

        # Architecture layers relate to APIs and risks
        for layer_node in layers[:6]:
            for api in apis[:4]:
                await add_edge(layer_node, api, "exposes", 0.55)
            for risk in risks[:4]:
                await add_edge(risk, layer_node, "threatens", 0.5)

        # Summary depends on facts
        summaries = by_category.get("summary", [])
        facts = [n for n in nodes if n.kind == KnowledgeKind.fact][:12]
        for summary in summaries[:1]:
            for fact in facts:
                await add_edge(summary, fact, "grounded_in", 0.7)

        await self.session.flush()
        return written

    async def graph_snapshot(self, project_id: UUID) -> dict[str, Any]:
        nodes = await self.list_nodes(project_id, include_stale=False, limit=800)
        edges = await self.list_edges(project_id)
        return {
            "nodes": [
                {
                    "id": str(n.id),
                    "memory_layer": n.memory_layer,
                    "category": n.category,
                    "kind": n.kind.value,
                    "title": n.title,
                    "confidence": n.confidence,
                    "source_path": n.source_path,
                }
                for n in nodes
            ],
            "edges": [
                {
                    "id": str(e.id),
                    "from": str(e.from_node_id),
                    "to": str(e.to_node_id),
                    "relation": e.relation,
                    "confidence": e.confidence,
                }
                for e in edges
            ],
            "layers": {
                layer: sum(1 for n in nodes if n.memory_layer == layer)
                for layer in MEMORY_LAYERS
            },
        }
