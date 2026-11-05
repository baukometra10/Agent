"""Self-Improvement Engine — proposes; never mutates production weights alone."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.distillation.engine import get_distillation_engine
from app.eval.harness import get_eval_harness
from app.ops.monitor import get_ops_monitor
from app.training.lora import get_lora_trainer


TECHNIQUE_HINTS = {
    "low_data": "Synthetic Data Factory + curated seed",
    "parity_gap": "Knowledge Distillation on hard teacher traces + DPO later",
    "stubbed": "Replace placeholder adapter with real LoRA on GPU host",
    "regression": "Continual Learning with replay of prior approved sets",
    "cost": "Prefer promoted internal; distill recurring teacher escalations",
}


class SelfImprovementEngine:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = Path(self.settings.learning_data_root) / "factory" / "self_improve"
        self.root.mkdir(parents=True, exist_ok=True)

    def propose(self, specialties: list[str] | None = None) -> dict[str, Any]:
        specialties = specialties or [
            "coding",
            "reasoning",
            "critic",
            "project_intelligence",
            "vision",
        ]
        distill = get_distillation_engine().stats()
        adapters = {a["specialty"]: a for a in get_lora_trainer().list_adapters()}
        harness = get_eval_harness()
        proposals: list[dict[str, Any]] = []

        for specialty in specialties:
            latest = harness.latest(specialty) or {}
            gates = latest.get("gates") or {}
            count = 0
            by = distill.get("examples_by_specialty") or {}
            count = int(by.get(specialty) or 0)
            adapter = adapters.get(specialty) or {}
            reasons: list[str] = []
            techniques: list[str] = []

            if count < int(self.settings.lora_min_examples):
                reasons.append("low_data")
                techniques.append(TECHNIQUE_HINTS["low_data"])
            if latest and not latest.get("promote"):
                if not gates.get("parity_vs_teacher", True):
                    reasons.append("parity_gap")
                    techniques.append(TECHNIQUE_HINTS["parity_gap"])
                if not gates.get("min_absolute", True):
                    reasons.append("absolute_floor")
                    techniques.append(TECHNIQUE_HINTS["parity_gap"])
                if gates.get("not_stub") is False:
                    reasons.append("stubbed")
                    techniques.append(TECHNIQUE_HINTS["stubbed"])
            if not adapter.get("ready"):
                reasons.append("not_production_ready")

            if not reasons:
                continue

            proposals.append(
                {
                    "id": str(uuid4()),
                    "specialty": specialty,
                    "severity": "high" if "parity_gap" in reasons or "stubbed" in reasons else "medium",
                    "reasons": reasons,
                    "suggested_techniques": list(dict.fromkeys(techniques)),
                    "evidence": {
                        "examples": count,
                        "student_score": latest.get("student_score"),
                        "teacher_score": latest.get("teacher_score"),
                        "adapter_ready": bool(adapter.get("ready")),
                    },
                    "auto_apply_forbidden": True,
                    "next_step": "run_factory_cycle_then_human_approve",
                }
            )

        batch = {
            "id": str(uuid4()),
            "at": datetime.now(timezone.utc).isoformat(),
            "doctrine": "propose_only_never_auto_mutate_production",
            "proposals": proposals,
            "note_ar": (
                "محرك التحسين الذاتي يقترح فقط. "
                "تطبيق الأوزان وقواعد الإنتاج يتطلب دورة مصنع + موافقة بشرية."
            ),
        }
        path = self.root / f"proposals-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
        path.write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8")
        (self.root / "latest.json").write_text(
            json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if proposals:
            get_ops_monitor().record_event(
                "factory_self_improve_proposals",
                detail=f"{len(proposals)} specialties need work",
            )
        batch["path"] = str(path)
        return batch
