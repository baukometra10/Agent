"""Promotion gates — eval pass ≠ production ship."""

from __future__ import annotations

from typing import Any


def eval_passes_gates(report: dict[str, Any] | None) -> tuple[bool, list[str]]:
    if not report:
        return False, ["missing_eval_report"]
    reasons: list[str] = []
    gates = report.get("gates") or {}
    if not report.get("promote"):
        reasons.append("eval_promote_false")
    if not gates.get("parity_vs_teacher", True):
        reasons.append("parity_vs_teacher")
    if not gates.get("min_absolute", True):
        reasons.append("min_absolute")
    if gates.get("not_stub") is False:
        reasons.append("stubbed_student")
    return (len(reasons) == 0 and bool(report.get("promote"))), reasons


def regression_vs_baseline(
    report: dict[str, Any] | None,
    baseline_student_score: float | None,
    *,
    tolerance: float = 0.02,
) -> tuple[bool, list[str]]:
    """Block if new candidate is worse than last factory-approved release."""
    if baseline_student_score is None:
        return True, []
    student = float((report or {}).get("student_score") or 0)
    if student + float(tolerance) < float(baseline_student_score):
        return False, [
            f"regression:{student}<{baseline_student_score}(tol={tolerance})"
        ]
    return True, []


def better_than_teacher(
    report: dict[str, Any] | None,
    *,
    baseline_student_score: float | None = None,
    regression_tolerance: float = 0.02,
) -> dict[str, Any]:
    """Declare specialty handoff readiness (still needs human approve)."""
    ok, reasons = eval_passes_gates(report)
    reg_ok, reg_reasons = regression_vs_baseline(
        report, baseline_student_score, tolerance=regression_tolerance
    )
    if not reg_ok:
        ok = False
        reasons = [*reasons, *reg_reasons]
    student = float((report or {}).get("student_score") or 0)
    teacher = float((report or {}).get("teacher_score") or 0)
    beat = ok and (teacher <= 0 or student >= teacher)
    return {
        "gates_ok": ok,
        "beat_or_parity": beat,
        "student_score": student,
        "teacher_score": teacher,
        "baseline_student_score": baseline_student_score,
        "regression_ok": reg_ok,
        "blockers": reasons,
        "needs_human_approval": True,
        "note_ar": (
            "اجتياز البوابات ينشئ اقتراح إصدار فقط — "
            "الترقية للإنتاج تتطلب موافقة بشرية صريحة."
        ),
    }
