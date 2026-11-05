"""Learn from everything — successes, failures, mistakes, rejections.

The owned agent becomes genius by absorbing the full outcome spectrum,
not only green-path answers.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from app.config import Settings, get_settings
from app.distillation.engine import DistillationEngine
from app.ownership.handoff import OwnershipHandoff

OutcomeKind = Literal["success", "failure", "error", "rejection", "risk", "lesson"]


class ExperienceJournal:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = Path(self.settings.learning_data_root) / "experience"
        self.root.mkdir(parents=True, exist_ok=True)
        self.engine = DistillationEngine(settings=self.settings)
        self.handoff = OwnershipHandoff(settings=self.settings)

    def _path(self) -> Path:
        return self.root / "journal.jsonl"

    def record(
        self,
        *,
        kind: OutcomeKind,
        title: str,
        detail: str,
        specialty: str = "reasoning",
        project_id: str | None = None,
        meta: dict[str, Any] | None = None,
        distill: bool = True,
    ) -> dict[str, Any]:
        row = {
            "at": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            "title": title[:200],
            "detail": detail[:4000],
            "specialty": specialty,
            "project_id": project_id,
            "meta": meta or {},
        }
        with self._path().open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

        distill_result = None
        if distill and self.settings.learn_from_everything:
            prompt = self._prompt_for(kind, title, detail, meta)
            answer = self._answer_for(kind, title, detail)
            distill_result = self.handoff.distill_pair(
                user_text=prompt,
                assistant_text=answer,
                specialty=specialty,
                source=f"experience_{kind}",
                project_id=project_id,
                human_verified=(kind in {"rejection", "lesson"}),
            )

        return {"recorded": True, "kind": kind, "distill": distill_result}

    def record_success(self, **kwargs: Any) -> dict[str, Any]:
        return self.record(kind="success", **kwargs)

    def record_failure(self, **kwargs: Any) -> dict[str, Any]:
        return self.record(kind="failure", **kwargs)

    def record_error(self, **kwargs: Any) -> dict[str, Any]:
        return self.record(kind="error", **kwargs)

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        path = self._path()
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows

    def stats(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for row in self.recent(limit=5000):
            k = str(row.get("kind") or "unknown")
            counts[k] = counts.get(k, 0) + 1
        return {
            "enabled": self.settings.learn_from_everything,
            "counts": counts,
            "total": sum(counts.values()),
            "path": str(self._path()),
        }

    @staticmethod
    def _prompt_for(
        kind: OutcomeKind, title: str, detail: str, meta: dict[str, Any] | None
    ) -> str:
        if kind == "success":
            return f"Successful outcome to internalize:\nTitle: {title}\nDetail: {detail}"
        if kind in {"failure", "error"}:
            return (
                f"Learn from this {kind}. Explain root cause, what to avoid next time, "
                f"and the corrected approach.\nTitle: {title}\nDetail: {detail}\n"
                f"Meta: {meta or {}}"
            )
        if kind == "rejection":
            return (
                f"Human rejected this proposal. Extract the lesson and adjusted strategy.\n"
                f"Title: {title}\nDetail: {detail}"
            )
        return f"Lesson ({kind}): {title}\n{detail}"

    @staticmethod
    def _answer_for(kind: OutcomeKind, title: str, detail: str) -> str:
        if kind == "success":
            return (
                f"Lesson (success): Retain this working pattern — {title}. "
                f"Evidence: {detail[:1200]}. Reuse when similar project constraints apply. "
                "Never claim merge/deploy without human gate."
            )
        if kind in {"failure", "error"}:
            return (
                f"Lesson ({kind}): Do not repeat — {title}. "
                f"Failure signal: {detail[:1000]}. "
                "Corrective approach: diagnose root cause, add a guard/test, "
                "propose a safer patch in sandbox first, then request human approval. "
                "Failures are training fuel for owned specialists."
            )
        if kind == "rejection":
            return (
                f"Lesson (human rejection): {title}. "
                f"Adjust: {detail[:1000]}. Respect human gates; revise proposal with clearer "
                "risks, blast radius, and acceptance criteria before re-asking."
            )
        return (
            f"Lesson: {title}. Detail: {detail[:1200]}. "
            "Apply only inside the bound project; never mix with other projects."
        )


_journal: ExperienceJournal | None = None


def get_experience_journal() -> ExperienceJournal:
    global _journal
    if _journal is None:
        _journal = ExperienceJournal()
    return _journal


def reset_experience_journal() -> None:
    global _journal
    _journal = None
