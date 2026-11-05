"""Digital Twin — live cognitive model + change-impact simulation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Project
from app.intelligence.engine import run_project_intelligence
from app.knowledge.graph import KnowledgeGraphService


TWIN_CATEGORIES = {
    "component",
    "dependency",
    "data_store",
    "behavior",
    "invariant",
    "layer",
}


class DigitalTwinService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.kg = KnowledgeGraphService(session)

    async def rebuild(self, project: Project) -> dict[str, Any]:
        root = Path(project.workspace_path)
        repo = root / "repo"
        workspace = repo if repo.exists() else root
        report = run_project_intelligence(workspace)
        items: list[dict[str, Any]] = []

        for layer in (report.architecture or {}).get("layers") or []:
            items.append(
                {
                    "memory_layer": "architecture",
                    "category": "layer",
                    "kind": "fact",
                    "title": f"Layer:{layer.get('layer')}",
                    "content": f"{layer.get('file_count', 0)} files in layer {layer.get('layer')}",
                    "confidence": 0.85,
                    "source_type": "agent",
                    "source_path": None,
                    "evidence": {"files": (layer.get("files") or [])[:20], "twin": "layer"},
                }
            )

        for mod in ((report.code or {}).get("modules") or [])[:80]:
            path = mod.get("path") or mod.get("name") or "module"
            items.append(
                {
                    "memory_layer": "architecture",
                    "category": "component",
                    "kind": "fact",
                    "title": f"Component:{path}",
                    "content": str(mod.get("summary") or mod.get("kind") or path),
                    "confidence": 0.7,
                    "source_type": "file",
                    "source_path": path,
                    "evidence": {"twin": "component", "module": mod},
                }
            )

        for dep in ((report.architecture or {}).get("coupling") or [])[:40]:
            items.append(
                {
                    "memory_layer": "architecture",
                    "category": "dependency",
                    "kind": "inference",
                    "title": f"Dep:{dep.get('from', '?')}→{dep.get('to', '?')}",
                    "content": str(dep),
                    "confidence": float(dep.get("score") or 0.55),
                    "source_type": "agent",
                    "evidence": {"twin": "dependency", **dep},
                }
            )

        for risk in ((report.architecture or {}).get("risks") or [])[:20]:
            items.append(
                {
                    "memory_layer": "architecture",
                    "category": "invariant",
                    "kind": "unverified",
                    "title": f"Risk:{risk.get('title') or risk.get('id') or 'risk'}",
                    "content": str(risk.get("detail") or risk),
                    "confidence": 0.5,
                    "source_type": "agent",
                    "evidence": {"twin": "invariant", "risk": risk},
                }
            )

        for cap in ((report.business or {}).get("capabilities") or [])[:30]:
            items.append(
                {
                    "memory_layer": "project",
                    "category": "behavior",
                    "kind": "inference",
                    "title": f"Behavior:{cap.get('name') or cap.get('id')}",
                    "content": str(cap.get("description") or cap),
                    "confidence": 0.6,
                    "source_type": "doc",
                    "evidence": {"twin": "behavior", "capability": cap},
                }
            )

        kg_meta: dict[str, Any] = {}
        try:
            kg_result = await self.kg.replace_auto_knowledge(
                project.id,
                items[:200],
                categories=TWIN_CATEGORIES | {"layer"},
            )
            kg_meta = {
                "knowledge_written": kg_result.get("nodes_written") or 0,
                "edges_written": kg_result.get("edges_written") or 0,
            }
        except Exception as exc:  # noqa: BLE001
            # SQLite lock / transient DB errors must not block Twin snapshot
            await self.session.rollback()
            kg_meta = {"knowledge_written": 0, "error": str(exc)[:240]}

        twin_snapshot = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "coverage": report.coverage,
            "layers": (report.architecture or {}).get("layers") or [],
            "component_count": sum(1 for i in items if i["category"] == "component"),
            "dependency_count": sum(1 for i in items if i["category"] == "dependency"),
            "behavior_count": sum(1 for i in items if i["category"] == "behavior"),
            "purpose": (report.business or {}).get("purpose"),
            **kg_meta,
        }
        # Re-load project after possible rollback
        project = await self.session.get(Project, project.id) or project
        settings = dict(project.settings or {})
        settings["digital_twin"] = twin_snapshot
        project.settings = settings
        await self.session.commit()
        return twin_snapshot

    async def simulate_change(
        self,
        project: Project,
        *,
        change_summary: str,
        affected_paths: list[str] | None = None,
    ) -> dict[str, Any]:
        twin = dict((project.settings or {}).get("digital_twin") or {})
        if not twin:
            twin = await self.rebuild(project)

        nodes = await self.kg.list_nodes(project.id, include_stale=False, limit=400)
        paths = [p.replace("\\", "/").lower() for p in (affected_paths or [])]
        blast: list[dict[str, Any]] = []
        risks: list[dict[str, Any]] = []

        for node in nodes:
            if node.category not in TWIN_CATEGORIES and node.category != "layer":
                continue
            hit = False
            sp = (node.source_path or "").replace("\\", "/").lower()
            title = (node.title or "").lower()
            for p in paths:
                if p and (p in sp or p in title or sp.endswith(p) or p in (node.content or "").lower()):
                    hit = True
                    break
            if not hit and paths:
                # Heuristic: same top-level folder
                for p in paths:
                    top = p.split("/")[0]
                    if top and top in sp:
                        hit = True
                        break
            if hit or (not paths and node.category in {"dependency", "invariant"}):
                blast.append(
                    {
                        "id": str(node.id),
                        "category": node.category,
                        "title": node.title,
                        "path": node.source_path,
                        "confidence": node.confidence,
                    }
                )
            if node.category == "invariant" and hit:
                risks.append(
                    {
                        "severity": "high",
                        "title": node.title,
                        "detail": node.content[:400],
                    }
                )

        # Layer impact
        layer_hits = sorted(
            {
                b["title"].split(":", 1)[-1]
                for b in blast
                if b.get("category") == "layer"
            }
        )
        if not layer_hits and paths:
            for p in paths:
                if "api" in p or "route" in p:
                    layer_hits.append("api")
                if "model" in p or "db" in p:
                    layer_hits.append("data")
                if "component" in p or "page" in p:
                    layer_hits.append("ui")
            layer_hits = sorted(set(layer_hits))

        score = min(1.0, 0.2 + 0.05 * len(blast) + 0.1 * len(risks))
        return {
            "change_summary": change_summary,
            "affected_paths": affected_paths or [],
            "blast_radius": blast[:60],
            "blast_count": len(blast),
            "layers_impacted": layer_hits,
            "risks": risks[:20],
            "risk_score": round(score, 3),
            "twin_updated_at": twin.get("updated_at"),
            "recommendation": (
                "require_human_review"
                if score >= 0.45 or risks
                else "low_impact_proceed_with_tests"
            ),
            "simulated_at": datetime.now(timezone.utc).isoformat(),
        }
