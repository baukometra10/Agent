"""Phase 6 — Strategic Planning Engine.

Turns Analysis findings into a prioritized, autonomous roadmap.
Independence rule: the agent may plan and draft freely; execution stays gated.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SEVERITY_SCORE = {
    "critical": 100,
    "high": 80,
    "medium": 55,
    "low": 30,
    "info": 15,
}

KIND_BONUS = {
    "problem": 10,
    "risk": 8,
    "opportunity": 4,
}

COMPLEXITY_BY_CATEGORY = {
    "security": "high",
    "architecture": "high",
    "performance": "medium",
    "integration": "medium",
    "quality": "medium",
    "maintainability": "low",
    "ux": "medium",
    "feature": "medium",
}


@dataclass
class PlanItemDraft:
    title: str
    description: str
    rationale: str
    goal: str
    category: str
    priority: int
    complexity: str
    impact_score: float
    risk_score: float
    affected_parts: list[Any] = field(default_factory=list)
    dependencies: list[Any] = field(default_factory=list)
    risks: str = ""
    acceptance_criteria: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    finding_fingerprint: str | None = None
    sort_order: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PlanningReport:
    title: str
    vision: str
    items: list[PlanItemDraft] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    knowledge: list[dict[str, Any]] = field(default_factory=list)
    autonomous: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "vision": self.vision,
            "items": [i.to_dict() for i in self.items],
            "summary": self.summary,
            "knowledge": self.knowledge,
            "autonomous": self.autonomous,
        }


def _score_finding(finding: dict[str, Any]) -> tuple[int, float, float]:
    severity = finding.get("severity", "medium")
    kind = finding.get("kind", "opportunity")
    confidence = float(finding.get("confidence") or 0.5)
    base = SEVERITY_SCORE.get(severity, 40) + KIND_BONUS.get(kind, 0)
    priority = int(base * (0.6 + 0.4 * confidence))
    impact = min(1.0, (SEVERITY_SCORE.get(severity, 40) / 100) * (0.5 + confidence / 2))
    risk = 0.7 if kind == "risk" else (0.55 if severity in {"critical", "high"} else 0.35)
    return priority, impact, risk


def _acceptance(finding: dict[str, Any]) -> str:
    return (
        f"1) Evidence for '{finding.get('title')}' is addressed or invalidated.\n"
        f"2) Recommendation applied or consciously deferred with rationale.\n"
        f"3) Regression checks for affected parts pass: "
        f"{', '.join(map(str, (finding.get('affected_parts') or ['n/a'])[:5]))}."
    )


def run_planning_engine(
    *,
    project_name: str,
    findings: list[dict[str, Any]],
    intelligence: dict[str, Any] | None = None,
    autonomous: bool = True,
) -> PlanningReport:
    intelligence = intelligence or {}
    purpose = (intelligence.get("business") or {}).get("purpose")
    vision = purpose or (
        f"Evolve {project_name} continuously: reduce risk, improve architecture, "
        "and unlock evidenced product opportunities — with human gates on execution."
    )

    drafts: list[PlanItemDraft] = []
    for finding in findings:
        priority, impact, risk = _score_finding(finding)
        category = finding.get("category") or "quality"
        drafts.append(
            PlanItemDraft(
                title=finding.get("title") or "Untitled initiative",
                description=finding.get("description") or "",
                rationale=(
                    f"Why now: {finding.get('kind')} / {finding.get('severity')} "
                    f"(confidence={finding.get('confidence')}). "
                    f"Source: {finding.get('source_agent', 'AnalysisEngine')}."
                ),
                goal=finding.get("recommendation") or "Resolve the finding with measurable acceptance.",
                category=category,
                priority=priority,
                complexity=COMPLEXITY_BY_CATEGORY.get(category, "medium"),
                impact_score=impact,
                risk_score=risk,
                affected_parts=finding.get("affected_parts") or [],
                dependencies=[],
                risks=f"Residual risk if deferred: {finding.get('severity')} {finding.get('kind')}.",
                acceptance_criteria=_acceptance(finding),
                evidence=finding.get("evidence") or {},
                finding_fingerprint=finding.get("fingerprint"),
            )
        )

    drafts.sort(key=lambda d: (-d.priority, d.category, d.title))
    for idx, item in enumerate(drafts):
        item.sort_order = idx
        # Light dependency chaining: high architecture before feature work
        if item.category == "feature":
            arch_deps = [
                d.title
                for d in drafts
                if d.category in {"architecture", "security"} and d.priority >= 70
            ][:3]
            item.dependencies = arch_deps

    by_category: dict[str, int] = {}
    for item in drafts:
        by_category[item.category] = by_category.get(item.category, 0) + 1

    knowledge = [
        {
            "memory_layer": "decision",
            "category": "roadmap",
            "kind": "inference",
            "title": f"Autonomous roadmap generated ({len(drafts)} items)",
            "content": vision,
            "confidence": 0.65 if drafts else 0.4,
            "source_type": "agent",
            "source_path": None,
            "evidence": {
                "autonomous": autonomous,
                "item_count": len(drafts),
                "by_category": by_category,
                "top": [d.title for d in drafts[:5]],
            },
        }
    ]

    return PlanningReport(
        title=f"Strategic roadmap — {project_name}",
        vision=vision,
        items=drafts,
        summary={
            "item_count": len(drafts),
            "by_category": by_category,
            "top_priorities": [
                {"title": d.title, "priority": d.priority, "category": d.category}
                for d in drafts[:8]
            ],
            "autonomous": autonomous,
            "execution_gated": True,
        },
        knowledge=knowledge,
        autonomous=autonomous,
    )
