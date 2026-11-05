"""Project Intelligence Engine — orchestrates Code/Business/Architecture/Visual."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.intelligence.architecture_intelligence import (
    ArchitectureIntelligenceResult,
    analyze_architecture,
)
from app.intelligence.business_intelligence import BusinessIntelligenceResult, analyze_business
from app.intelligence.code_intelligence import CodeIntelligenceResult, analyze_codebase
from app.intelligence.scanner import ProjectScanResult, scan_workspace
from app.intelligence.visual_intelligence import VisualIntelligenceResult, analyze_visual


@dataclass
class ProjectIntelligenceReport:
    scan: dict = field(default_factory=dict)
    code: dict = field(default_factory=dict)
    business: dict = field(default_factory=dict)
    architecture: dict = field(default_factory=dict)
    visual: dict = field(default_factory=dict)
    knowledge: list[dict] = field(default_factory=list)
    coverage: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _repo_root(workspace: Path) -> Path:
    workspace = workspace.resolve()
    repo = workspace / "repo"
    return repo if repo.exists() else workspace


def run_project_intelligence(workspace: Path) -> ProjectIntelligenceReport:
    root = _repo_root(workspace)
    scan: ProjectScanResult = scan_workspace(root)
    code: CodeIntelligenceResult = analyze_codebase(root)
    business: BusinessIntelligenceResult = analyze_business(root, scan, code.to_dict())
    architecture: ArchitectureIntelligenceResult = analyze_architecture(root, scan, code)
    visual: VisualIntelligenceResult = analyze_visual(root)

    knowledge: list[dict] = []
    knowledge.extend(scan.facts)
    knowledge.extend(code.facts)
    knowledge.extend(business.facts)
    knowledge.extend(architecture.facts)
    knowledge.extend(visual.facts)

    kinds = {"fact": 0, "inference": 0, "unverified": 0}
    for item in knowledge:
        k = item.get("kind", "unverified")
        kinds[k] = kinds.get(k, 0) + 1

    # Coverage heuristic for understanding_progress
    score = 0.15  # baseline scan
    if code.stats.get("symbols"):
        score += 0.2
    if code.stats.get("api_endpoints"):
        score += 0.1
    if business.purpose:
        score += 0.15
    if architecture.layers:
        score += 0.15
    if any(s.get("count", 0) > 0 for s in visual.ui_surfaces):
        score += 0.1
    if kinds.get("unverified", 0) == 0:
        score += 0.05
    score = min(score, 0.95)

    return ProjectIntelligenceReport(
        scan=scan.to_dict(),
        code=code.to_dict(),
        business=business.to_dict(),
        architecture=architecture.to_dict(),
        visual=visual.to_dict(),
        knowledge=knowledge,
        coverage={
            "understanding_progress": round(score, 3),
            "knowledge_counts": kinds,
            "layers": [layer["layer"] for layer in architecture.layers],
            "purpose_known": bool(business.purpose),
        },
    )
