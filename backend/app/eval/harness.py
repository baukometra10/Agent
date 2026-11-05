"""Teacher vs Student evaluation harness with promotion gates."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.eval.suite import EvalCase, score_answer, suite_for
from app.gateway.router import ModelGateway, get_model_gateway
from app.gateway.types import ModelRole


SPECIALTY_ROLE: dict[str, ModelRole] = {
    "project_intelligence": ModelRole.reasoning,
    "coding": ModelRole.coding,
    "reasoning": ModelRole.reasoning,
    "critic": ModelRole.critic,
    "vision": ModelRole.multimodal,
    "embeddings": ModelRole.embedding,
}


class EvalHarness:
    def __init__(self, settings: Settings | None = None, gateway: ModelGateway | None = None) -> None:
        self.settings = settings or get_settings()
        self.gateway = gateway or get_model_gateway()
        self.root = Path(self.settings.eval_data_root)
        self.root.mkdir(parents=True, exist_ok=True)

    async def run_case(
        self,
        case: EvalCase,
        *,
        tier: str,
    ) -> dict[str, Any]:
        role = SPECIALTY_ROLE.get(case.specialty, ModelRole.reasoning)
        specialty_model = {
            "project_intelligence": "internal/project-intelligence",
            "coding": "internal/coding",
            "reasoning": "internal/reasoning",
            "critic": "internal/critic",
            "vision": "internal/vision",
            "embeddings": "internal/embeddings",
        }.get(case.specialty)

        # Student path: one direct specialty call (avoid gateway escalate + double Ollama hits)
        if tier == "internal" and specialty_model:
            from app.gateway.internal import internal_chat

            try:
                content, tin, tout, raw, stubbed = await internal_chat(
                    settings=self.settings,
                    model_id=specialty_model,
                    prompt=case.prompt,
                    system=case.system,
                    use_eval_model=True,
                )
                score = score_answer(case, content)
                return {
                    "case_id": case.id,
                    "tier": tier,
                    "model_id": specialty_model,
                    "served_model": (raw or {}).get("served_model"),
                    "score": score,
                    "simulated": stubbed,
                    "error": None,
                    "content_preview": content[:280],
                    "tokens_in": tin,
                    "tokens_out": tout,
                }
            except Exception as exc:  # noqa: BLE001 — timeouts / host flakes must not kill the suite
                return {
                    "case_id": case.id,
                    "tier": tier,
                    "model_id": specialty_model,
                    "score": 0.0,
                    "simulated": False,
                    "error": str(exc),
                    "content_preview": f"[eval-error] {exc}"[:280],
                    "tokens_in": 0,
                    "tokens_out": 0,
                }

        meta: dict[str, Any] = {
            "eval": True,
            "eval_case": case.id,
            "skip_cache": True,
            "specialty": case.specialty,
            "force_teacher": True,
        }
        response = await self.gateway.complete(
            role,
            case.prompt,
            system=case.system,
            metadata=meta,
        )
        score = score_answer(case, response.content)
        return {
            "case_id": case.id,
            "tier": tier,
            "model_id": response.model_id,
            "score": score,
            "simulated": response.simulated,
            "error": response.error,
            "content_preview": (response.content or "")[:280],
            "tokens_in": response.tokens_in,
            "tokens_out": response.tokens_out,
        }

    async def compare(
        self,
        specialty: str = "project_intelligence",
        *,
        persist: bool = True,
        skip_teacher: bool | None = None,
    ) -> dict[str, Any]:
        cases = suite_for(specialty)
        student_rows: list[dict[str, Any]] = []
        teacher_rows: list[dict[str, Any]] = []
        keyed = bool(
            (self.settings.openai_api_key or "").strip()
            or (self.settings.anthropic_api_key or "").strip()
        )
        if skip_teacher is None:
            skip_teacher = not keyed

        for case in cases:
            student_rows.append(await self.run_case(case, tier="internal"))
            if not skip_teacher:
                teacher_rows.append(await self.run_case(case, tier="teacher"))

        def weighted(rows: list[dict[str, Any]]) -> float:
            if not rows:
                return 0.0
            total_w = sum(c.weight for c in cases) or 1.0
            by_id = {r["case_id"]: r["score"] for r in rows}
            return round(sum(by_id.get(c.id, 0.0) * c.weight for c in cases) / total_w, 4)

        student_score = weighted(student_rows)
        teacher_score = weighted(teacher_rows)
        min_abs = float(self.settings.eval_min_student_score)
        ratio_ok = teacher_score <= 0 or student_score >= teacher_score * float(
            self.settings.eval_teacher_parity_ratio
        )
        abs_ok = student_score >= min_abs
        # Stubs cannot promote
        stubbed = any(r.get("simulated") for r in student_rows)
        promote = bool(ratio_ok and abs_ok and not stubbed)

        report = {
            "specialty": specialty if specialty != "pi" else "project_intelligence",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "student_score": student_score,
            "teacher_score": teacher_score,
            "skip_teacher": skip_teacher,
            "promote": promote,
            "gates": {
                "parity_vs_teacher": ratio_ok,
                "min_absolute": abs_ok,
                "not_stub": not stubbed,
                "parity_ratio_required": self.settings.eval_teacher_parity_ratio,
                "min_student_score": min_abs,
            },
            "cases": {"student": student_rows, "teacher": teacher_rows},
            "note": (
                "Promote only when student beats gates on held-out suite. "
                "Never promote stubs or unverified distillation alone. "
                "Teacher compare skipped when no external keys (student absolute gate still applies)."
            ),
        }
        if persist:
            path = self.root / f"eval-{report['specialty']}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            latest = self.root / f"latest-{report['specialty']}.json"
            latest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            report["path"] = str(path)
        return report

    def latest(self, specialty: str = "project_intelligence") -> dict[str, Any] | None:
        path = self.root / f"latest-{specialty}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))


_harness: EvalHarness | None = None


def get_eval_harness() -> EvalHarness:
    global _harness
    if _harness is None:
        _harness = EvalHarness()
    return _harness
