"""Adversarial Lab — intentional critique before approval."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Project
from app.gateway.router import ModelRole, get_model_gateway


ROLES = (
    ("security", "Find injection, secrets, auth gaps, unsafe defaults."),
    ("logic", "Find contradictory requirements and broken business rules."),
    ("failure", "Find missing rollback, partial failure, and ops hazards."),
    ("performance", "Find N+1, unbounded scans, and scaling bottlenecks."),
)

# Phrase-level only — single words like "secret" false-positive on normal docs.
CRITICAL_HINTS = (
    "sql injection",
    "api_key=",
    "password=",
    "no rollback",
    "without backup",
    "hardcoded secret",
    "eval(",
    "rm -rf",
)


class AdversarialLab:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session
        self.gateway = get_model_gateway()

    async def critique(
        self,
        project: Project,
        *,
        artifact_title: str,
        artifact_text: str,
        twin_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        # Deterministic scanners first
        lower = (artifact_text or "").lower()
        for hint in CRITICAL_HINTS:
            if hint in lower:
                findings.append(
                    {
                        "role": "security" if "sql" in hint or "secret" in hint else "failure",
                        "severity": "critical",
                        "title": f"Heuristic hit: {hint}",
                        "detail": f"Artifact mentions '{hint}' — treat as blocking until remediated.",
                        "must_fix": True,
                    }
                )

        twin_snip = str((twin_context or {}).get("layers") or "")[:500]
        for role, instruction in ROLES:
            prompt = (
                f"Adversarial role: {role}. {instruction}\n"
                f"Project: {project.name}\n"
                f"Artifact: {artifact_title}\n"
                f"Twin layers: {twin_snip}\n"
                f"Content:\n{artifact_text[:5000]}\n\n"
                "Return JSON list of findings: "
                "[{severity: critical|high|medium|low, title, detail, must_fix: bool}]"
            )
            response = await self.gateway.complete(
                ModelRole.critic,
                prompt,
                system="You are Spixa Adversarial Lab. Prefer false positives over missed criticals.",
                metadata={"agent": f"Adversarial-{role}", "project_id": str(project.id)},
            )
            findings.extend(self._parse_findings(response.content, role))

        critical = [f for f in findings if f.get("severity") == "critical" or f.get("must_fix")]
        high = [f for f in findings if f.get("severity") == "high"]
        resilience = max(0.0, 1.0 - 0.25 * len(critical) - 0.1 * len(high))
        return {
            "artifact_title": artifact_title,
            "findings": findings[:40],
            "critical_count": len(critical),
            "high_count": len(high),
            "resilience_score": round(resilience, 3),
            "blocking": bool(critical),
            "recommendation": "block_approval" if critical else "proceed_with_fixes" if high else "acceptable",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _parse_findings(self, content: str, role: str) -> list[dict[str, Any]]:
        import json

        text = (content or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            start = text.find("[")
            end = text.rfind("]")
            raw = text[start : end + 1] if start >= 0 and end > start else text
            data = json.loads(raw)
            if isinstance(data, list):
                out = []
                for item in data[:8]:
                    if not isinstance(item, dict):
                        continue
                    out.append(
                        {
                            "role": role,
                            "severity": str(item.get("severity") or "medium").lower(),
                            "title": str(item.get("title") or "finding")[:200],
                            "detail": str(item.get("detail") or "")[:800],
                            "must_fix": bool(item.get("must_fix")),
                        }
                    )
                return out
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        # Fallback single finding from prose
        if len(text) > 40:
            sev = "high" if any(h in text.lower() for h in CRITICAL_HINTS) else "medium"
            return [
                {
                    "role": role,
                    "severity": sev,
                    "title": f"{role} critique",
                    "detail": text[:800],
                    "must_fix": sev in {"critical", "high"},
                }
            ]
        return []
