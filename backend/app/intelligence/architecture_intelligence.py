"""Architecture Intelligence — layers, coupling signals, change-impact hints."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.intelligence.code_intelligence import CodeIntelligenceResult
from app.intelligence.scanner import ProjectScanResult


LAYER_HINTS = {
    "api": ("api", "routes", "controllers", "handlers", "endpoints"),
    "domain": ("domain", "models", "entities", "services", "core"),
    "data": ("db", "database", "repositories", "migrations", "prisma", "sqlalchemy"),
    "ui": ("components", "pages", "views", "ui", "frontend", "app"),
    "infra": ("docker", "deploy", "infra", "ci", "ops", "k8s"),
    "tests": ("tests", "test", "__tests__", "spec"),
}


@dataclass
class ArchitectureIntelligenceResult:
    layers: list[dict] = field(default_factory=list)
    coupling: list[dict] = field(default_factory=list)
    risks: list[dict] = field(default_factory=list)
    suggested_future: list[dict] = field(default_factory=list)
    facts: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _classify_path(rel: str) -> str | None:
    parts = rel.lower().replace("\\", "/").split("/")
    for layer, hints in LAYER_HINTS.items():
        if any(h in parts for h in hints):
            return layer
    return None


def analyze_architecture(
    workspace: Path,
    scan: ProjectScanResult | dict,
    code: CodeIntelligenceResult | dict,
) -> ArchitectureIntelligenceResult:
    scan_dict = scan.to_dict() if isinstance(scan, ProjectScanResult) else scan
    code_dict = code.to_dict() if isinstance(code, CodeIntelligenceResult) else code
    result = ArchitectureIntelligenceResult()

    layer_files: dict[str, list[str]] = defaultdict(list)
    for mod in code_dict.get("modules") or []:
        path = mod.get("path") or ""
        layer = _classify_path(path)
        if layer:
            layer_files[layer].append(path)

    for top in scan_dict.get("top_directories") or []:
        name = top.get("name", "")
        layer = _classify_path(name)
        if layer and name not in {Path(p).parts[0] for p in layer_files[layer]}:
            layer_files[layer].append(name)

    for layer, files in sorted(layer_files.items()):
        result.layers.append(
            {
                "layer": layer,
                "files": files[:30],
                "file_count": len(files),
            }
        )
        result.facts.append(
            {
                "memory_layer": "architecture",
                "category": "layer",
                "kind": "fact",
                "title": f"Detected {layer} layer signals",
                "content": f"{len(files)} paths classified under architectural layer '{layer}'.",
                "confidence": 0.8,
                "source_type": "file",
                "source_path": files[0] if files else ".",
                "evidence": {"layer": layer, "sample": files[:8]},
            }
        )

    # Coupling: files that both export many symbols and import many modules
    import_count = Counter()
    for edge in code_dict.get("import_edges") or []:
        import_count[edge.get("from_path")] += 1
    symbol_count = Counter()
    for sym in code_dict.get("symbols") or []:
        symbol_count[sym.get("path")] += 1

    scored = []
    for path, imports in import_count.items():
        score = imports + symbol_count.get(path, 0)
        scored.append((path, imports, symbol_count.get(path, 0), score))
    scored.sort(key=lambda x: x[3], reverse=True)
    for path, imports, symbols, score in scored[:8]:
        result.coupling.append(
            {
                "path": path,
                "outbound_imports": imports,
                "symbols": symbols,
                "score": score,
            }
        )

    if scored and scored[0][3] >= 15:
        path = scored[0][0]
        result.risks.append(
            {
                "title": "Possible hub / God-module",
                "path": path,
                "detail": "High import and symbol concentration may indicate tight coupling.",
            }
        )
        result.facts.append(
            {
                "memory_layer": "architecture",
                "category": "risk",
                "kind": "inference",
                "title": f"Potential coupling hotspot: {path}",
                "content": "Static metrics suggest this module is a dependency hub; changes may have wide blast radius.",
                "confidence": 0.58,
                "source_type": "agent",
                "source_path": path,
                "evidence": {"outbound_imports": scored[0][1], "symbols": scored[0][2]},
            }
        )

    endpoints = code_dict.get("api_endpoints") or []
    if endpoints and "data" not in layer_files:
        result.suggested_future.append(
            {
                "title": "Clarify data access boundary",
                "reason": "APIs detected without a clear data-layer directory convention.",
            }
        )
        result.facts.append(
            {
                "memory_layer": "architecture",
                "category": "recommendation",
                "kind": "inference",
                "title": "Data layer boundary is unclear",
                "content": "Routes exist but no conventional data/repository layer was classified.",
                "confidence": 0.5,
                "source_type": "agent",
                "source_path": None,
                "evidence": {"api_count": len(endpoints)},
            }
        )

    if not result.layers:
        result.facts.append(
            {
                "memory_layer": "architecture",
                "category": "coverage",
                "kind": "unverified",
                "title": "Architecture layers not confidently mapped",
                "content": "Directory and module naming did not match known layer conventions.",
                "confidence": 0.3,
                "source_type": "agent",
                "source_path": str(workspace),
                "evidence": {"top_directories": scan_dict.get("top_directories")},
            }
        )

    # Impact template: changing an entry point affects discovered routes
    for flow in code_dict.get("entry_flows") or []:
        result.facts.append(
            {
                "memory_layer": "architecture",
                "category": "impact",
                "kind": "inference",
                "title": f"Change impact anchor: {flow.get('entry')}",
                "content": "Modifying this entry point may affect process bootstrapping and downstream wiring.",
                "confidence": float(flow.get("confidence") or 0.5),
                "source_type": "file",
                "source_path": flow.get("entry"),
                "evidence": {"entry_flow": flow, "related_apis": len(endpoints)},
            }
        )

    return result
