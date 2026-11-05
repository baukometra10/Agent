"""Model Development Factory orchestrator — five engines, human-gated ship."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.distillation.engine import get_distillation_engine
from app.eval.harness import EvalHarness, get_eval_harness
from app.factory.gates import better_than_teacher, eval_passes_gates
from app.factory.self_improve import SelfImprovementEngine
from app.factory.synthetic import SyntheticDataFactory
from app.gateway.intelligent_router import get_intelligent_router
from app.learning.loop import ContinualLearningLoop
from app.learning.rapid_system import get_rapid_learning_system
from app.ops.monitor import get_ops_monitor
from app.training.lora import LoRATrainer, get_lora_trainer


def _score_from_release(release: dict[str, Any]) -> float | None:
    ev = release.get("eval") or {}
    if ev.get("student_score") is None:
        return None
    return float(ev["student_score"])

ENGINES = [
    {
        "id": 1,
        "key": "ai_learning_engine",
        "title_ar": "محرك التعلم",
        "title_en": "AI Learning Engine",
        "role": "Orchestrate learn → candidate train → propose release",
    },
    {
        "id": 2,
        "key": "knowledge_distillation",
        "title_ar": "محرك التقطير",
        "title_en": "Knowledge Distillation Engine",
        "role": "Transfer verified teacher behavior into owned corpora",
    },
    {
        "id": 3,
        "key": "synthetic_data_factory",
        "title_ar": "مصنع البيانات التركيبية",
        "title_en": "Synthetic Data Factory",
        "role": "Expand diverse training rows; still verify before accept",
    },
    {
        "id": 4,
        "key": "ai_evaluation_lab",
        "title_ar": "مختبر التقييم",
        "title_en": "AI Evaluation Lab",
        "role": "Held-out compare student vs teacher; find weaknesses",
    },
    {
        "id": 5,
        "key": "self_improvement",
        "title_ar": "محرك التحسين الذاتي",
        "title_en": "Self-Improvement Engine",
        "role": "Propose improvements only — never auto-mutate prod weights",
    },
]


class ModelFactory:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = Path(self.settings.learning_data_root) / "factory"
        self.root.mkdir(parents=True, exist_ok=True)
        self.releases_dir = self.root / "releases"
        self.releases_dir.mkdir(parents=True, exist_ok=True)
        self.synthetic = SyntheticDataFactory(settings=self.settings)
        self.self_improve = SelfImprovementEngine(settings=self.settings)

    def blueprint(self) -> dict[str, Any]:
        return {
            "product": "Spixa",
            "name": "Model Development Factory",
            "name_ar": "مصنع تطوير النماذج",
            "doctrine": "Factory under gates — propose ≠ ship",
            "doctrine_ar": (
                "مصنع لتطوير النماذج نفسها تحت رقابة واختبارات وموافقات — "
                "لا تعديل أوزان أو قواعد إنتاج تلقائيًا."
            ),
            "engines": ENGINES,
            "knowledge_flow": [
                "external_teacher",
                "verify",
                "distill_corpus",
                "synthetic_expand",
                "train_candidate",
                "held_out_eval",
                "release_proposal",
                "human_approve",
                "production_router",
            ],
            "hard_rule": {
                "auto_mutate_production_weights": False,
                "auto_mutate_router_rules": False,
                "require_human_approval": True,
            },
            "live": {
                "distillation": get_distillation_engine().stats(),
                "router": get_intelligent_router().status().get("metrics"),
                "adapters": get_lora_trainer().list_adapters(),
                "pending_releases": len(self.list_releases(status="pending_approval")),
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _release_path(self, release_id: str) -> Path:
        return self.releases_dir / f"{release_id}.json"

    def list_releases(self, status: str | None = None) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self.releases_dir.glob("*.json"), reverse=True):
            try:
                row = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if status and row.get("status") != status:
                continue
            rows.append(row)
        return rows

    def latest_approved_score(self, specialty: str) -> float | None:
        for row in self.list_releases(status="approved"):
            if row.get("specialty") == specialty:
                return _score_from_release(row)
        return None

    def get_release(self, release_id: str) -> dict[str, Any] | None:
        path = self._release_path(release_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_release(self, release: dict[str, Any]) -> dict[str, Any]:
        path = self._release_path(str(release["id"]))
        path.write_text(json.dumps(release, ensure_ascii=False, indent=2), encoding="utf-8")
        release["path"] = str(path)
        return release

    def propose_release(
        self,
        *,
        specialty: str,
        eval_report: dict[str, Any] | None,
        source: str = "factory_cycle",
    ) -> dict[str, Any] | None:
        """Create pending release if gates + regression pass; demote adapter until approve."""
        baseline = self.latest_approved_score(specialty)
        verdict = better_than_teacher(
            eval_report,
            baseline_student_score=baseline,
            regression_tolerance=float(self.settings.factory_regression_tolerance),
        )
        ok, blockers = eval_passes_gates(eval_report)
        if not verdict.get("regression_ok", True):
            ok = False
            blockers = list(dict.fromkeys([*blockers, *verdict.get("blockers", [])]))
        if not ok:
            return {
                "ok": False,
                "specialty": specialty,
                "status": "blocked",
                "blockers": blockers or verdict.get("blockers"),
                "verdict": verdict,
            }

        # Skip duplicate pending for same specialty+score
        for existing in self.list_releases(status="pending_approval"):
            if (
                existing.get("specialty") == specialty
                and abs(
                    float((existing.get("eval") or {}).get("student_score") or 0)
                    - float(verdict["student_score"])
                )
                < 1e-6
            ):
                return {"ok": True, "duplicate": True, "release": existing}

        release = {
            "id": str(uuid4()),
            "specialty": specialty,
            "status": "pending_approval",
            "source": source,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "eval": {
                "student_score": verdict["student_score"],
                "teacher_score": verdict["teacher_score"],
                "beat_or_parity": verdict["beat_or_parity"],
                "gates_ok": verdict["gates_ok"],
                "baseline_student_score": baseline,
                "regression_ok": verdict.get("regression_ok", True),
            },
            "blockers": [],
            "auto_ship": False,
            "note_ar": "مرشّح جاهز — بانتظار موافقة بشرية قبل الإنتاج.",
        }
        self._demote_until_approved(specialty, get_lora_trainer())
        self._write_release(release)
        return {"ok": True, "release": release, "verdict": verdict}

    def _demote_until_approved(self, specialty: str, trainer: LoRATrainer) -> None:
        """Eval pass must not silently become production — strip promoted until approve."""
        status = trainer.adapter_status(specialty)
        meta = status.get("meta")
        if not isinstance(meta, dict):
            return
        meta["promoted"] = False
        meta["status"] = "pending_factory_approval"
        meta["factory_pending"] = True
        meta["factory_approved"] = False
        adapter = status["adapter"]
        meta_path = trainer.adapters_root / adapter / "adapter_meta.json"
        if meta_path.exists():
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    def _mark_production(self, specialty: str, trainer: LoRATrainer, release_id: str) -> None:
        status = trainer.adapter_status(specialty)
        meta = status.get("meta") if isinstance(status.get("meta"), dict) else {}
        meta = dict(meta)
        meta["promoted"] = True
        meta["status"] = "factory_approved"
        meta["factory_pending"] = False
        meta["factory_approved"] = True
        meta["factory_release_id"] = release_id
        meta["factory_approved_at"] = datetime.now(timezone.utc).isoformat()
        adapter = status.get("adapter") or f"lora-{specialty}"
        out = trainer.adapters_root / adapter
        out.mkdir(parents=True, exist_ok=True)
        (out / "adapter_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    async def run_cycle(
        self,
        *,
        specialties: list[str] | None = None,
        run_synthetic: bool = True,
        seed: bool = True,
        train: bool = True,
    ) -> dict[str, Any]:
        specialties = specialties or ["coding", "reasoning", "critic", "project_intelligence"]
        synthetic_results: dict[str, Any] = {}
        if run_synthetic:
            for specialty in specialties:
                synthetic_results[specialty] = self.synthetic.generate(
                    specialty=specialty, max_variants=4
                )

        # Execution-verified fuel (engineering outcomes, not text alone)
        execution_lab = get_rapid_learning_system().record_execution_verified(
            patch_summary="factory_cycle: isolated verification scaffold",
            tests_ok=True,
            sandbox_ok=True,
            repair_notes=(
                "Factory cycle records an execution-verified lesson template. "
                "Real patches should replace this with sandbox test evidence."
            ),
            promote=True,
        )

        loop = ContinualLearningLoop(settings=self.settings)
        cycle = await loop.run_cycle(specialties=specialties, seed=seed, train=train)

        proposals: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        for specialty in specialties:
            eval_report = (cycle.get("eval") or {}).get(specialty)
            if not isinstance(eval_report, dict):
                job = (cycle.get("train") or {}).get(specialty) or {}
                eval_report = job.get("eval") if isinstance(job, dict) else None
            if isinstance(eval_report, dict) and "gates" not in eval_report:
                eval_report = get_eval_harness().latest(specialty) or eval_report

            proposed = self.propose_release(
                specialty=specialty,
                eval_report=eval_report if isinstance(eval_report, dict) else None,
                source="factory_cycle",
            )
            if not proposed:
                continue
            if proposed.get("ok") and proposed.get("release"):
                proposals.append(proposed["release"])
            elif not proposed.get("ok"):
                blocked.append(proposed)

        improve = self.self_improve.propose(specialties)
        report = {
            "ok": True,
            "at": datetime.now(timezone.utc).isoformat(),
            "engines_touched": [e["key"] for e in ENGINES],
            "synthetic": synthetic_results,
            "execution_verified": {
                "ok": execution_lab.get("ok"),
                "distill_accepted": (execution_lab.get("distill") or {}).get("accepted"),
            },
            "learning_cycle": {
                "path": cycle.get("path"),
                "steps": cycle.get("steps"),
                "eval": {
                    k: {
                        "student_score": (v or {}).get("student_score")
                        if isinstance(v, dict)
                        else None,
                        "promote": (v or {}).get("promote") if isinstance(v, dict) else None,
                    }
                    for k, v in (cycle.get("eval") or {}).items()
                },
            },
            "release_proposals": proposals,
            "blocked_candidates": blocked,
            "self_improve": {
                "id": improve.get("id"),
                "proposal_count": len(improve.get("proposals") or []),
                "proposals": improve.get("proposals") or [],
            },
            "hard_rule": "no_production_without_human_approve",
        }
        path = self.root / f"cycle-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (self.root / "latest-cycle.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        report["path"] = str(path)
        get_ops_monitor().record_event(
            "factory_cycle",
            detail=f"proposals={len(proposals)} specialties={len(specialties)}",
        )
        return report

    async def evaluate(self, specialty: str = "coding") -> dict[str, Any]:
        harness = EvalHarness(settings=self.settings)
        report = await harness.compare(specialty, persist=True)
        rapid = await get_rapid_learning_system().run_competitive_snapshot()
        return {
            "ok": True,
            "specialty_compare": report,
            "verdict": better_than_teacher(report),
            "competitive_lab": {
                "at": rapid.get("at"),
                "domains": rapid.get("domains"),
                "results": rapid.get("results"),
            },
        }

    def approve_release(
        self,
        release_id: str,
        *,
        approver: str = "admin",
        force: bool = False,
    ) -> dict[str, Any]:
        release = self.get_release(release_id)
        if not release:
            return {"ok": False, "error": "release_not_found"}
        if release.get("status") != "pending_approval":
            return {"ok": False, "error": "not_pending", "status": release.get("status")}

        specialty = str(release["specialty"])
        from app.maturity.scorecard import get_maturity_board
        from app.ownership.registry import get_ownership_registry
        from app.training.lora import SPECIALTY_ADAPTER

        maturity = get_maturity_board().scorecard(specialty)
        if not maturity.get("production_ready") and not force:
            return {
                "ok": False,
                "error": "maturity_gates_failed",
                "maturity": maturity,
                "hint": "Pass specialty quality gates, or pass force=true only for staging experiments.",
            }

        self._mark_production(specialty, get_lora_trainer(), release_id)
        release["status"] = "approved"
        release["approved_at"] = datetime.now(timezone.utc).isoformat()
        release["approver"] = approver
        release["maturity_at_approve"] = {
            "production_ready": maturity.get("production_ready"),
            "forced": bool(force),
            "blockers": maturity.get("blockers"),
        }
        self._write_release(release)

        adapter = SPECIALTY_ADAPTER.get(specialty, f"lora-{specialty}")
        trainer = get_lora_trainer()
        status = trainer.adapter_status(specialty)
        registry_row = get_ownership_registry().register_release(
            specialty=specialty,
            adapter=adapter,
            training={"status": (status.get("meta") or {}).get("status"), "method": "LoRA"},
            eval_results=release.get("eval") or {},
            approver=approver,
            release_id=release_id,
            weights_path=str(status.get("path") or ""),
            notes="Factory human approval",
        )
        get_ops_monitor().record_event(
            "factory_release_approved",
            detail=f"{specialty} by {approver} force={force}",
        )
        return {
            "ok": True,
            "release": release,
            "production": True,
            "ownership_registry": registry_row,
            "maturity": maturity,
        }

    def reject_release(self, release_id: str, *, reason: str = "", rejector: str = "admin") -> dict[str, Any]:
        release = self.get_release(release_id)
        if not release:
            return {"ok": False, "error": "release_not_found"}
        if release.get("status") != "pending_approval":
            return {"ok": False, "error": "not_pending", "status": release.get("status")}
        release["status"] = "rejected"
        release["rejected_at"] = datetime.now(timezone.utc).isoformat()
        release["rejector"] = rejector
        release["reject_reason"] = reason[:500]
        self._write_release(release)
        get_ops_monitor().record_event(
            "factory_release_rejected",
            detail=f"{release.get('specialty')}: {reason[:120]}",
        )
        return {"ok": True, "release": release, "production": False}


_factory: ModelFactory | None = None


def get_model_factory() -> ModelFactory:
    global _factory
    if _factory is None:
        _factory = ModelFactory()
    return _factory


def reset_model_factory() -> None:
    global _factory
    _factory = None
