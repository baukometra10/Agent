"""Phase 5 — Analysis Engine: problems & opportunities from Project Intelligence."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any


ANALYSIS_CATEGORIES = (
    "quality",
    "architecture",
    "performance",
    "security",
    "ux",
    "feature",
    "integration",
    "maintainability",
)


@dataclass
class FindingDraft:
    category: str
    kind: str  # problem|opportunity|risk
    severity: str
    title: str
    description: str
    recommendation: str
    confidence: float
    affected_parts: list[Any] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    source_agent: str = "AnalysisEngine"

    def fingerprint(self) -> str:
        raw = f"{self.category}|{self.kind}|{self.title}|{sorted(map(str, self.affected_parts))}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["fingerprint"] = self.fingerprint()
        return data


@dataclass
class AnalysisReport:
    findings: list[FindingDraft] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    knowledge: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
            "knowledge": self.knowledge,
        }


def _add(findings: list[FindingDraft], draft: FindingDraft) -> None:
    fp = draft.fingerprint()
    if any(f.fingerprint() == fp for f in findings):
        return
    findings.append(draft)


def _analyze_quality(intel: dict[str, Any], findings: list[FindingDraft]) -> None:
    code = intel.get("code") or {}
    scan = intel.get("scan") or {}
    stats = code.get("stats") or {}
    file_stats = scan.get("file_stats") or {}
    total_files = int(file_stats.get("total_files") or 0)
    symbols = int(stats.get("symbols") or 0)
    if total_files > 80 and symbols == 0:
        _add(
            findings,
            FindingDraft(
                category="quality",
                kind="problem",
                severity="high",
                title="Large codebase with no extracted symbols",
                description="File count is high but symbol extraction returned empty — analysis coverage is weak.",
                recommendation="Improve language parsers / Tree-sitter coverage for the dominant languages.",
                confidence=0.75,
                affected_parts=["codebase"],
                evidence={"total_files": total_files, "symbols": symbols},
            ),
        )
    entry_flows = code.get("entry_flows") or scan.get("entry_points") or []
    if total_files > 10 and not entry_flows:
        _add(
            findings,
            FindingDraft(
                category="quality",
                kind="risk",
                severity="medium",
                title="No clear application entry points detected",
                description="Without entry points, change impact and boot-path testing remain uncertain.",
                recommendation="Document and tag main entry modules; verify runtime start commands.",
                confidence=0.65,
                affected_parts=["boot"],
                evidence={"total_files": total_files},
            ),
        )


def _analyze_architecture(intel: dict[str, Any], findings: list[FindingDraft]) -> None:
    arch = intel.get("architecture") or {}
    for risk in arch.get("risks") or []:
        _add(
            findings,
            FindingDraft(
                category="architecture",
                kind="risk",
                severity="high",
                title=risk.get("title") or "Architecture risk",
                description=risk.get("detail") or str(risk),
                recommendation="Reduce coupling around the hotspot; introduce clearer module boundaries.",
                confidence=0.6,
                affected_parts=[risk.get("path")] if risk.get("path") else [],
                evidence=risk,
                source_agent="SoftwareArchitect",
            ),
        )
    layers = arch.get("layers") or []
    layer_names = {layer.get("layer") for layer in layers}
    if "api" in layer_names and "data" not in layer_names:
        _add(
            findings,
            FindingDraft(
                category="architecture",
                kind="problem",
                severity="medium",
                title="API layer without clear data boundary",
                description="Routes/API signals exist but no conventional data/repository layer was mapped.",
                recommendation="Introduce an explicit data-access layer and keep handlers thin.",
                confidence=0.55,
                affected_parts=["api", "data"],
                evidence={"layers": list(layer_names)},
            ),
        )
    for item in arch.get("suggested_future") or []:
        _add(
            findings,
            FindingDraft(
                category="architecture",
                kind="opportunity",
                severity="low",
                title=item.get("title") or "Architecture opportunity",
                description=item.get("reason") or str(item),
                recommendation=item.get("title") or "Review architectural suggestion",
                confidence=0.5,
                affected_parts=[],
                evidence=item,
            ),
        )


def _analyze_security(intel: dict[str, Any], findings: list[FindingDraft]) -> None:
    code = intel.get("code") or {}
    business = intel.get("business") or {}
    endpoints = code.get("api_endpoints") or []
    actors = business.get("actors") or []
    caps = {c.get("label", "").lower() for c in (business.get("capabilities") or [])}
    if endpoints and not actors:
        _add(
            findings,
            FindingDraft(
                category="security",
                kind="risk",
                severity="high",
                title="HTTP surface without evidenced roles/actors",
                description=f"{len(endpoints)} routes/pages detected but no user roles were evidenced in docs/structure.",
                recommendation="Map authentication/authorization model before changing privileged flows.",
                confidence=0.7,
                affected_parts=[e.get("path") for e in endpoints[:8] if isinstance(e, dict)],
                evidence={"api_count": len(endpoints), "sample": endpoints[:5]},
                source_agent="SecurityAuditor",
            ),
        )
    if any("auth" in c or "permission" in c for c in caps) and not endpoints:
        _add(
            findings,
            FindingDraft(
                category="security",
                kind="problem",
                severity="medium",
                title="Auth capability hinted but no routes extracted",
                description="Security-related capabilities appear in structure/docs without detected handlers.",
                recommendation="Locate auth entrypoints and verify permission checks with tests.",
                confidence=0.55,
                affected_parts=["auth"],
                evidence={"capabilities": list(caps)},
            ),
        )


def _analyze_performance(intel: dict[str, Any], findings: list[FindingDraft]) -> None:
    arch = intel.get("architecture") or {}
    coupling = arch.get("coupling") or []
    if coupling:
        top = coupling[0]
        if int(top.get("score") or 0) >= 20:
            _add(
                findings,
                FindingDraft(
                    category="performance",
                    kind="risk",
                    severity="medium",
                    title=f"Hot module may become a runtime bottleneck: {top.get('path')}",
                    description="High symbol/import concentration often correlates with change risk and load hotspots.",
                    recommendation="Profile this module; split responsibilities; cache expensive paths if proven hot.",
                    confidence=0.45,
                    affected_parts=[top.get("path")],
                    evidence=top,
                ),
            )


def _analyze_ux(intel: dict[str, Any], findings: list[FindingDraft]) -> None:
    visual = intel.get("visual") or {}
    surfaces = visual.get("ui_surfaces") or []
    pages = next((s for s in surfaces if s.get("kind") == "page"), None)
    components = next((s for s in surfaces if s.get("kind") == "component"), None)
    design_signals = visual.get("design_signals") or []
    if pages and int(pages.get("count") or 0) >= 5 and not design_signals:
        _add(
            findings,
            FindingDraft(
                category="ux",
                kind="opportunity",
                severity="medium",
                title="Multiple UI pages without design-system tooling",
                description="UI surface exists but no Tailwind/Storybook/shadcn-style config was detected.",
                recommendation="Introduce a design system / shared component library to reduce UI drift.",
                confidence=0.55,
                affected_parts=(pages.get("sample") or [])[:5],
                evidence={"pages": pages, "components": components, "design_signals": design_signals},
            ),
        )
    if components and int(components.get("count") or 0) == 0 and pages and int(pages.get("count") or 0) > 0:
        _add(
            findings,
            FindingDraft(
                category="ux",
                kind="problem",
                severity="low",
                title="Pages found without reusable components folder signal",
                description="Page-like files exist but component inventory is empty — possible duplication.",
                recommendation="Extract shared UI primitives and standardize layout patterns.",
                confidence=0.4,
                affected_parts=(pages.get("sample") or [])[:5],
                evidence={"pages": pages},
            ),
        )


def _analyze_features(intel: dict[str, Any], findings: list[FindingDraft]) -> None:
    business = intel.get("business") or {}
    for contradiction in business.get("contradictions") or []:
        _add(
            findings,
            FindingDraft(
                category="feature",
                kind="problem",
                severity="medium",
                title=contradiction.get("title") or "Business contradiction",
                description=contradiction.get("detail") or str(contradiction),
                recommendation="Reconcile documentation claims with implemented capabilities.",
                confidence=0.55,
                affected_parts=[],
                evidence=contradiction,
                source_agent="BusinessLogicAnalyst",
            ),
        )
    caps = business.get("capabilities") or []
    if business.get("purpose") and len(caps) < 2:
        _add(
            findings,
            FindingDraft(
                category="feature",
                kind="opportunity",
                severity="low",
                title="Thin capability map relative to stated purpose",
                description="Purpose is known but few capabilities were evidenced — product expansion surface may exist.",
                recommendation="Derive a capability backlog from user journeys and unmet jobs-to-be-done.",
                confidence=0.4,
                affected_parts=[],
                evidence={"purpose": business.get("purpose"), "capabilities": caps},
                source_agent="FeatureStrategist",
            ),
        )


def _analyze_integration(intel: dict[str, Any], findings: list[FindingDraft]) -> None:
    scan = intel.get("scan") or {}
    tech = scan.get("tech_stack") or {}
    pkg = tech.get("package_json") or {}
    deps = list(pkg.get("dependencies") or [])
    integration_hints = [
        d
        for d in deps
        if any(x in str(d).lower() for x in ("stripe", "aws", "firebase", "supabase", "openai", "sentry", "redis"))
    ]
    if integration_hints:
        _add(
            findings,
            FindingDraft(
                category="integration",
                kind="opportunity",
                severity="info",
                title="External integrations detected in dependencies",
                description="Third-party packages suggest integration surfaces that need monitoring and contract tests.",
                recommendation="Document integration owners, failure modes, and health checks.",
                confidence=0.7,
                affected_parts=integration_hints[:10],
                evidence={"dependencies": integration_hints},
            ),
        )
    code = intel.get("code") or {}
    if not (code.get("api_endpoints") or []) and "api" in {
        d.get("name", "").lower() for d in (scan.get("top_directories") or [])
    }:
        _add(
            findings,
            FindingDraft(
                category="integration",
                kind="problem",
                severity="medium",
                title="API directory present but no routes extracted",
                description="Integration/API folder exists without detected handlers — external contracts may be opaque.",
                recommendation="Inventory public endpoints and generate OpenAPI/contract docs.",
                confidence=0.5,
                affected_parts=["api"],
                evidence={"top_directories": scan.get("top_directories")},
            ),
        )


def _analyze_maintainability(intel: dict[str, Any], findings: list[FindingDraft]) -> None:
    coverage = intel.get("coverage") or {}
    if not coverage.get("purpose_known"):
        _add(
            findings,
            FindingDraft(
                category="maintainability",
                kind="problem",
                severity="medium",
                title="Project purpose not documented",
                description="No evidenced purpose paragraph in README/docs — onboarding and change rationale will suffer.",
                recommendation="Add a concise product purpose and architecture overview to README/docs.",
                confidence=0.8,
                affected_parts=["README.md", "docs"],
                evidence={"coverage": coverage},
            ),
        )
    knowledge_counts = coverage.get("knowledge_counts") or {}
    unverified = int(knowledge_counts.get("unverified") or 0)
    facts = int(knowledge_counts.get("fact") or 0)
    if unverified > facts + 2:
        _add(
            findings,
            FindingDraft(
                category="maintainability",
                kind="risk",
                severity="medium",
                title="Knowledge base skewed toward unverified items",
                description=f"unverified={unverified} exceeds facts={facts}; decisions may rest on weak ground.",
                recommendation="Verify top unverified nodes against code/docs before planning major changes.",
                confidence=0.7,
                affected_parts=["knowledge"],
                evidence=knowledge_counts,
            ),
        )


def run_analysis_engine(intelligence: dict[str, Any]) -> AnalysisReport:
    findings: list[FindingDraft] = []
    _analyze_quality(intelligence, findings)
    _analyze_architecture(intelligence, findings)
    _analyze_security(intelligence, findings)
    _analyze_performance(intelligence, findings)
    _analyze_ux(intelligence, findings)
    _analyze_features(intelligence, findings)
    _analyze_integration(intelligence, findings)
    _analyze_maintainability(intelligence, findings)

    by_category = {c: 0 for c in ANALYSIS_CATEGORIES}
    by_kind = {"problem": 0, "opportunity": 0, "risk": 0}
    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in findings:
        by_category[f.category] = by_category.get(f.category, 0) + 1
        by_kind[f.kind] = by_kind.get(f.kind, 0) + 1
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1

    knowledge = [
        {
            "memory_layer": "architecture",
            "category": "analysis_summary",
            "kind": "inference",
            "title": f"Analysis Engine produced {len(findings)} findings",
            "content": (
                f"Problems={by_kind.get('problem', 0)}, "
                f"risks={by_kind.get('risk', 0)}, "
                f"opportunities={by_kind.get('opportunity', 0)}."
            ),
            "confidence": 0.7 if findings else 0.4,
            "source_type": "agent",
            "source_path": None,
            "evidence": {
                "by_category": by_category,
                "by_kind": by_kind,
                "by_severity": by_severity,
            },
        }
    ]
    for f in findings[:20]:
        knowledge.append(
            {
                "memory_layer": "architecture" if f.category in {"architecture", "security", "performance"} else "project",
                "category": "finding",
                "kind": "inference" if f.confidence >= 0.55 else "unverified",
                "title": f"[{f.severity}] {f.title}",
                "content": f"{f.description} Recommendation: {f.recommendation}",
                "confidence": f.confidence,
                "source_type": "agent",
                "source_path": (f.affected_parts[0] if f.affected_parts else None),
                "evidence": {
                    "category": f.category,
                    "kind": f.kind,
                    "severity": f.severity,
                    "fingerprint": f.fingerprint(),
                    **(f.evidence or {}),
                },
            }
        )

    return AnalysisReport(
        findings=findings,
        summary={
            "total": len(findings),
            "by_category": by_category,
            "by_kind": by_kind,
            "by_severity": by_severity,
        },
        knowledge=knowledge,
    )
