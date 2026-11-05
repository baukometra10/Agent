"""AI Cost Efficiency — Internal Intelligence First economics meter.

Measures owned vs external share, costs, training burn, and cost per successful task.
Never optimize cost by sacrificing quality: escalate when internal quality is insufficient.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.distillation.engine import get_distillation_engine
from app.gateway.intelligent_router import get_intelligent_router

DOCTRINE = "Internal Intelligence First"
DOCTRINE_AR = "الذكاء الداخلي أولًا — الخارجي عند الضرورة فقط"
QUALITY_RULE = (
    "Never save cost by accepting lower quality on sensitive work; "
    "escalate to a stronger model when the internal student is below the gate."
)


class CostEfficiencyLedger:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = Path(self.settings.learning_data_root) / "economics"
        self.root.mkdir(parents=True, exist_ok=True)
        self.events_path = self.root / "cost_events.jsonl"
        self.training_path = self.root / "training_spend.json"

    def _load_training(self) -> dict[str, Any]:
        if not self.training_path.exists():
            return {"estimated_usd": 0.0, "jobs": 0, "updated_at": None}
        try:
            return json.loads(self.training_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"estimated_usd": 0.0, "jobs": 0, "updated_at": None}

    def _save_training(self, data: dict[str, Any]) -> None:
        self.training_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def record_event(
        self,
        *,
        tier: str,
        success: bool,
        specialty: str = "",
        tokens_in: int = 0,
        tokens_out: int = 0,
        estimated_usd: float | None = None,
        quality: float | None = None,
        escalated: bool = False,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        tin = max(0, int(tokens_in or 0))
        tout = max(0, int(tokens_out or 0))
        if estimated_usd is None:
            if tier == "teacher":
                estimated_usd = tin * 3e-6 + tout * 9e-6
            else:
                estimated_usd = tin * 2e-7 + tout * 2e-7
        row = {
            "id": str(uuid4()),
            "tier": tier,
            "success": bool(success),
            "specialty": specialty,
            "tokens_in": tin,
            "tokens_out": tout,
            "estimated_usd": round(float(estimated_usd), 8),
            "quality": quality,
            "escalated": bool(escalated),
            "meta": meta or {},
            "at": datetime.now(timezone.utc).isoformat(),
        }
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def record_training_spend(self, *, estimated_usd: float, job: str = "lora") -> dict[str, Any]:
        data = self._load_training()
        data["estimated_usd"] = float(data.get("estimated_usd") or 0) + float(estimated_usd)
        data["jobs"] = int(data.get("jobs") or 0) + 1
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        data["last_job"] = job
        self._save_training(data)
        self.record_event(
            tier="training",
            success=True,
            estimated_usd=estimated_usd,
            meta={"job": job},
        )
        return data

    def _iter_events(self, limit: int = 5000) -> list[dict[str, Any]]:
        if not self.events_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows[-limit:]

    def report(self) -> dict[str, Any]:
        router = get_intelligent_router().status()
        metrics = router.get("metrics") or {}
        distill = get_distillation_engine().stats()
        training = self._load_training()
        events = self._iter_events()

        internal_ok = int(metrics.get("internal_ok") or 0)
        teacher_ok = int(metrics.get("teacher_ok") or 0)
        successes = max(1, internal_ok + teacher_ok)
        internal_ratio = round(internal_ok / successes, 4) if (internal_ok + teacher_ok) else 0.0

        external_cost = 0.0
        internal_cost = 0.0
        quality_vals: list[float] = []
        success_events = 0
        for e in events:
            tier = e.get("tier")
            cost = float(e.get("estimated_usd") or 0)
            if tier == "teacher":
                external_cost += cost
            elif tier == "internal":
                internal_cost += cost
            if e.get("success") and tier in {"internal", "teacher"}:
                success_events += 1
            q = e.get("quality")
            if isinstance(q, (int, float)):
                quality_vals.append(float(q))

        # Fallback to router aggregate if ledger still empty
        router_cost = float(metrics.get("estimated_cost_usd") or 0)
        if external_cost + internal_cost <= 0 and router_cost > 0:
            # Split by share
            external_cost = router_cost * (1 - internal_ratio)
            internal_cost = router_cost * internal_ratio

        training_cost = float(training.get("estimated_usd") or 0)
        total_cost = external_cost + internal_cost + training_cost
        successful = max(success_events, internal_ok + teacher_ok, 1)
        cost_per_success = round(total_cost / successful, 6)
        avg_quality = round(sum(quality_vals) / len(quality_vals), 4) if quality_vals else None

        # Efficiency score 0..100 — reward internal share + quality, penalize external spend share
        quality_component = (avg_quality if avg_quality is not None else 0.7) * 40
        internal_component = internal_ratio * 45
        cost_component = max(0.0, 15 - min(15.0, total_cost * 100))
        score = round(min(100.0, quality_component + internal_component + cost_component), 1)

        return {
            "product": "Spixa",
            "metric": "AI Cost Efficiency",
            "doctrine": DOCTRINE,
            "doctrine_ar": DOCTRINE_AR,
            "quality_rule": QUALITY_RULE,
            "score": score,
            "internal_task_ratio": internal_ratio,
            "internal_tasks": internal_ok,
            "external_tasks": teacher_ok,
            "escalations": int(metrics.get("escalations") or 0),
            "external_cost_usd": round(external_cost, 6),
            "internal_run_cost_usd": round(internal_cost, 6),
            "training_update_cost_usd": round(training_cost, 6),
            "total_cost_usd": round(total_cost, 6),
            "avg_quality": avg_quality,
            "cost_per_successful_task_usd": cost_per_success,
            "cache_hits": int((router.get("cache") or {}).get("hits") or metrics.get("cache_hits") or 0),
            "distillation": {
                "enabled": distill.get("enabled"),
                "examples": distill.get("total_examples") or distill.get("examples"),
                "by_specialty": distill.get("by_specialty") or distill.get("specialties"),
            },
            "phases": [
                "External teachers seed students",
                "Simple tasks → owned models",
                "Recurring coding → owned coding model",
                "Project analysis → owned project intelligence",
                "Review & planning → owned reasoning/critic",
                "External only for hard gaps below quality gate",
            ],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


_ledger: CostEfficiencyLedger | None = None


def get_cost_efficiency_ledger() -> CostEfficiencyLedger:
    global _ledger
    if _ledger is None:
        _ledger = CostEfficiencyLedger()
    return _ledger
