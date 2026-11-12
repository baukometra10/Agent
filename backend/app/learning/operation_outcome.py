"""Learn from every agent operation — ASAP, in-process, no waiting for batch jobs.

Every chat success/failure, IDE accept/reject, preview start, and abort feeds:
1) Experience journal
2) Ownership distillation (student fuel)
3) Optional micro LoRA kick when enough verified coding examples land
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any, Literal

from app.config import get_settings
from app.learning.experience import OutcomeKind, get_experience_journal
from app.ownership.handoff import get_ownership_handoff

OpKind = Literal[
    "chat_success",
    "chat_error",
    "chat_abort",
    "edits_accepted",
    "edits_rejected",
    "edits_failed",
    "preview_ok",
    "preview_fail",
    "build_ok",
    "build_fail",
]

_LOCK = threading.Lock()
_COUNTS: dict[str, int] = {}
_LAST_MEMORY: dict[str, float] = {}
_TRAIN_BUSY = False


def _specialty_for(kind: OpKind, intent: str | None) -> str:
    if kind.startswith("preview") or kind.startswith("build") or kind.startswith("edits"):
        return "coding"
    if (intent or "").lower() == "implement":
        return "coding"
    return "reasoning"


def _journal_kind(kind: OpKind) -> OutcomeKind:
    if kind in {"chat_success", "edits_accepted", "preview_ok", "build_ok"}:
        return "success"
    if kind in {"edits_rejected"}:
        return "rejection"
    if kind in {"chat_abort"}:
        return "lesson"
    return "error"


def learn_from_operation(
    *,
    kind: OpKind,
    title: str,
    detail: str,
    project_id: str | None = None,
    user_text: str = "",
    assistant_text: str = "",
    files: list[str] | None = None,
    intent: str | None = None,
    human_verified: bool = False,
    distill_pair: bool = True,
) -> dict[str, Any]:
    """Record + distill one operational outcome immediately."""
    settings = get_settings()
    specialty = _specialty_for(kind, intent)
    files = [f for f in (files or []) if f][:40]
    detail_full = detail
    if files:
        detail_full = f"{detail}\nFiles: {', '.join(files)}"

    journal = get_experience_journal().record(
        kind=_journal_kind(kind),
        title=title,
        detail=detail_full[:4000],
        specialty=specialty,
        project_id=project_id,
        meta={"op": kind, "files": files, "intent": intent},
        # Hub does the real pair distill — avoid double synthetic fuel when we have a pair
        distill=not (distill_pair and user_text and assistant_text),
    )

    distill_result = None
    handoff = get_ownership_handoff()
    if distill_pair and settings.learn_from_everything and settings.fast_handoff_enabled:
        u = (user_text or title).strip()
        a = (assistant_text or detail_full).strip()
        if kind in {"edits_rejected", "chat_error", "edits_failed", "preview_fail", "build_fail"}:
            a = (
                f"Outcome={kind}. Avoid repeating this failure.\n"
                f"Context: {detail_full[:1500]}\n"
                f"Corrective approach: re-read the workspace, fix the root cause, "
                f"then emit a smaller verified change."
            )
            human_verified = True
        if kind == "edits_accepted" and files:
            a = f"{a}\n\nApplied workspace files:\n" + "\n".join(f"- {p}" for p in files)
            human_verified = True
        distill_result = handoff.distill_pair(
            user_text=u[:4000] or title,
            assistant_text=a[:6000],
            intent=intent,
            specialty=specialty,
            source=f"op_{kind}",
            project_id=project_id,
            human_verified=human_verified or kind in {"edits_accepted", "preview_ok", "build_ok"},
        )

    with _LOCK:
        _COUNTS[specialty] = int(_COUNTS.get(specialty, 0)) + 1
        count = _COUNTS[specialty]

    micro = None
    if human_verified or kind in {"edits_accepted", "preview_ok", "build_ok"}:
        micro = maybe_kick_micro_train(specialty, count)

    return {
        "ok": True,
        "kind": kind,
        "specialty": specialty,
        "journal": journal,
        "distill": distill_result,
        "micro_train": micro,
        "ops_count": count,
    }


def maybe_kick_micro_train(specialty: str, count: int) -> dict[str, Any] | None:
    """Every N verified ops, kick a tiny background LoRA train (non-blocking)."""
    global _TRAIN_BUSY
    settings = get_settings()
    every = max(4, int(getattr(settings, "lora_min_examples", 8) or 8) // 2)
    if count % every != 0:
        return {"scheduled": False, "reason": "wait", "every": every, "count": count}
    if not bool(getattr(settings, "lora_real_train_enabled", False)):
        return {"scheduled": False, "reason": "lora_disabled"}
    with _LOCK:
        if _TRAIN_BUSY:
            return {"scheduled": False, "reason": "busy"}
        _TRAIN_BUSY = True

    def _run() -> None:
        global _TRAIN_BUSY
        try:
            from app.training.lora import get_lora_trainer

            trainer = get_lora_trainer()
            asyncio.run(
                trainer.train_specialty(specialty, run_eval=False, force_placeholder=False)
            )
            try:
                get_ownership_handoff().sync_auto_retire()
            except Exception:  # noqa: BLE001
                pass
        except Exception:  # noqa: BLE001
            pass
        finally:
            with _LOCK:
                _TRAIN_BUSY = False

    threading.Thread(target=_run, name=f"spixa-micro-lora-{specialty}", daemon=True).start()
    return {"scheduled": True, "specialty": specialty, "count": count}


def should_distill_project_memory(project_id: str, *, min_interval_sec: float = 45.0) -> bool:
    """Debounce heavy LTM→student sweeps so every apply stays fast."""
    now = time.time()
    with _LOCK:
        last = float(_LAST_MEMORY.get(project_id) or 0)
        if now - last < min_interval_sec:
            return False
        _LAST_MEMORY[project_id] = now
        return True


def learning_pulse() -> dict[str, Any]:
    settings = get_settings()
    return {
        "learn_from_everything": bool(settings.learn_from_everything),
        "fast_handoff_enabled": bool(settings.fast_handoff_enabled),
        "distillation_enabled": bool(getattr(settings, "distillation_enabled", True)),
        "ops_by_specialty": dict(_COUNTS),
        "doctrine": "Every operation trains Spixa — success, failure, reject, preview, abort.",
        "doctrine_ar": "كل عملية تُعلّم سبيسا — نجاح، فشل، رفض، معاينة، إلغاء.",
    }
