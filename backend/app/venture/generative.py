"""Generative Software Design — business goal → BusinessSystemSpec + design pack."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Project
from app.gateway.router import ModelRole, get_model_gateway
from app.intelligence.business_intelligence import analyze_business
from app.intelligence.scanner import scan_workspace
from app.intelligence.code_intelligence import analyze_codebase
from app.security.isolation import assert_path_inside_workspace
from app.venture.patterns import PatternLibrary


def _repo_root(project: Project) -> Path:
    workspace = Path(project.workspace_path)
    repo = workspace / "repo"
    return repo if repo.exists() else workspace


class GenerativeDesignEngine:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.gateway = get_model_gateway()

    async def build_spec(self, project: Project, brief: str) -> dict[str, Any]:
        root = _repo_root(project)
        scan = scan_workspace(root)
        code = analyze_codebase(root)
        business = analyze_business(root, scan, code.to_dict())
        patterns = await PatternLibrary(self.session).suggest_for_brief(brief, limit=5)

        prompt = (
            "You are Spixa Generative Software Design.\n"
            "From the business goal, produce a JSON BusinessSystemSpec with keys:\n"
            "purpose, actors (list of {role, goals}), capabilities (list of {id, name, description}),\n"
            "processes (list of {name, steps}), constraints (list of str),\n"
            "success_metrics (list of str), data_entities (list of {name, fields}),\n"
            "api_surface (list of {method, path, purpose}), ux_map (list of {screen, purpose}).\n"
            "Respond with JSON only.\n\n"
            f"Goal (AR/EN):\n{brief}\n\n"
            f"Existing purpose guess: {business.purpose}\n"
            f"Existing actors: {business.actors[:8]}\n"
            f"Existing capabilities: {business.capabilities[:12]}\n"
            f"Reusable patterns (abstract): {[p.get('title') for p in patterns]}\n"
        )
        response = await self.gateway.complete(
            ModelRole.reasoning,
            prompt,
            system="Output valid JSON only. Prefer concrete, testable capabilities.",
            metadata={"agent": "GenerativeDesign", "project_id": str(project.id)},
        )
        spec = self._parse_spec(response.content, brief, business.to_dict())
        architecture = await self._propose_architecture(project, brief, spec)
        written = self._write_pack(root, project, brief, spec, architecture)
        return {
            "spec": spec,
            "architecture": architecture,
            "files": written,
            "patterns_used": patterns,
            "model": response.model_id,
            "simulated": bool(response.simulated),
        }

    async def _propose_architecture(
        self, project: Project, brief: str, spec: dict[str, Any]
    ) -> dict[str, Any]:
        prompt = (
            "Propose a pragmatic software architecture for this BusinessSystemSpec.\n"
            "Return JSON: {style, layers, services, data_stores, integrations, risks, rationale}.\n"
            f"Project: {project.name}\nBrief: {brief}\nSpec: {json.dumps(spec, ensure_ascii=False)[:4000]}\n"
        )
        response = await self.gateway.complete(
            ModelRole.reasoning,
            prompt,
            system="You are ArchitectureDesigner. Prefer modular, evolvable designs.",
            metadata={"agent": "ArchitectureDesigner", "project_id": str(project.id)},
        )
        try:
            data = json.loads(self._extract_json(response.content))
            if isinstance(data, dict):
                data["model"] = response.model_id
                return data
        except (json.JSONDecodeError, TypeError):
            pass
        return {
            "style": "modular_monolith",
            "layers": ["api", "domain", "data", "ui"],
            "services": [c.get("name") for c in (spec.get("capabilities") or [])[:8]],
            "data_stores": [e.get("name") for e in (spec.get("data_entities") or [])[:8]],
            "integrations": [],
            "risks": ["scale boundaries unclear until traffic known"],
            "rationale": response.content[:1200],
            "model": response.model_id,
        }

    def _write_pack(
        self,
        root: Path,
        project: Project,
        brief: str,
        spec: dict[str, Any],
        architecture: dict[str, Any],
    ) -> list[str]:
        base = root / ".spixa" / "design"
        base.mkdir(parents=True, exist_ok=True)
        files = {
            "BUSINESS_SPEC.json": json.dumps(spec, ensure_ascii=False, indent=2),
            "ARCHITECTURE.json": json.dumps(architecture, ensure_ascii=False, indent=2),
            "architecture.md": self._arch_md(project, brief, spec, architecture),
            "API_CONTRACT.md": self._api_md(spec),
            "UX_MAP.md": self._ux_md(spec),
            "DATA_MODEL.md": self._data_md(spec),
        }
        written: list[str] = []
        for name, content in files.items():
            path = base / name
            assert_path_inside_workspace(Path(project.workspace_path), path.resolve())
            path.write_text(content, encoding="utf-8")
            try:
                rel = str(path.relative_to(root)).replace("\\", "/")
            except ValueError:
                rel = str(path)
            written.append(rel)
        # Minimal prototype skeleton
        proto = base / "prototype"
        proto.mkdir(parents=True, exist_ok=True)
        readme = proto / "README.md"
        readme.write_text(
            f"# Prototype — {project.name}\n\nGoal: {brief}\n\n"
            "Skeleton generated by Spixa Generative Design. Implement behind human approval.\n",
            encoding="utf-8",
        )
        written.append(str(readme.relative_to(root)).replace("\\", "/"))
        return written

    def _arch_md(
        self, project: Project, brief: str, spec: dict[str, Any], architecture: dict[str, Any]
    ) -> str:
        return (
            f"# Architecture — {project.name}\n\n"
            f"## Goal\n{brief}\n\n"
            f"## Purpose\n{spec.get('purpose')}\n\n"
            f"## Style\n{architecture.get('style')}\n\n"
            f"## Layers\n{', '.join(architecture.get('layers') or [])}\n\n"
            f"## Services\n{json.dumps(architecture.get('services') or [], ensure_ascii=False, indent=2)}\n\n"
            f"## Risks\n{json.dumps(architecture.get('risks') or [], ensure_ascii=False, indent=2)}\n\n"
            f"## Rationale\n{architecture.get('rationale')}\n"
        )

    def _api_md(self, spec: dict[str, Any]) -> str:
        lines = ["# API Contract\n"]
        for ep in spec.get("api_surface") or []:
            lines.append(
                f"- `{ep.get('method', 'GET')} {ep.get('path', '/')}` — {ep.get('purpose', '')}"
            )
        return "\n".join(lines) + "\n"

    def _ux_md(self, spec: dict[str, Any]) -> str:
        lines = ["# UX Map\n"]
        for screen in spec.get("ux_map") or []:
            lines.append(f"- **{screen.get('screen')}**: {screen.get('purpose')}")
        return "\n".join(lines) + "\n"

    def _data_md(self, spec: dict[str, Any]) -> str:
        lines = ["# Data Model\n"]
        for ent in spec.get("data_entities") or []:
            fields = ", ".join(ent.get("fields") or [])
            lines.append(f"- **{ent.get('name')}**: {fields}")
        return "\n".join(lines) + "\n"

    def _parse_spec(self, content: str, brief: str, business: dict[str, Any]) -> dict[str, Any]:
        try:
            data = json.loads(self._extract_json(content))
            if isinstance(data, dict) and data.get("capabilities"):
                return data
        except (json.JSONDecodeError, TypeError):
            pass
        actors = business.get("actors") or [{"role": "Owner", "goals": ["run the business"]}]
        caps = business.get("capabilities") or [
            {"id": "core", "name": "Core operations", "description": brief[:200]}
        ]
        return {
            "purpose": business.get("purpose") or brief[:280],
            "actors": actors,
            "capabilities": caps,
            "processes": [{"name": "primary", "steps": ["intake", "operate", "improve"]}],
            "constraints": ["human approval before production merge"],
            "success_metrics": ["task completion", "bottleneck detection", "adaptation speed"],
            "data_entities": [{"name": "Organization", "fields": ["id", "name", "stage"]}],
            "api_surface": [{"method": "GET", "path": "/health", "purpose": "liveness"}],
            "ux_map": [{"screen": "Dashboard", "purpose": "overview + bottlenecks"}],
            "fallback": True,
            "raw_model_notes": content[:1500],
        }

    @staticmethod
    def _extract_json(text: str) -> str:
        text = (text or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return text[start : end + 1]
        return text
