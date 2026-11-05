"""Seed Project-Intelligence training data from deterministic intelligence reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.distillation.engine import DistillationEngine, get_distillation_engine
from app.intelligence.engine import run_project_intelligence


def _report_to_qa(workspace: Path, report: dict[str, Any]) -> list[dict[str, str]]:
    name = workspace.name
    arch = report.get("architecture") or {}
    code = report.get("code") or {}
    business = report.get("business") or {}
    coverage = report.get("coverage") or {}
    langs = (code.get("stats") or {}).get("languages") or (report.get("scan") or {}).get("languages") or []
    frameworks = (code.get("stats") or {}).get("frameworks") or []

    pairs = [
        {
            "prompt": f"Summarize the architecture of project '{name}' from evidence.",
            "output": json.dumps(
                {
                    "architecture": arch,
                    "coverage": coverage,
                    "note": "Derived from Project Intelligence scan — treat as evidence-backed.",
                },
                ensure_ascii=False,
            )[:4000],
        },
        {
            "prompt": f"What languages and frameworks does '{name}' use?",
            "output": (
                f"Languages: {langs}. Frameworks: {frameworks}. "
                f"File/symbol stats: {code.get('stats') or {}}."
            )[:4000],
        },
        {
            "prompt": f"List business-facing signals detected in '{name}'.",
            "output": json.dumps(business, ensure_ascii=False)[:4000],
        },
    ]
    return pairs


def seed_from_workspace(
    workspace: Path,
    *,
    settings: Settings | None = None,
    engine: DistillationEngine | None = None,
) -> dict[str, Any]:
    """Run deterministic PI and promote pairs as verified training examples (tool-verified)."""
    settings = settings or get_settings()
    engine = engine or get_distillation_engine()
    report = run_project_intelligence(workspace).to_dict()
    pairs = _report_to_qa(workspace, report)
    accepted = 0
    ids: list[str] = []
    for pair in pairs:
        result = engine.ingest_teacher_output(
            role="project_intelligence",
            prompt=pair["prompt"],
            system="You are Internal Project Intelligence. Cite only provided evidence.",
            teacher_model="evolve/deterministic-project-intelligence",
            teacher_output=pair["output"],
            metadata={
                "specialty": "project_intelligence",
                "distill": True,
                "tools_ok": True,  # deterministic scanner/tools produced the evidence
                "source_workspace": str(workspace),
            },
        )
        if result.get("accepted"):
            accepted += 1
            ids.append(str(result.get("id")))
    return {
        "workspace": str(workspace),
        "pairs": len(pairs),
        "accepted": accepted,
        "ids": ids,
        "coverage": report.get("coverage"),
    }
