"""Intelligence Evolution Dashboard — specialty trajectories over time."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.eval.harness import get_eval_harness
from app.factory.orchestrator import ModelFactory
from app.factory.proof import FactoryProofTrack
from app.intelligence.ecosystem import SPIXA_FAMILY
from app.maturity.scorecard import get_maturity_board
from app.ownership.registry import get_ownership_registry


def evolution_dashboard(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    factory = ModelFactory(settings=settings)
    proof = FactoryProofTrack(settings=settings)
    maturity = get_maturity_board()
    registry = get_ownership_registry()
    eval_root = Path(settings.eval_data_root)

    specialties: list[dict[str, Any]] = []
    for fam in SPIXA_FAMILY:
        sp = fam["specialty"]
        releases = [r for r in factory.list_releases() if r.get("specialty") == sp]
        releases_sorted = sorted(releases, key=lambda r: r.get("created_at") or "")
        trail = []
        for r in releases_sorted:
            ev = r.get("eval") or {}
            trail.append(
                {
                    "at": r.get("created_at") or r.get("approved_at"),
                    "status": r.get("status"),
                    "student_score": ev.get("student_score"),
                    "teacher_score": ev.get("teacher_score"),
                    "release_id": r.get("id"),
                }
            )
        # eval file history (latest + any eval-*.json count)
        latest = get_eval_harness().latest(sp)
        hist_files = sorted(eval_root.glob(f"eval-{sp}-*.json")) if eval_root.exists() else []
        improve = proof.improvement_report(sp)
        card = maturity.scorecard(sp)
        reg = registry.list_specialty(sp)
        scores = [t["student_score"] for t in trail if t.get("student_score") is not None]
        improved_skills = []
        regressed_skills = []
        if len(scores) >= 2:
            delta = float(scores[-1]) - float(scores[0])
            if delta > 0:
                improved_skills.append({"skill": "held_out_benchmark", "delta": round(delta, 4)})
            elif delta < 0:
                regressed_skills.append({"skill": "held_out_benchmark", "delta": round(delta, 4)})

        specialties.append(
            {
                "product": fam["product"],
                "specialty": sp,
                "priority": fam["priority"],
                "release_trail": trail,
                "eval_latest": {
                    "student_score": (latest or {}).get("student_score"),
                    "teacher_score": (latest or {}).get("teacher_score"),
                    "promote": (latest or {}).get("promote"),
                },
                "eval_snapshots": len(hist_files),
                "successive_improvement": improve,
                "maturity": {
                    "production_ready": card["production_ready"],
                    "blockers": card["blockers"],
                    "metrics_summary": {
                        k: (v or {}).get("value") for k, v in (card.get("metrics") or {}).items()
                    },
                },
                "ownership_versions": len((reg.get("versions") or [])),
                "skills_improved": improved_skills,
                "skills_regressed": regressed_skills,
                "vs_previous": {
                    "delta_student": improve.get("delta_student_score"),
                    "improved": improve.get("improved"),
                    "non_regressing": improve.get("non_regressing"),
                },
                "vs_teacher": {
                    "student": (latest or {}).get("student_score"),
                    "teacher": (latest or {}).get("teacher_score"),
                },
            }
        )

    return {
        "name": "Intelligence Evolution Dashboard",
        "name_ar": "لوحة تطور الذكاء",
        "doctrine_ar": (
            "تتبع كل تخصص عبر الزمن: تحسن، تراجع، تكلفة، ومقارنة بالإصدارات والمعلّمين — "
            "بدون الاعتماد على عدد الأمثلة."
        ),
        "specialties": specialties,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
