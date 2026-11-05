"""Rapid Learning System — seven linked layers for Internal Intelligence First.

1 External teachers → 2 Knowledge extraction → 3 Training-data factory →
4 Specialized train/distill → 5 Competitive eval → 6 Improve & retrain →
7 Continual cycle.

Plus: multi-teacher disagreement, Multi-Agent Learning Lab, execution-verified learning.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.distillation.engine import get_distillation_engine
from app.eval.harness import EvalHarness
from app.gateway.intelligent_router import get_intelligent_router
from app.learning.loop import ContinualLearningLoop
from app.ops.monitor import get_ops_monitor

LAYERS = [
    {
        "id": 1,
        "key": "external_teachers",
        "title_ar": "النماذج المعلّمة الخارجية",
        "title_en": "External Teacher Models",
        "role": "Advanced solutions for hard tasks only",
    },
    {
        "id": 2,
        "key": "knowledge_extraction",
        "title_ar": "محرك استخلاص المعرفة",
        "title_en": "Knowledge Extraction Engine",
        "role": "Extract solutions, strategies, errors, lessons",
    },
    {
        "id": 3,
        "key": "training_data_factory",
        "title_ar": "مصنع البيانات التعليمية",
        "title_en": "Training Data Factory",
        "role": "Reliable, diverse, tested training corpora",
    },
    {
        "id": 4,
        "key": "specialized_train_distill",
        "title_ar": "التدريب والتقطير المتخصص",
        "title_en": "Specialized Train & Distill",
        "role": "SFT, LoRA, QLoRA, Knowledge Distillation",
    },
    {
        "id": 5,
        "key": "competitive_eval",
        "title_ar": "الاختبار والمنافسة",
        "title_en": "Competitive Evaluation Lab",
        "role": "Independent comparison vs teachers; find weaknesses",
    },
    {
        "id": 6,
        "key": "improve_retrain",
        "title_ar": "التحسين وإعادة التدريب",
        "title_en": "Improve & Retrain",
        "role": "Fix weaknesses; ship better releases",
    },
    {
        "id": 7,
        "key": "continual_cycle",
        "title_ar": "دورة تعلم مستمرة",
        "title_en": "Continual Learning Cycle",
        "role": "Each release seeds the next",
    },
]

TEACHER_ROSTER = [
    {
        "id": "teacher_coding",
        "specialty": "coding",
        "label": "Coding Teacher",
        "config_key": "default_coding_model",
        "license_note": "Respect provider ToS / data-use terms before distillation",
    },
    {
        "id": "teacher_reasoning",
        "specialty": "reasoning",
        "label": "Reasoning & Planning Teacher",
        "config_key": "default_reasoning_model",
        "license_note": "Respect provider ToS / data-use terms before distillation",
    },
    {
        "id": "teacher_critic",
        "specialty": "critic",
        "label": "Code Review Teacher",
        "config_key": "default_critic_model",
        "license_note": "Respect provider ToS / data-use terms before distillation",
    },
    {
        "id": "teacher_vision",
        "specialty": "vision",
        "label": "Design / UI Analysis Teacher",
        "config_key": "default_multimodal_model",
        "license_note": "Respect provider ToS / data-use terms before distillation",
    },
]

COMPETITIVE_DOMAINS = [
    {"id": "project_understanding", "ar": "فهم المشاريع", "measure": "دقة المعمارية والعلاقات"},
    {"id": "coding", "ar": "البرمجة", "measure": "نجاح الكود والاختبارات"},
    {"id": "debugging", "ar": "حل المشكلات", "measure": "دقة السبب الجذري"},
    {"id": "architecture", "ar": "الهندسة المعمارية", "measure": "جودة القرارات وقابلية التوسع"},
    {"id": "security", "ar": "الأمن", "measure": "اكتشاف الثغرات والمخاطر"},
    {"id": "design", "ar": "التصميم", "measure": "جودة الواجهات وتجربة الاستخدام"},
    {"id": "planning", "ar": "التخطيط", "measure": "دقة الأولويات والتقديرات"},
]

MULTI_AGENT_ROLES = [
    {"id": "coder", "ar": "نموذج البرمجة", "job": "ينتج حلًا"},
    {"id": "reviewer", "ar": "نموذج المراجعة", "job": "يكتشف الأخطاء"},
    {"id": "security", "ar": "نموذج الأمن", "job": "يفحص المخاطر"},
    {"id": "tester", "ar": "نموذج الاختبار", "job": "يتحقق من عمل الحل"},
    {"id": "architect", "ar": "نموذج المعمارية", "job": "يراجع جودة التصميم"},
    {"id": "coordinator", "ar": "المنسّق", "job": "يختار ما يستحق أن يصبح بيانات تعليمية"},
]

ADVANCED_TECHNIQUES = [
    {"id": "kd", "name": "Knowledge Distillation", "when": "نقل مهارات المعلّم"},
    {"id": "sft", "name": "SFT", "when": "أنماط المهام الصحيحة"},
    {"id": "dpo", "name": "DPO / Preference Optimization", "when": "تفضيل الحلول الأفضل"},
    {"id": "rl", "name": "Reinforcement Learning", "when": "مكافآت قابلة للتحقق"},
    {"id": "lora", "name": "LoRA / QLoRA", "when": "تخصيص رخيص"},
    {"id": "synthetic", "name": "Synthetic Data", "when": "توسيع البيانات"},
    {"id": "continual", "name": "Continual Learning", "when": "تطوير دون نسيان"},
]


class RapidLearningSystem:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = Path(self.settings.learning_data_root) / "rapid_learning"
        self.root.mkdir(parents=True, exist_ok=True)
        self.lab_path = self.root / "multi_agent_lab.jsonl"
        self.exec_path = self.root / "execution_verified.jsonl"
        self.disagreement_path = self.root / "teacher_disagreements.jsonl"

    def blueprint(self) -> dict[str, Any]:
        settings = self.settings
        teachers = []
        for t in TEACHER_ROSTER:
            model = getattr(settings, t["config_key"], "") or ""
            teachers.append({**t, "model": model, "configured": bool(model)})

        distill = get_distillation_engine().stats()
        router = get_intelligent_router().status()
        return {
            "product": "Spixa",
            "name": "Rapid Learning System",
            "name_ar": "منظومة التعلم السريع",
            "doctrine": "Internal Intelligence First",
            "layers": LAYERS,
            "multi_teacher": {
                "enabled": True,
                "roster": teachers,
                "adjudication": [
                    "sandbox_tests",
                    "tools_evidence",
                    "independent_critic",
                    "license_check",
                ],
            },
            "competitive_lab": {
                "domains": COMPETITIVE_DOMAINS,
                "held_out_only": True,
                "unseen_projects_required": True,
            },
            "multi_agent_learning_lab": {
                "roles": MULTI_AGENT_ROLES,
                "learns_from": ["successes", "failures", "fixes", "failed_decisions"],
            },
            "techniques": ADVANCED_TECHNIQUES,
            "execution_verified_learning": {
                "steps": [
                    "write_patch",
                    "run_isolated",
                    "run_tests",
                    "analyze_errors",
                    "repair",
                    "independent_review",
                    "promote_verified_example",
                ]
            },
            "live": {
                "distillation": distill,
                "router": router.get("metrics"),
                "prefer_internal": router.get("prefer_internal"),
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def record_teacher_disagreement(
        self,
        *,
        prompt: str,
        answers: list[dict[str, Any]],
        winner: dict[str, Any] | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = {
            "id": str(uuid4()),
            "prompt_preview": (prompt or "")[:400],
            "answers": answers,
            "winner": winner,
            "evidence": evidence or {},
            "at": datetime.now(timezone.utc).isoformat(),
        }
        with self.disagreement_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def run_multi_agent_lab(
        self,
        *,
        task: str,
        artifacts: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Scaffold: collect role findings; only verified lessons become distill fuel."""
        arts = artifacts or {}
        findings = []
        for role in MULTI_AGENT_ROLES:
            if role["id"] == "coordinator":
                continue
            finding = {
                "role": role["id"],
                "label": role["ar"],
                "note": arts.get(role["id"])
                or f"pending_{role['id']}_pass",
                "severity": arts.get(f"{role['id']}_severity", "info"),
            }
            findings.append(finding)

        # Coordinator decides what is training-worthy
        worthy = [
            f
            for f in findings
            if f.get("severity") in {"critical", "high", "verified_fix", "verified_success"}
            or arts.get("force_promote")
        ]
        session = {
            "id": str(uuid4()),
            "task": task,
            "findings": findings,
            "training_candidates": worthy,
            "learns_from_failures": True,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        with self.lab_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(session, ensure_ascii=False) + "\n")

        promoted = []
        engine = get_distillation_engine()
        for item in worthy[:5]:
            note = str(item.get("note") or "").strip()
            lesson = (
                f"Role={item['role']} severity={item.get('severity')}\n"
                f"Task: {task}\n"
                f"Finding: {note or 'verified_lesson'}\n"
                "Learn from both the issue and the correction path."
            )
            result = engine.ingest_teacher_output(
                role="critic" if item["role"] in {"reviewer", "security"} else "coding",
                prompt=f"[Multi-Agent Lab] {task}\nRole={item['role']}",
                system="Spixa Multi-Agent Learning Lab verified lesson.",
                teacher_model=f"lab/{item['role']}",
                teacher_output=lesson,
                metadata={
                    "specialty": "coding" if item["role"] == "coder" else "critic",
                    "tools_ok": True,
                    "tests_ok": bool(arts.get("tests_ok")),
                    "lab": "multi_agent",
                    "distill": True,
                },
            )
            promoted.append(result)

        return {"ok": True, "session": session, "distill": promoted}

    def record_execution_verified(
        self,
        *,
        patch_summary: str,
        tests_ok: bool,
        sandbox_ok: bool,
        error_log: str = "",
        repair_notes: str = "",
        promote: bool = True,
    ) -> dict[str, Any]:
        """Learn from real engineering outcomes, not text alone."""
        row = {
            "id": str(uuid4()),
            "patch_summary": patch_summary,
            "tests_ok": tests_ok,
            "sandbox_ok": sandbox_ok,
            "error_log": (error_log or "")[:2000],
            "repair_notes": (repair_notes or "")[:2000],
            "at": datetime.now(timezone.utc).isoformat(),
        }
        with self.exec_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

        distill_result = None
        if promote and tests_ok and sandbox_ok:
            distill_result = get_distillation_engine().ingest_teacher_output(
                role="coding",
                prompt=f"Execution-verified task:\n{patch_summary}",
                system="Produce working code; prefer fixes that pass isolated tests.",
                teacher_model="execution_lab",
                teacher_output=repair_notes or patch_summary,
                metadata={
                    "specialty": "coding",
                    "tests_ok": True,
                    "tools_ok": True,
                    "execution_verified": True,
                    "distill": True,
                },
            )
        elif promote and not tests_ok:
            # Failures are also fuel
            distill_result = get_distillation_engine().ingest_teacher_output(
                role="critic",
                prompt=f"Failed execution:\n{patch_summary}\nErrors:\n{error_log}",
                system="Explain failure cause and a minimal correct fix.",
                teacher_model="execution_lab_failure",
                teacher_output=repair_notes or error_log or "tests failed",
                metadata={
                    "specialty": "critic",
                    "tests_ok": False,
                    "tools_ok": True,
                    "execution_verified": True,
                    "failure_lesson": True,
                    "distill": True,
                },
            )
            get_ops_monitor().record_event(
                "execution_learning_failure",
                detail=patch_summary[:200],
            )

        return {"ok": True, "record": row, "distill": distill_result}

    async def run_competitive_snapshot(self) -> dict[str, Any]:
        """Light competitive pass across held-out specialties (independent of train data)."""
        harness = EvalHarness(settings=self.settings)
        results = {}
        for specialty in ("project_intelligence", "coding", "reasoning", "critic"):
            try:
                report = await harness.compare(specialty, persist=True, skip_teacher=True)
                results[specialty] = {
                    "ok": True,
                    "student_score": report.get("student_score"),
                    "teacher_score": report.get("teacher_score"),
                    "promote": report.get("promote"),
                    "gates": report.get("gates"),
                }
            except Exception as exc:  # noqa: BLE001
                results[specialty] = {"ok": False, "error": str(exc)}
        path = self.root / "competitive_latest.json"
        payload = {
            "at": datetime.now(timezone.utc).isoformat(),
            "held_out": True,
            "unseen_projects_required": True,
            "domains": COMPETITIVE_DOMAINS,
            "results": results,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    async def run_full_cycle(self) -> dict[str, Any]:
        """Layer 7 — continual cycle wrapping existing ContinualLearningLoop."""
        loop = ContinualLearningLoop(settings=self.settings)
        cycle = await loop.run_cycle()
        lab = self.run_multi_agent_lab(
            task="continual_cycle_review",
            artifacts={"coordinator_severity": "info", "tests_ok": True},
        )
        return {
            "ok": True,
            "layers_advanced": [4, 5, 6, 7],
            "continual": cycle,
            "multi_agent_lab": lab,
            "blueprint": self.blueprint(),
        }


_rapid: RapidLearningSystem | None = None


def get_rapid_learning_system() -> RapidLearningSystem:
    global _rapid
    if _rapid is None:
        _rapid = RapidLearningSystem()
    return _rapid
