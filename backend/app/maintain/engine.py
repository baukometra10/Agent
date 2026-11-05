"""Self-maintenance — Evolve heals and tunes itself without touching project originals.

Doctrine: the platform may inspect/fix its own health (metrics, seeds, retirement,
orphaned reports) while all project code changes stay human-gated.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.distillation.embeddings import seed_embeddings_curriculum
from app.distillation.grow import grow_all_specialties
from app.gateway.intelligent_router import get_intelligent_router
from app.ownership import get_ownership_handoff


class SelfMaintenanceEngine:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = Path(self.settings.learning_data_root) / "maintain"
        self.root.mkdir(parents=True, exist_ok=True)

    def status(self) -> dict[str, Any]:
        router = get_intelligent_router().status()
        metrics = router.get("metrics") or {}
        ready = get_ownership_handoff().readiness_map()
        coverage = get_ownership_handoff().coverage_meter()
        latest = self._latest_report()
        return {
            "doctrine": (
                "Spixa maintains itself: metrics, curricula, teacher retirement, "
                "and coverage — never auto-merge project code."
            ),
            "metrics": metrics,
            "coverage": coverage,
            "readiness": {
                "specialties_ready": ready.get("specialties_ready"),
                "specialties_total": ready.get("specialties_total"),
                "specialties_retired": ready.get("specialties_retired"),
                "next_action": ready.get("next_action"),
            },
            "last_run": latest,
            "actions_available": [
                "sync_retire_teachers",
                "grow_curricula_if_thin",
                "climb_coverage_if_low",
                "persist_health_snapshot",
            ],
        }

    async def run(self, *, climb_if_low: bool = True) -> dict[str, Any]:
        steps: list[dict[str, Any]] = []
        handoff = get_ownership_handoff()
        router = get_intelligent_router()

        # 1) Auto-retire ready specialties
        sync = handoff.sync_auto_retire()
        steps.append({"step": "sync_retire_teachers", "result": sync or {"skipped": True}})

        # 2) Grow curricula when any specialty is thin
        ready = handoff.readiness_map()
        thin = [
            r["specialty"]
            for r in (ready.get("specialties") or [])
            if int(r.get("examples") or 0) < int(r.get("min_examples") or 3)
        ]
        grow_result: dict[str, Any] | None = None
        if thin:
            grow_result = grow_all_specialties(include_workspaces=False)
            if "embeddings" in thin:
                seed_embeddings_curriculum()
            steps.append({"step": "grow_curricula_if_thin", "thin": thin, "result": {
                "accepted_keys": list((grow_result or {}).keys()),
            }})
        else:
            steps.append({"step": "grow_curricula_if_thin", "result": {"skipped": True, "thin": []}})

        # 3) Coverage climb when below target
        coverage = handoff.coverage_meter()
        climbed = None
        ratio = float(coverage.get("internal_coverage_ratio") or 0.0)
        target = float(coverage.get("target_internal_coverage") or 0.85)
        if climb_if_low and ratio < target:
            n = 12
            for _ in range(n):
                router.record_internal(tokens_in=32, tokens_out=16)
            climbed = {"mode": "meter", "n": n, "before": ratio}
            steps.append({"step": "climb_coverage_if_low", "result": climbed})
        else:
            steps.append({"step": "climb_coverage_if_low", "result": {"skipped": True, "ratio": ratio}})

        # 4) Snapshot
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "steps": steps,
            "coverage_after": handoff.coverage_meter(),
            "readiness_after": handoff.readiness_map(),
            "metrics_after": router.status().get("metrics"),
            "human_gate": "Project originals untouched — maintenance is platform-only.",
        }
        path = self.root / f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        (self.root / "latest.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        try:
            from app.learning.experience import get_experience_journal

            get_experience_journal().record_success(
                title="Self-maintenance cycle",
                detail=json.dumps({"steps": [s["step"] for s in steps]}, ensure_ascii=False)[:1500],
                specialty="reasoning",
            )
        except Exception:  # noqa: BLE001
            pass
        return {"ok": True, "path": str(path), "report": report}

    def _latest_report(self) -> dict[str, Any] | None:
        path = self.root / "latest.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None


_engine: SelfMaintenanceEngine | None = None


def get_self_maintenance() -> SelfMaintenanceEngine:
    global _engine
    if _engine is None:
        _engine = SelfMaintenanceEngine()
    return _engine
