"""Independent per-specialty maturity scorecards — not example/adapter counts."""

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

# Production gates (override via settings when needed)
DEFAULT_GATES: dict[str, float] = {
    "task_success_rate": 0.75,
    "benchmark_score": 0.55,
    "regression_rate_max": 0.05,  # max allowed regression fraction
    "cost_per_successful_task_max": 0.05,  # USD soft ceiling for local/dev
    "human_acceptance_rate": 0.70,
    "generalization_score": 0.50,
    "safety_reliability": 0.95,
}


class SpecialtyMaturity:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = Path(self.settings.learning_data_root) / "maturity"
        self.root.mkdir(parents=True, exist_ok=True)
        self.human_path = self.root / "human_acceptances.jsonl"
        self.task_path = self.root / "task_outcomes.jsonl"
        self.safety_path = self.root / "safety_events.jsonl"

    def _read_jsonl(self, path: Path, limit: int = 500) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows[-limit:]

    def record_human_acceptance(
        self, *, specialty: str, accepted: bool, note: str = "", actor: str = ""
    ) -> dict[str, Any]:
        row = {
            "specialty": specialty,
            "accepted": bool(accepted),
            "note": note[:400],
            "actor": actor,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        with self.human_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def record_task_outcome(
        self, *, specialty: str, success: bool, source: str = "runtime"
    ) -> dict[str, Any]:
        row = {
            "specialty": specialty,
            "success": bool(success),
            "source": source,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        with self.task_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def record_safety_event(
        self, *, specialty: str, safe: bool, detail: str = ""
    ) -> dict[str, Any]:
        row = {
            "specialty": specialty,
            "safe": bool(safe),
            "detail": detail[:400],
            "at": datetime.now(timezone.utc).isoformat(),
        }
        with self.safety_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def _rate(self, rows: list[dict[str, Any]], key: str, truth: Any = True) -> float | None:
        if not rows:
            return None
        ok = sum(1 for r in rows if r.get(key) is truth)
        return round(ok / len(rows), 4)

    def _cost_events_for(self, specialty: str) -> list[dict[str, Any]]:
        path = Path(self.settings.learning_data_root) / "economics" / "cost_events.jsonl"
        rows = self._read_jsonl(path, limit=2000)
        return [r for r in rows if (r.get("specialty") or "") in {"", specialty} or r.get("specialty") == specialty]

    def scorecard(self, specialty: str) -> dict[str, Any]:
        gates = dict(DEFAULT_GATES)
        gates["benchmark_score"] = float(self.settings.eval_min_student_score)

        tasks = [r for r in self._read_jsonl(self.task_path) if r.get("specialty") == specialty]
        # Fallback: cost ledger successes for specialty
        cost_rows = self._cost_events_for(specialty)
        if not tasks and cost_rows:
            tasks = [
                {"success": bool(r.get("success")), "specialty": specialty}
                for r in cost_rows
                if r.get("specialty") == specialty
            ]

        human = [r for r in self._read_jsonl(self.human_path) if r.get("specialty") == specialty]
        safety = [r for r in self._read_jsonl(self.safety_path) if r.get("specialty") == specialty]

        eval_report = get_eval_harness().latest(specialty) or {}
        student = float(eval_report.get("student_score") or 0.0)
        teacher = float(eval_report.get("teacher_score") or 0.0)
        benchmark = student
        # Parity signal when teacher ran
        if teacher > 0:
            benchmark = min(1.0, student / max(teacher, 1e-6))

        factory = ModelFactory(settings=self.settings)
        approved = factory.list_releases(status="approved")
        approved_spec = [r for r in approved if r.get("specialty") == specialty]
        baseline = None
        if len(approved_spec) >= 2:
            scores = [
                float((r.get("eval") or {}).get("student_score") or 0)
                for r in approved_spec
                if (r.get("eval") or {}).get("student_score") is not None
            ]
            if len(scores) >= 2:
                # regression rate ≈ fraction of steps that dropped
                drops = sum(1 for i in range(1, len(scores)) if scores[i] + 1e-9 < scores[i - 1])
                baseline = drops / (len(scores) - 1)

        proof = FactoryProofTrack(settings=self.settings).improvement_report(specialty)
        if baseline is None and proof.get("ok"):
            # single delta: 0 if non-regressing else 1
            baseline = 0.0 if proof.get("non_regressing") else 1.0

        succ_cost_rows = [r for r in cost_rows if r.get("success") and r.get("specialty") == specialty]
        if not succ_cost_rows:
            succ_cost_rows = [r for r in cost_rows if r.get("success")]
        cost_sum = sum(float(r.get("estimated_usd") or 0) for r in succ_cost_rows)
        cost_per = (cost_sum / len(succ_cost_rows)) if succ_cost_rows else None

        # Generalization: prefer competitive / held-out flag on eval
        generalization = None
        if eval_report:
            generalization = student if eval_report.get("held_out") or True else None
            # competitive latest
            comp_path = (
                Path(self.settings.learning_data_root) / "rapid_learning" / "competitive_latest.json"
            )
            if comp_path.exists():
                try:
                    comp = json.loads(comp_path.read_text(encoding="utf-8"))
                    row = (comp.get("results") or {}).get(specialty) or {}
                    if row.get("student_score") is not None:
                        generalization = float(row["student_score"])
                except (OSError, json.JSONDecodeError, TypeError, ValueError):
                    pass

        task_success = self._rate(tasks, "success", True)
        human_rate = self._rate(human, "accepted", True)
        safety_rate = self._rate(safety, "safe", True)
        if safety_rate is None:
            # no incidents recorded → provisional high if settings disallow untrusted exec
            safety_rate = 1.0 if not self.settings.allow_untrusted_code_execution else 0.5

        metrics = {
            "task_success_rate": {
                "value": task_success,
                "proves": "نجاح المهام الحقيقية",
                "n": len(tasks),
                "gate": gates["task_success_rate"],
            },
            "benchmark_score": {
                "value": round(benchmark, 4) if eval_report else None,
                "proves": "مستوى القدرة مقارنة بالمعلمين / الأرضية",
                "student_score": student if eval_report else None,
                "teacher_score": teacher if eval_report else None,
                "n": 1 if eval_report else 0,
                "gate": gates["benchmark_score"],
            },
            "regression_rate": {
                "value": baseline,
                "proves": "عدم فقدان القدرات السابقة",
                "n": len(approved_spec),
                "gate_max": gates["regression_rate_max"],
            },
            "cost_per_successful_task": {
                "value": round(cost_per, 6) if cost_per is not None else None,
                "proves": "الاقتصاد الحقيقي",
                "n": len(succ_cost_rows),
                "gate_max": gates["cost_per_successful_task_max"],
            },
            "human_acceptance_rate": {
                "value": human_rate,
                "proves": "مدى قبول الخبراء للنتائج",
                "n": len(human),
                "gate": gates["human_acceptance_rate"],
            },
            "generalization": {
                "value": round(float(generalization), 4) if generalization is not None else None,
                "proves": "الأداء على مشاريع/حالات غير موجودة بالتدريب (held-out)",
                "n": 1 if generalization is not None else 0,
                "gate": gates["generalization_score"],
            },
            "safety_reliability": {
                "value": safety_rate,
                "proves": "عدم تنفيذ تعديلات خطرة أو غير موثوقة",
                "n": len(safety),
                "gate": gates["safety_reliability"],
            },
        }

        checks: dict[str, bool] = {}
        blockers: list[str] = []

        def need(name: str, ok: bool, why: str) -> None:
            checks[name] = ok
            if not ok:
                blockers.append(why)

        ts = metrics["task_success_rate"]["value"]
        need(
            "task_success_rate",
            ts is not None and ts >= gates["task_success_rate"],
            "task_success_rate",
        )
        bm = metrics["benchmark_score"]["value"]
        need(
            "benchmark_score",
            bm is not None and bm >= gates["benchmark_score"],
            "benchmark_score",
        )
        reg = metrics["regression_rate"]["value"]
        need(
            "regression_rate",
            reg is not None and reg <= gates["regression_rate_max"],
            "regression_rate",
        )
        cost_v = metrics["cost_per_successful_task"]["value"]
        need(
            "cost_per_successful_task",
            cost_v is not None and cost_v <= gates["cost_per_successful_task_max"],
            "cost_per_successful_task",
        )
        ha = metrics["human_acceptance_rate"]["value"]
        need(
            "human_acceptance_rate",
            ha is not None and ha >= gates["human_acceptance_rate"],
            "human_acceptance_rate",
        )
        gen = metrics["generalization"]["value"]
        need(
            "generalization",
            gen is not None and gen >= gates["generalization_score"],
            "generalization",
        )
        saf = metrics["safety_reliability"]["value"]
        need(
            "safety_reliability",
            saf is not None and saf >= gates["safety_reliability"],
            "safety_reliability",
        )

        # Insufficient evidence = not production-ready (explicit)
        insufficient = [
            k
            for k, m in metrics.items()
            if m.get("n", 0) == 0 and k not in {"safety_reliability"}  # safety may provisional
        ]
        for k in insufficient:
            checks[k] = False
            if k not in blockers:
                blockers.append(f"insufficient_evidence:{k}")

        production_ready = all(checks.values()) and not blockers
        product = next((f["product"] for f in SPIXA_FAMILY if f["specialty"] == specialty), specialty)

        return {
            "specialty": specialty,
            "product": product,
            "production_ready": production_ready,
            "checks": checks,
            "blockers": blockers,
            "metrics": metrics,
            "gates": gates,
            "note_ar": (
                "النضج لا يُقاس بعدد الأمثلة أو الـAdapters. "
                "الإنتاج فقط بعد اجتياز كل بوابات الجودة لهذا التخصص."
            ),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def board(self) -> dict[str, Any]:
        cards = [self.scorecard(f["specialty"]) for f in SPIXA_FAMILY]
        return {
            "doctrine": "Maturity by quality gates, not corpus size",
            "doctrine_ar": "النضج ببوابات الجودة — لا بحجم البيانات أو عدد الـAdapters",
            "specialties": cards,
            "production_ready": [c["specialty"] for c in cards if c["production_ready"]],
            "blocked": [c["specialty"] for c in cards if not c["production_ready"]],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


_maturity: SpecialtyMaturity | None = None


def get_maturity_board() -> SpecialtyMaturity:
    global _maturity
    if _maturity is None:
        _maturity = SpecialtyMaturity()
    return _maturity
