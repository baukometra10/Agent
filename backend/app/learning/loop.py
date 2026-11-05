"""Continuous Model Learning — fail → classify → distill → train → eval → promote."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.distillation.engine import DistillationEngine
from app.distillation.grow import grow_all_specialties
from app.eval.harness import EvalHarness
from app.gateway.host import probe_internal_host
from app.gateway.intelligent_router import IntelligentModelRouter
from app.gateway.router import ModelGateway
from app.training.lora import LoRATrainer


class ContinualLearningLoop:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = Path(self.settings.learning_data_root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.engine = DistillationEngine(settings=self.settings)
        self.router = IntelligentModelRouter(settings=self.settings)
        self.gateway = ModelGateway(settings=self.settings, router=self.router)
        self.harness = EvalHarness(settings=self.settings, gateway=self.gateway)
        self.trainer = LoRATrainer(settings=self.settings)

    def _workspaces(self) -> list[Path]:
        root = Path(self.settings.workspaces_root)
        if not root.exists():
            return []
        return [p for p in root.iterdir() if p.is_dir()]

    async def run_cycle(
        self,
        *,
        specialties: list[str] | None = None,
        seed: bool = True,
        train: bool = True,
    ) -> dict[str, Any]:
        specialties = specialties or [
            "project_intelligence",
            "coding",
            "reasoning",
            "critic",
            "vision",
        ]
        host = await probe_internal_host(self.settings)
        steps: list[dict[str, Any]] = []
        seed_results: dict[str, Any] = {}

        if seed:
            seed_results = grow_all_specialties(
                settings=self.settings,
                engine=self.engine,
                include_workspaces=True,
            )
            steps.append({"step": "grow_all_specialties", "ok": True})

        train_results: dict[str, Any] = {}
        eval_results: dict[str, Any] = {}

        for specialty in specialties:
            if train:
                job = await self.trainer.train_specialty(
                    specialty, run_eval=True, harness=self.harness
                )
                if not job.get("ok"):
                    job = await self.trainer.train_specialty(
                        specialty,
                        run_eval=True,
                        force_placeholder=True,
                        harness=self.harness,
                    )
                train_results[specialty] = job
                steps.append(
                    {
                        "step": f"train_{specialty}",
                        "ok": bool(job.get("ok")),
                        "promoted": bool((job.get("job") or {}).get("promoted")),
                    }
                )
                if job.get("eval"):
                    eval_results[specialty] = job["eval"]
            else:
                eval_results[specialty] = await self.harness.compare(specialty, persist=True)
                steps.append({"step": f"eval_{specialty}", "ok": True})

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "host": host,
            "seed": seed_results,
            "train": train_results,
            "eval": eval_results,
            "steps": steps,
            "doctrine": "fail→seed/distill→train→held-out eval→promote only on real gain",
            "note": (
                "Cycle does not train after every user task; run daily/weekly. "
                "External teachers remain escalate-only when keys exist."
            ),
        }
        path = self.root / f"cycle-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (self.root / "latest-cycle.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        report["path"] = str(path)
        return report


_loop: ContinualLearningLoop | None = None


def get_learning_loop() -> ContinualLearningLoop:
    global _loop
    if _loop is None:
        _loop = ContinualLearningLoop()
    return _loop
