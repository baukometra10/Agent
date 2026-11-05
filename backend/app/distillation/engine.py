"""AI Knowledge Transfer & Distillation Engine (foundation).

External teacher outputs become training candidates ONLY after verification.
This does not copy teacher weights — it captures behavioral examples for SFT/LoRA.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings


SPECIALTY_TAGS = (
    "reasoning",
    "coding",
    "project_intelligence",
    "vision",
    "critic",
    "embeddings",
    "general",
)


@dataclass
class DistillCandidate:
    id: str
    specialty: str
    role: str
    prompt: str
    system: str | None
    teacher_model: str
    teacher_output: str
    verified: bool
    verification: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    promoted: bool = False

    def to_jsonl(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "specialty": self.specialty,
            "role": self.role,
            "messages": (
                ([{"role": "system", "content": self.system}] if self.system else [])
                + [
                    {"role": "user", "content": self.prompt},
                    {"role": "assistant", "content": self.teacher_output},
                ]
            ),
            "teacher_model": self.teacher_model,
            "verified": self.verified,
            "verification": self.verification,
            "created_at": self.created_at,
        }


class DistillationEngine:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = Path(self.settings.distillation_data_root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._accepted = 0
        self._rejected = 0
        self._queued_unverified = 0

    def _specialty_path(self, specialty: str) -> Path:
        safe = specialty if specialty in SPECIALTY_TAGS else "general"
        path = self.root / safe
        path.mkdir(parents=True, exist_ok=True)
        return path / "train.jsonl"

    def classify_specialty(self, role: str, metadata: dict[str, Any] | None = None) -> str:
        meta = metadata or {}
        if meta.get("specialty") in SPECIALTY_TAGS:
            return str(meta["specialty"])
        mapping = {
            "reasoning": "reasoning",
            "coding": "coding",
            "fast": "coding",
            "multimodal": "vision",
            "embedding": "embeddings",
            "critic": "critic",
            "project_intelligence": "project_intelligence",
        }
        return mapping.get(role, "general")

    def verify(
        self,
        *,
        output: str,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        """Independent verification signals — tools/tests/heuristics, not teacher self-score."""
        meta = metadata or {}
        checks: dict[str, Any] = {}
        if "tests_ok" in meta:
            checks["tests_ok"] = bool(meta["tests_ok"])
        if "tools_ok" in meta:
            checks["tools_ok"] = bool(meta["tools_ok"])
        if meta.get("human_verified") is True:
            checks["human_verified"] = True
        if meta.get("critic_approved") is True:
            checks["critic_approved"] = True

        # Heuristic gates: reject empty / error / pure stubs
        text = (output or "").strip()
        checks["non_empty"] = len(text) >= 16
        checks["not_error"] = not text.startswith("[provider-error")
        checks["not_stub"] = "[internal-student:" not in text and "[simulated:" not in text

        required = []
        if "tests_ok" in checks:
            required.append(checks["tests_ok"])
        if "tools_ok" in checks:
            required.append(checks["tools_ok"])
        if "human_verified" in checks:
            required.append(True)
        if "critic_approved" in checks:
            required.append(True)

        structural = checks["non_empty"] and checks["not_error"] and checks["not_stub"]
        if required:
            ok = structural and all(required)
        else:
            # Without explicit tool/test evidence, only queue as unverified candidate
            ok = False
            checks["needs_explicit_verification"] = True
        return ok, checks

    def ingest_teacher_output(
        self,
        *,
        role: str,
        prompt: str,
        system: str | None,
        teacher_model: str,
        teacher_output: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.settings.distillation_enabled:
            return {"accepted": False, "reason": "distillation_disabled"}

        meta = metadata or {}
        specialty = self.classify_specialty(role, meta)
        verified, verification = self.verify(output=teacher_output, metadata=meta)
        candidate = DistillCandidate(
            id=str(uuid.uuid4()),
            specialty=specialty,
            role=role,
            prompt=prompt,
            system=system,
            teacher_model=teacher_model,
            teacher_output=teacher_output,
            verified=verified,
            verification=verification,
            created_at=datetime.now(timezone.utc).isoformat(),
            promoted=verified,
        )

        if not verified:
            # Keep side channel for later human/tool verification
            pending = self.root / "_pending" / f"{candidate.id}.json"
            pending.parent.mkdir(parents=True, exist_ok=True)
            pending.write_text(json.dumps(asdict(candidate), ensure_ascii=False, indent=2), encoding="utf-8")
            self._queued_unverified += 1
            self._rejected += 1
            return {
                "accepted": False,
                "queued_pending": True,
                "id": candidate.id,
                "specialty": specialty,
                "verification": verification,
            }

        path = self._specialty_path(specialty)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(candidate.to_jsonl(), ensure_ascii=False) + "\n")
        self._accepted += 1
        return {
            "accepted": True,
            "id": candidate.id,
            "specialty": specialty,
            "path": str(path),
            "verification": verification,
        }

    def stats(self) -> dict[str, Any]:
        by_specialty: dict[str, int] = {}
        for tag in SPECIALTY_TAGS:
            path = self.root / tag / "train.jsonl"
            if path.exists():
                by_specialty[tag] = sum(1 for _ in path.open(encoding="utf-8") if _.strip())
            else:
                by_specialty[tag] = 0
        pending_dir = self.root / "_pending"
        pending = len(list(pending_dir.glob("*.json"))) if pending_dir.exists() else 0
        return {
            "enabled": self.settings.distillation_enabled,
            "data_root": str(self.root),
            "accepted_session": self._accepted,
            "rejected_or_pending_session": self._rejected,
            "queued_unverified_session": self._queued_unverified,
            "examples_by_specialty": by_specialty,
            "pending_files": pending,
            "techniques_planned": [
                "SFT",
                "LoRA",
                "QLoRA",
                "Knowledge Distillation",
                "DPO",
                "Quantization",
                "Synthetic Data",
                "Continual Evaluation",
            ],
        }


_engine: DistillationEngine | None = None


def get_distillation_engine() -> DistillationEngine:
    global _engine
    if _engine is None:
        _engine = DistillationEngine()
    return _engine


def reset_distillation_engine() -> None:
    global _engine
    _engine = None
