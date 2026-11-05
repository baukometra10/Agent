"""Practical proof track — real LoRA → eval → factory release → successive gains."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.eval.harness import EvalHarness
from app.factory.orchestrator import ModelFactory
from app.gateway.intelligent_router import IntelligentModelRouter
from app.gateway.router import ModelGateway
from app.ops.monitor import get_ops_monitor
from app.training.lora import LoRATrainer


def probe_train_stack() -> dict[str, Any]:
    missing = [
        name
        for name in ("torch", "transformers", "peft", "datasets")
        if importlib.util.find_spec(name) is None
    ]
    cuda = False
    device = None
    torch_version = None
    if "torch" not in missing:
        import torch

        torch_version = torch.__version__
        cuda = bool(torch.cuda.is_available())
        if cuda:
            device = torch.cuda.get_device_name(0)
    return {
        "packages_ok": len(missing) == 0,
        "missing": missing,
        "torch_version": torch_version,
        "cuda": cuda,
        "device": device,
        "ready_for_real_lora": len(missing) == 0,
    }


class FactoryProofTrack:
    """Run measurable coding ownership proofs under human-gated factory rules."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = Path(self.settings.learning_data_root) / "factory" / "proof"
        self.root.mkdir(parents=True, exist_ok=True)
        self.history_path = self.root / "coding_release_history.jsonl"
        self.factory = ModelFactory(settings=self.settings)

    def history(self, specialty: str = "coding", limit: int = 20) -> list[dict[str, Any]]:
        if not self.history_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.history_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("specialty") == specialty:
                rows.append(row)
        return rows[-limit:]

    def improvement_report(self, specialty: str = "coding") -> dict[str, Any]:
        rows = self.history(specialty=specialty, limit=50)
        scored = [r for r in rows if r.get("student_score") is not None]
        if len(scored) < 2:
            return {
                "ok": False,
                "specialty": specialty,
                "points": len(scored),
                "proof": "insufficient_successive_releases",
                "note_ar": "يلزم إصدارين متعاقبين على الأقل لإثبات التحسن.",
                "history": scored,
            }
        first = scored[0]
        last = scored[-1]
        delta = float(last["student_score"]) - float(first["student_score"])
        return {
            "ok": True,
            "specialty": specialty,
            "points": len(scored),
            "first": first,
            "latest": last,
            "delta_student_score": round(delta, 4),
            "improved": delta > 0,
            "non_regressing": delta >= -float(self.settings.factory_regression_tolerance),
            "history": scored,
            "note_ar": (
                "تحسن عبر الإصدارات" if delta > 0 else "لا تحسن صافٍ بعد — راجع بيانات/تدريب"
            ),
        }

    def _append_history(self, row: dict[str, Any]) -> None:
        with self.history_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    async def run_coding_proof(
        self,
        *,
        real_train: bool = True,
        approve_if_gates_pass: bool = False,
        approver: str = "proof_operator",
        max_steps: int | None = None,
        label: str = "",
    ) -> dict[str, Any]:
        stack = probe_train_stack()
        specialty = "coding"
        trainer = LoRATrainer(settings=self.settings)
        gateway = ModelGateway(
            settings=self.settings, router=IntelligentModelRouter(settings=self.settings)
        )
        harness = EvalHarness(settings=self.settings, gateway=gateway)

        run_settings = self.settings
        if real_train:
            if not stack["packages_ok"]:
                return {
                    "ok": False,
                    "error": "train_stack_missing",
                    "stack": stack,
                    "hint": "pip install 'spixa[train]' or: pip install torch transformers peft datasets",
                    "note_ar": "حزم التدريب غير مثبتة — لا يمكن إثبات LoRA الحقيقي بعد.",
                }
            updates: dict[str, Any] = {"lora_real_train_enabled": True}
            if max_steps is not None:
                updates["lora_real_train_max_steps"] = int(max_steps)
            run_settings = self.settings.model_copy(update=updates)
            trainer = LoRATrainer(settings=run_settings)
            self.factory = ModelFactory(settings=run_settings)

        train_result = await trainer.train_specialty(
            specialty,
            run_eval=True,
            force_placeholder=not real_train,
            harness=harness,
        )

        job = (train_result.get("job") or {}) if train_result.get("ok") else {}
        eval_report = train_result.get("eval")
        if not isinstance(eval_report, dict) or "gates" not in eval_report:
            eval_report = harness.latest(specialty) or eval_report

        proposed = self.factory.propose_release(
            specialty=specialty,
            eval_report=eval_report if isinstance(eval_report, dict) else None,
            source="coding_proof",
        )

        approval: dict[str, Any] | None = None
        release = (proposed or {}).get("release") if isinstance(proposed, dict) else None
        if (
            approve_if_gates_pass
            and isinstance(proposed, dict)
            and proposed.get("ok")
            and release
            and not proposed.get("duplicate")
        ):
            approval = self.factory.approve_release(str(release["id"]), approver=approver)
            release = (approval or {}).get("release") or release

        student = None
        teacher = None
        if isinstance(eval_report, dict):
            student = eval_report.get("student_score")
            teacher = eval_report.get("teacher_score")

        hist = {
            "id": str(uuid4()),
            "at": datetime.now(timezone.utc).isoformat(),
            "specialty": specialty,
            "label": label or f"proof-{datetime.now(timezone.utc).strftime('%H%M%S')}",
            "student_score": student,
            "teacher_score": teacher,
            "gpu_training": bool(job.get("gpu_training")),
            "real_train": bool(job.get("real_train") or job.get("gpu_training")),
            "train_status": job.get("status"),
            "base_model_used": job.get("base_model_used"),
            "candidate_ready": bool(job.get("candidate_ready")),
            "promoted": bool(job.get("promoted"))
            or bool((release or {}).get("status") == "approved"),
            "release_id": (release or {}).get("id"),
            "release_status": (release or {}).get("status"),
            "cuda": stack.get("cuda"),
            "device": stack.get("device") or job.get("device"),
        }
        self._append_history(hist)

        improve = self.improvement_report(specialty)
        real_weights = bool(job.get("real_train") or job.get("status") == "trained")
        coding_ready = bool(
            (release or {}).get("status") == "approved"
            or trainer.adapter_status(specialty).get("ready")
        )
        report = {
            "ok": bool(train_result.get("ok")),
            "proof_id": hist["id"],
            "stack": stack,
            "hardware_note": {
                "nvidia_present_hint": "Check nvidia-smi on host",
                "torch_cuda": stack.get("cuda"),
                "note_ar": (
                    "GPU في الجهاز لا يكفي وحده — يلزم عجلة torch CUDA متوافقة مع Python."
                    if not stack.get("cuda")
                    else "CUDA جاهز للتدريب على GPU."
                ),
            },
            "train": {
                "ok": train_result.get("ok"),
                "real_train": real_weights,
                "gpu_training": job.get("gpu_training"),
                "status": job.get("status"),
                "base_model_used": job.get("base_model_used"),
                "device": job.get("device"),
                "train_loss": job.get("train_loss"),
                "examples_used": job.get("examples_used"),
                "candidate_ready": job.get("candidate_ready"),
                "promoted": job.get("promoted"),
                "eval": job.get("eval"),
                "error": train_result.get("error"),
                "gpu_training_error": job.get("gpu_training_error"),
            },
            "factory_proposal": proposed,
            "approval": approval,
            "coding_production_ready": coding_ready,
            "successive_improvement": improve,
            "adapter": trainer.adapter_status(specialty),
            "at": hist["at"],
            "checklist": {
                "real_lora_weights": real_weights,
                "real_lora_on_cuda": bool(job.get("gpu_training")) and bool(stack.get("cuda")),
                "release_proposed_or_approved": bool(release),
                "coding_ready": coding_ready,
                "successive_gain_proven": bool(improve.get("improved")),
            },
        }
        path = self.root / f"proof-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (self.root / "latest.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        report["path"] = str(path)
        get_ops_monitor().record_event(
            "factory_coding_proof",
            detail=f"gpu={job.get('gpu_training')} ready={report['checklist']['coding_ready']}",
        )
        return report
