"""LoRA specialty training jobs.

Real GPU fine-tuning is optional: when peft/transformers are absent we write a
reproducible job manifest + adapter placeholder so the ownership pipeline can
run end-to-end. Promote adapters only after EvalHarness gates pass.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from typing import TYPE_CHECKING

from app.config import Settings, get_settings

if TYPE_CHECKING:
    from app.eval.harness import EvalHarness


SPECIALTY_ADAPTER = {
    "project_intelligence": "lora-project-intel",
    "coding": "lora-coding",
    "reasoning": "lora-reasoning",
    "critic": "lora-critic",
    "vision": "lora-vision",
    "embeddings": "lora-embeddings",
}


class LoRATrainer:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = Path(self.settings.training_artifacts_root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.adapters_root = self.root / "adapters"
        self.adapters_root.mkdir(parents=True, exist_ok=True)

    def _dataset_path(self, specialty: str) -> Path:
        return Path(self.settings.distillation_data_root) / specialty / "train.jsonl"

    def dataset_count(self, specialty: str) -> int:
        path = self._dataset_path(specialty)
        if not path.exists():
            return 0
        return sum(1 for line in path.open(encoding="utf-8") if line.strip())

    def adapter_status(self, specialty: str) -> dict[str, Any]:
        name = SPECIALTY_ADAPTER.get(specialty, f"lora-{specialty}")
        path = self.adapters_root / name
        meta_path = path / "adapter_meta.json"
        if not meta_path.exists():
            return {"specialty": specialty, "adapter": name, "ready": False, "path": str(path)}
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return {
            "specialty": specialty,
            "adapter": name,
            "ready": bool(meta.get("promoted")),
            "path": str(path),
            "meta": meta,
        }

    def list_adapters(self) -> list[dict[str, Any]]:
        return [self.adapter_status(s) for s in SPECIALTY_ADAPTER]

    async def train_specialty(
        self,
        specialty: str = "project_intelligence",
        *,
        run_eval: bool = True,
        force_placeholder: bool = False,
        harness: "EvalHarness | None" = None,
    ) -> dict[str, Any]:
        specialty = "project_intelligence" if specialty in ("pi", "project-intelligence") else specialty
        adapter = SPECIALTY_ADAPTER.get(specialty)
        if not adapter:
            return {"ok": False, "error": f"unknown specialty: {specialty}"}

        count = self.dataset_count(specialty)
        min_examples = int(self.settings.lora_min_examples)
        if count < min_examples and not force_placeholder:
            return {
                "ok": False,
                "error": f"need>={min_examples} verified JSONL examples, have {count}",
                "dataset_count": count,
                "hint": "Seed via distillation / project-intel seed, with tools_ok or tests_ok.",
            }

        out = self.adapters_root / adapter
        out.mkdir(parents=True, exist_ok=True)
        job = {
            "specialty": specialty,
            "adapter": adapter,
            "base_model": self.settings.internal_model_name or "evolve-base",
            "dataset": str(self._dataset_path(specialty)),
            "dataset_count": count,
            "method": "LoRA",
            "rank": self.settings.lora_rank,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "prepared",
            "promoted": False,
            "gpu_training": False,
        }

        # Attempt real training only if explicitly enabled and libs present
        if self.settings.lora_real_train_enabled and not force_placeholder:
            try:
                job.update(self._try_real_train(specialty, out))
            except Exception as exc:  # noqa: BLE001
                job["gpu_training_error"] = str(exc)
                job["status"] = "placeholder_after_error"
        else:
            # Placeholder adapter marker — pipeline-complete without GPU
            (out / "adapter_config.json").write_text(
                json.dumps(
                    {
                        "peft_type": "LORA",
                        "r": self.settings.lora_rank,
                        "target_modules": ["q_proj", "v_proj"],
                        "evolve_placeholder": True,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            job["status"] = "placeholder_ready_for_gpu"
            job["note"] = (
                "Manifest written. Enable LORA_REAL_TRAIN_ENABLED with peft/transformers "
                "on a GPU host to produce real weights; promotion still requires eval gates."
            )

        eval_report = None
        if run_eval:
            if harness is None:
                from app.eval.harness import get_eval_harness

                harness = get_eval_harness()
            try:
                eval_report = await harness.compare(specialty, persist=True)
                job["eval"] = {
                    "student_score": eval_report["student_score"],
                    "teacher_score": eval_report["teacher_score"],
                    "promote": eval_report["promote"],
                    "gates": eval_report["gates"],
                    "skip_teacher": eval_report.get("skip_teacher"),
                }
                if eval_report["promote"]:
                    job["eval_gates_passed"] = True
                    job["candidate_ready"] = True
                    if self.settings.factory_require_human_approval:
                        # Propose ≠ ship — production needs factory human approve
                        job["promoted"] = False
                        job["status"] = "pending_factory_approval"
                        job["factory_pending"] = True
                        job["note_promotion"] = (
                            "Eval gates passed. Awaiting Model Factory human approval "
                            "before production router trust."
                        )
                    else:
                        job["promoted"] = True
                        job["status"] = "promoted"
                else:
                    job["promoted"] = False
                    job["eval_gates_passed"] = False
                    job["candidate_ready"] = False
            except Exception as exc:  # noqa: BLE001 — keep adapter artifacts even if eval host flakes
                job["eval_error"] = str(exc)
                job["promoted"] = False
                job["candidate_ready"] = False

        meta_path = out / "adapter_meta.json"
        meta_path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        # Keep a copy of train slice fingerprint
        ds = self._dataset_path(specialty)
        if ds.exists():
            try:
                shutil.copy2(ds, out / "train.jsonl")
            except OSError as exc:
                job["dataset_copy_error"] = str(exc)

        return {"ok": True, "job": job, "eval": eval_report}

    def _try_real_train(self, specialty: str, out: Path) -> dict[str, Any]:
        """Run concrete short LoRA fine-tune when ML stack is installed."""
        from app.training.real_lora import run_real_lora_train

        return run_real_lora_train(
            specialty=specialty,
            dataset_path=self._dataset_path(specialty),
            out_dir=out,
            base_model=self.settings.internal_model_name or "",
            rank=int(self.settings.lora_rank),
            max_steps=int(getattr(self.settings, "lora_real_train_max_steps", 30) or 30),
            tiny_fallback=bool(getattr(self.settings, "lora_real_train_tiny_fallback", True)),
        )


_trainer: LoRATrainer | None = None


def get_lora_trainer() -> LoRATrainer:
    global _trainer
    if _trainer is None:
        _trainer = LoRATrainer()
    return _trainer
