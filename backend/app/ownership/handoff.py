"""Fast Ownership Handoff — learn rapidly, then retire external teachers.

Doctrine (user intent):
- Owned students learn at extreme speed from teachers + verified outcomes + LTM.
- When a specialty can execute reliably, hand off: prefer internal, stop escalating.
- Per-project memory fuels standing instructions and project-bound examples.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.distillation.engine import DistillationEngine
from app.gateway.intelligent_router import get_intelligent_router
from app.gateway.internal import family_catalog
from app.memory import ProjectLongTermMemory
from app.training.lora import get_lora_trainer

SPECIALTIES = (
    "coding",
    "reasoning",
    "critic",
    "project_intelligence",
    "vision",
    "embeddings",
)

INTENT_TO_SPECIALTY = {
    "implement": "coding",
    "design": "vision",
    "quality": "critic",
    "security": "critic",
    "ops": "reasoning",
    "analyze": "project_intelligence",
    "plan": "reasoning",
    "explain": "reasoning",
    "retrieve": "embeddings",
    "search": "embeddings",
    "embed": "embeddings",
}

CODE_HINT = re.compile(
    r"\b(code|implement|function|api|endpoint|bug|fix|refactor|أضف|صلح|برمج|endpoint)\b",
    re.I,
)
REASON_HINT = re.compile(
    r"\b(plan|why|decide|architect|strategy|خطة|لماذا|قرر|تصميم معماري)\b",
    re.I,
)


INTERNAL_BY_SPECIALTY = {
    "coding": "internal/coding",
    "reasoning": "internal/reasoning",
    "critic": "internal/critic",
    "project_intelligence": "internal/project-intelligence",
    "vision": "internal/vision",
    "embeddings": "internal/embeddings",
}


class OwnershipHandoff:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = Path(self.settings.learning_data_root) / "handoff"
        self.root.mkdir(parents=True, exist_ok=True)
        self.engine = DistillationEngine(settings=self.settings)

    def _min_examples(self) -> int:
        return max(3, int(self.settings.lora_min_examples))

    def _retired_path(self) -> Path:
        return self.root / "retired_teachers.json"

    def list_retired(self) -> dict[str, Any]:
        path = self._retired_path()
        if not path.exists():
            return {"specialties": [], "updated_at": None}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"specialties": [], "updated_at": None}
        specs = [s for s in (data.get("specialties") or []) if s in SPECIALTIES]
        return {
            "specialties": specs,
            "updated_at": data.get("updated_at"),
            "reasons": data.get("reasons") or {},
        }

    def is_specialty_retired(self, specialty_or_model_id: str) -> bool:
        token = str(specialty_or_model_id or "")
        retired = set(self.list_retired().get("specialties") or [])
        if token in retired:
            return True
        for name, iid in INTERNAL_BY_SPECIALTY.items():
            if name in retired and (token == iid or token.endswith(name) or name in token):
                return True
        return False

    def retire_specialty(self, specialty: str, *, reason: str = "manual") -> dict[str, Any]:
        name = str(specialty or "").strip()
        if name not in SPECIALTIES:
            return {"ok": False, "error": "unknown_specialty", "specialty": name}
        data = self.list_retired()
        specs = list(data.get("specialties") or [])
        reasons = dict(data.get("reasons") or {})
        if name not in specs:
            specs.append(name)
        reasons[name] = {
            "reason": reason,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        payload = {
            "specialties": specs,
            "reasons": reasons,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._retired_path().write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._append_journal(
            {
                "event": "retire_teacher",
                "specialty": name,
                "reason": reason,
                "at": payload["updated_at"],
            }
        )
        return {"ok": True, "specialty": name, "retired": specs, "reason": reason}

    def restore_specialty(self, specialty: str, *, reason: str = "manual_restore") -> dict[str, Any]:
        name = str(specialty or "").strip()
        if name not in SPECIALTIES:
            return {"ok": False, "error": "unknown_specialty", "specialty": name}
        data = self.list_retired()
        specs = [s for s in (data.get("specialties") or []) if s != name]
        reasons = dict(data.get("reasons") or {})
        reasons.pop(name, None)
        payload = {
            "specialties": specs,
            "reasons": reasons,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._retired_path().write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._append_journal(
            {
                "event": "restore_teacher",
                "specialty": name,
                "reason": reason,
                "at": payload["updated_at"],
            }
        )
        return {"ok": True, "specialty": name, "retired": specs, "reason": reason}

    def retire_all_ready(self, *, reason: str = "auto_ready") -> dict[str, Any]:
        """Retire teachers for every handoff_ready specialty."""
        # Avoid recursion: compute readiness without auto-sync
        ready_names = [
            row["specialty"]
            for row in self._readiness_rows()
            if row.get("handoff_ready")
        ]
        results = [self.retire_specialty(n, reason=reason) for n in ready_names]
        return {
            "ok": True,
            "retired_now": ready_names,
            "results": results,
            "retired": self.list_retired().get("specialties") or [],
        }

    def sync_auto_retire(self) -> dict[str, Any] | None:
        if not getattr(self.settings, "auto_retire_ready_teachers", True):
            return None
        rows = self._readiness_rows()
        ready = [r["specialty"] for r in rows if r.get("handoff_ready")]
        not_ready = {r["specialty"] for r in rows if not r.get("handoff_ready")}
        already = set(self.list_retired().get("specialties") or [])
        # Safety: never keep teachers retired for specialties that are not actually handoff_ready.
        # (Prevents coding bootstrap lockout after a stale auto_ready retire.)
        wrongly_retired = [n for n in already if n in not_ready]
        for name in wrongly_retired:
            self.restore_specialty(name, reason="auto_restore_not_handoff_ready")
        already = set(self.list_retired().get("specialties") or [])
        missing = [n for n in ready if n not in already]
        if not missing and not wrongly_retired:
            return None
        for name in missing:
            self.retire_specialty(name, reason="auto_ready")
        return {
            "auto_retired": missing,
            "auto_restored": wrongly_retired,
        }

    def _readiness_rows(self) -> list[dict[str, Any]]:
        catalog = {row["id"]: row for row in family_catalog(self.settings)}
        adapters = {a.get("adapter"): a for a in get_lora_trainer().list_adapters()}
        distill = self.engine.stats().get("examples_by_specialty") or {}
        rows: list[dict[str, Any]] = []
        for name in SPECIALTIES:
            internal_id = INTERNAL_BY_SPECIALTY[name]
            fam = catalog.get(internal_id) or {}
            adapter_name = fam.get("adapter")
            adapter = adapters.get(adapter_name) or {}
            examples = int(distill.get(name) or 0)
            promoted = bool(fam.get("adapter_promoted") or adapter.get("ready") or fam.get("ready"))
            enough_data = examples >= self._min_examples()
            handoff_ready = promoted and enough_data
            rows.append(
                {
                    "specialty": name,
                    "internal_id": internal_id,
                    "promoted": promoted,
                    "examples": examples,
                    "min_examples": self._min_examples(),
                    "enough_data": enough_data,
                    "handoff_ready": handoff_ready,
                    "host": fam.get("host"),
                }
            )
        return rows

    def readiness_map(self) -> dict[str, Any]:
        """Score each specialty for teacher retirement readiness."""
        self.sync_auto_retire()
        router = get_intelligent_router().status()
        metrics = router.get("metrics") or {}
        coverage = float(metrics.get("internal_coverage_ratio") or 0.0)
        target = float(metrics.get("target_internal_coverage") or 0.85)
        retired = set(self.list_retired().get("specialties") or [])
        reasons = self.list_retired().get("reasons") or {}

        specialties: list[dict[str, Any]] = []
        ready_count = 0
        retired_count = 0
        for row in self._readiness_rows():
            name = row["specialty"]
            handoff_ready = bool(row.get("handoff_ready"))
            is_retired = name in retired
            if handoff_ready:
                ready_count += 1
            if is_retired:
                retired_count += 1
            if is_retired:
                policy = "retired"
            elif handoff_ready:
                policy = "escalate_only"
            else:
                policy = "bootstrap_allowed"
            specialties.append(
                {
                    **row,
                    "teachers_retired": is_retired,
                    "retire_reason": (reasons.get(name) or {}).get("reason"),
                    "teacher_policy": policy,
                }
            )

        ratio = ready_count / len(SPECIALTIES) if SPECIALTIES else 0.0
        if retired_count >= ready_count and ready_count >= 3:
            next_action = "maintain_owned_coverage"
        elif ready_count >= 3:
            next_action = "retire_teachers_for_ready_specialties"
        else:
            next_action = "grow_datasets_and_promote"
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "doctrine": "Teacher → Student → Self-Owned — hand off when specialty is promoted + fueled",
            "internal_coverage_ratio": coverage,
            "target_internal_coverage": target,
            "coverage_on_track": coverage >= target * 0.6 or ready_count >= 3,
            "specialties_ready": ready_count,
            "specialties_total": len(SPECIALTIES),
            "specialties_retired": retired_count,
            "specialty_ready_ratio": round(ratio, 4),
            "prefer_promoted_internal": self.settings.prefer_promoted_internal,
            "promoted_no_escalate": self.settings.promoted_no_escalate,
            "fast_handoff_enabled": self.settings.fast_handoff_enabled,
            "auto_retire_ready_teachers": bool(
                getattr(self.settings, "auto_retire_ready_teachers", True)
            ),
            "specialties": specialties,
            "next_action": next_action,
        }

    def coverage_meter(self) -> dict[str, Any]:
        """Progress toward self-owned ecosystem (~85% successful internal tasks)."""
        ready = self.readiness_map()
        coverage = float(ready.get("internal_coverage_ratio") or 0.0)
        target = float(ready.get("target_internal_coverage") or 0.85)
        specialty_ratio = float(ready.get("specialty_ready_ratio") or 0.0)
        # Blend live router coverage with specialty readiness (fuel for future coverage)
        blended = round(min(1.0, coverage * 0.65 + specialty_ratio * 0.35), 4)
        gap = max(0.0, round(target - coverage, 4))
        return {
            "generated_at": ready.get("generated_at"),
            "internal_coverage_ratio": coverage,
            "specialty_ready_ratio": specialty_ratio,
            "blended_progress": blended,
            "target_internal_coverage": target,
            "gap_to_target": gap,
            "percent_internal": round(coverage * 100, 1),
            "percent_blended": round(blended * 100, 1),
            "percent_target": round(target * 100, 1),
            "on_track": bool(ready.get("coverage_on_track")),
            "specialties_ready": ready.get("specialties_ready"),
            "specialties_total": ready.get("specialties_total"),
            "next_action": ready.get("next_action"),
            "cost_per_successful_task_usd": float(
                (get_intelligent_router().status().get("metrics") or {}).get(
                    "cost_per_successful_task_usd"
                )
                or 0.0
            ),
            "estimated_cost_usd": float(
                (get_intelligent_router().status().get("metrics") or {}).get("estimated_cost_usd")
                or 0.0
            ),
            "label_ar": (
                f"تغطية داخلية {round(coverage * 100)}% من هدف {round(target * 100)}% · "
                f"تخصصات جاهزة {ready.get('specialties_ready')}/{ready.get('specialties_total')}"
            ),
        }

    def _infer_specialty(self, text: str, intent: str | None = None) -> str:
        if intent and intent in INTENT_TO_SPECIALTY:
            return INTENT_TO_SPECIALTY[intent]
        if CODE_HINT.search(text or ""):
            return "coding"
        if REASON_HINT.search(text or ""):
            return "reasoning"
        return "reasoning"

    def distill_pair(
        self,
        *,
        user_text: str,
        assistant_text: str,
        intent: str | None = None,
        specialty: str | None = None,
        source: str = "chat_outcome",
        project_id: str | None = None,
        human_verified: bool = False,
    ) -> dict[str, Any]:
        """Rapidly turn a successful dialogue into student training fuel."""
        if not self.settings.fast_handoff_enabled:
            return {"accepted": False, "reason": "fast_handoff_disabled"}
        user_text = (user_text or "").strip()
        assistant_text = (assistant_text or "").strip()
        if len(user_text) < 4 or len(assistant_text) < 16:
            return {"accepted": False, "reason": "too_short"}
        if assistant_text.startswith("[provider-error") or "[internal-student:" in assistant_text:
            return {"accepted": False, "reason": "stub_or_error"}

        specialty = specialty or self._infer_specialty(user_text, intent)
        meta: dict[str, Any] = {
            "specialty": specialty,
            "distill": True,
            "selective_distill": True,
            "source": source,
            "project_id": project_id,
            "tools_ok": True,  # operational completion under Master/Chief gate
            "fast_handoff": True,
        }
        if human_verified:
            meta["human_verified"] = True

        result = self.engine.ingest_teacher_output(
            role=specialty if specialty != "vision" else "multimodal",
            prompt=user_text,
            system=(
                "You are an Evolve owned specialist. Obey project-isolated memory. "
                "Never claim merges/deploys without human gate."
            ),
            teacher_model=f"evolve/{source}",
            teacher_output=assistant_text,
            metadata=meta,
        )
        self._append_journal(
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "event": "distill_pair",
                "specialty": specialty,
                "accepted": bool(result.get("accepted")),
                "source": source,
                "project_id": project_id,
            }
        )
        return result

    async def distill_project_memory(
        self,
        session: AsyncSession,
        project_id: UUID,
        *,
        limit: int = 40,
    ) -> dict[str, Any]:
        """Convert standing instructions + recent transcript pairs into training examples."""
        ltm = ProjectLongTermMemory(session)
        recall = await ltm.recall(project_id, transcript_limit=limit)
        accepted = 0
        rows: list[dict[str, Any]] = []

        for inst in recall.get("standing_instructions") or []:
            content = (inst.get("content") or "").strip()
            if not content:
                continue
            out = self.distill_pair(
                user_text=content,
                assistant_text=(
                    "Acknowledged as standing instruction for THIS project only. "
                    f"I will retain and execute: {content}"
                ),
                specialty="reasoning",
                source="standing_instruction",
                project_id=str(project_id),
                human_verified=True,
            )
            rows.append(out)
            if out.get("accepted"):
                accepted += 1

        transcript = recall.get("transcript") or []
        # Pair consecutive user→assistant turns
        i = 0
        while i < len(transcript) - 1:
            a, b = transcript[i], transcript[i + 1]
            if a.get("role") == "user" and b.get("role") == "assistant":
                out = self.distill_pair(
                    user_text=str(a.get("content") or ""),
                    assistant_text=str(b.get("content") or ""),
                    source="ltm_transcript",
                    project_id=str(project_id),
                )
                rows.append(out)
                if out.get("accepted"):
                    accepted += 1
                i += 2
            else:
                i += 1

        report = {
            "project_id": str(project_id),
            "binding": recall.get("binding"),
            "pairs_considered": len(rows),
            "accepted": accepted,
            "readiness": self.readiness_map(),
        }
        self._append_journal({"at": datetime.now(timezone.utc).isoformat(), "event": "distill_project", **report})
        return report

    def absorb_chat_turn(
        self,
        *,
        user_message: str,
        reply: str,
        intent: str | None = None,
        project_id: str | None = None,
        simulated: bool = False,
        human_verified: bool = False,
        specialty: str | None = None,
        source: str = "chat_outcome",
    ) -> dict[str, Any]:
        if simulated:
            return {"accepted": False, "reason": "simulated"}
        return self.distill_pair(
            user_text=user_message,
            assistant_text=reply,
            intent=intent,
            specialty=specialty,
            source=source,
            project_id=project_id,
            human_verified=human_verified,
        )

    def rapid_learn_ide_turn(
        self,
        *,
        user_text: str,
        assistant_text: str,
        project_id: str | None = None,
        files: list[str] | None = None,
        intent: str | None = "implement",
    ) -> dict[str, Any]:
        """Aggressive Cursor-like learning after the human applies IDE edits."""
        files = [f for f in (files or []) if f][:40]
        enriched_reply = (assistant_text or "").strip()
        if files:
            enriched_reply = (
                f"{enriched_reply}\n\nApplied workspace files:\n"
                + "\n".join(f"- {p}" for p in files)
            )
        distill = self.distill_pair(
            user_text=user_text,
            assistant_text=enriched_reply[:6000],
            intent=intent or "implement",
            specialty="coding",
            source="ide_human_apply",
            project_id=project_id,
            human_verified=True,
        )
        # Second pass: short coding pattern for retrieval
        pattern = self.distill_pair(
            user_text=f"IDE task: {(user_text or '')[:500]}",
            assistant_text=(
                "Deliver applyable file edits for the ask. Prefer small correct diffs. "
                f"Touched: {', '.join(files) if files else 'workspace files'}."
            ),
            specialty="coding",
            source="ide_pattern",
            project_id=project_id,
            human_verified=True,
        )
        return {"distill": distill, "pattern": pattern, "files": files}

    def status(self) -> dict[str, Any]:
        readiness = self.readiness_map()
        journal = self._read_journal(limit=30)
        path = self.root / "latest-readiness.json"
        path.write_text(json.dumps(readiness, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "readiness": readiness,
            "recent_events": journal,
            "latest_path": str(path),
        }

    def _append_journal(self, row: dict[str, Any]) -> None:
        path = self.root / "journal.jsonl"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    def _read_journal(self, limit: int = 30) -> list[dict[str, Any]]:
        path = self.root / "journal.jsonl"
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        out: list[dict[str, Any]] = []
        for line in lines[-limit:]:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out


_handoff: OwnershipHandoff | None = None


def get_ownership_handoff() -> OwnershipHandoff:
    global _handoff
    if _handoff is None:
        _handoff = OwnershipHandoff()
    return _handoff


def reset_ownership_handoff() -> None:
    global _handoff
    _handoff = None
