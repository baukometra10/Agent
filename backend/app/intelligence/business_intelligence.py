"""Business Intelligence — purpose, actors, capabilities from docs + structure."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.intelligence.scanner import IGNORE_DIRS, ProjectScanResult

DOC_NAMES = {
    "readme.md",
    "readme.rst",
    "readme.txt",
    "contributing.md",
    "architecture.md",
    "docs/readme.md",
}

ROLE_HINTS = [
    ("admin", "Administrator"),
    ("user", "End User"),
    ("customer", "Customer"),
    ("employee", "Employee"),
    ("manager", "Manager"),
    ("owner", "Owner"),
    ("guest", "Guest"),
    ("operator", "Operator"),
]

CAPABILITY_HINTS = [
    ("auth", "Authentication / identity"),
    ("payment", "Payments"),
    ("billing", "Billing"),
    ("invoice", "Invoicing"),
    ("report", "Reporting"),
    ("dashboard", "Dashboard"),
    ("inventory", "Inventory"),
    ("order", "Orders"),
    ("chat", "Messaging"),
    ("notif", "Notifications"),
    ("permission", "Permissions / authorization"),
    ("workflow", "Workflows"),
]


@dataclass
class BusinessIntelligenceResult:
    purpose: str | None = None
    actors: list[dict] = field(default_factory=list)
    capabilities: list[dict] = field(default_factory=list)
    contradictions: list[dict] = field(default_factory=list)
    facts: list[dict] = field(default_factory=list)
    doc_excerpts: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _read_docs(root: Path) -> list[tuple[str, str]]:
    docs: list[tuple[str, str]] = []
    # Named docs
    for name in DOC_NAMES:
        path = root / name
        if path.exists() and path.is_file():
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")[:8000]
                docs.append((name, text))
            except OSError:
                pass
    # Any markdown under docs/ (limited)
    docs_dir = root / "docs"
    if docs_dir.is_dir():
        count = 0
        for path in docs_dir.rglob("*.md"):
            if any(part in IGNORE_DIRS for part in path.parts):
                continue
            try:
                rel = str(path.relative_to(root)).replace("\\", "/")
                text = path.read_text(encoding="utf-8", errors="ignore")[:4000]
                docs.append((rel, text))
            except OSError:
                continue
            count += 1
            if count >= 8:
                break
    return docs


def _first_paragraph(text: str) -> str | None:
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            if lines:
                break
            continue
        if s.startswith("#"):
            # keep heading as purpose seed if no body yet
            if not lines:
                lines.append(s.lstrip("# ").strip())
            continue
        if s.startswith("```"):
            break
        lines.append(s)
        if sum(len(x) for x in lines) > 280:
            break
    para = " ".join(lines).strip()
    return para or None


def analyze_business(
    workspace: Path,
    scan: ProjectScanResult | dict,
    code: dict | None = None,
) -> BusinessIntelligenceResult:
    root = workspace.resolve()
    scan_dict = scan.to_dict() if isinstance(scan, ProjectScanResult) else scan
    result = BusinessIntelligenceResult()
    docs = _read_docs(root)

    for path, text in docs:
        result.doc_excerpts.append({"path": path, "chars": len(text)})
        if result.purpose is None:
            purpose = _first_paragraph(text)
            if purpose:
                result.purpose = purpose
                result.facts.append(
                    {
                        "memory_layer": "project",
                        "category": "purpose",
                        "kind": "fact",
                        "title": "Project purpose extracted from documentation",
                        "content": purpose,
                        "confidence": 0.78,
                        "source_type": "doc",
                        "source_path": path,
                        "evidence": {"excerpt": purpose[:400]},
                    }
                )

        lower = text.lower()
        for needle, label in ROLE_HINTS:
            if re.search(rf"\b{needle}s?\b", lower):
                if not any(a["label"] == label for a in result.actors):
                    result.actors.append(
                        {"label": label, "signal": needle, "source": path}
                    )

        for needle, label in CAPABILITY_HINTS:
            if needle in lower:
                if not any(c["label"] == label for c in result.capabilities):
                    result.capabilities.append(
                        {"label": label, "signal": needle, "source": path, "kind": "doc"}
                    )

    # Structural capability signals from directories / frameworks
    frameworks = {str(f).lower() for f in (scan_dict.get("frameworks") or [])}
    tops = [d.get("name", "").lower() for d in (scan_dict.get("top_directories") or [])]
    structural_map = {
        "auth": "Authentication / identity",
        "users": "User management",
        "billing": "Billing",
        "payments": "Payments",
        "reports": "Reporting",
        "dashboard": "Dashboard",
        "admin": "Administration",
        "api": "API surface",
    }
    for key, label in structural_map.items():
        if key in tops or any(key in f for f in frameworks):
            if not any(c["label"] == label for c in result.capabilities):
                result.capabilities.append(
                    {"label": label, "signal": key, "source": "structure", "kind": "structure"}
                )
                result.facts.append(
                    {
                        "memory_layer": "project",
                        "category": "capability",
                        "kind": "inference",
                        "title": f"Capability signal: {label}",
                        "content": f"Inferred from project structure/framework signal '{key}'.",
                        "confidence": 0.55,
                        "source_type": "file",
                        "source_path": key if key in tops else ".",
                        "evidence": {"signal": key, "frameworks": list(frameworks)[:10]},
                    }
                )

    for actor in result.actors:
        result.facts.append(
            {
                "memory_layer": "project",
                "category": "actor",
                "kind": "inference",
                "title": f"Possible actor: {actor['label']}",
                "content": f"Documentation mentions '{actor['signal']}'.",
                "confidence": 0.6,
                "source_type": "doc",
                "source_path": actor["source"],
                "evidence": actor,
            }
        )

    # Contradiction: docs claim API but no routes found
    code = code or {}
    endpoints = code.get("api_endpoints") or []
    if any(c["label"] == "API surface" for c in result.capabilities) and not endpoints:
        result.contradictions.append(
            {
                "title": "API capability hinted but no routes extracted",
                "detail": "Structure/docs suggest an API, but code intelligence found no endpoints.",
            }
        )
        result.facts.append(
            {
                "memory_layer": "project",
                "category": "contradiction",
                "kind": "unverified",
                "title": "Possible gap between claimed API capability and detected routes",
                "content": "Needs verification: API folder/docs exist without detected handlers.",
                "confidence": 0.4,
                "source_type": "agent",
                "source_path": None,
                "evidence": {"capabilities": result.capabilities, "endpoints": 0},
            }
        )

    if not result.purpose:
        name_guess = workspace.name
        result.facts.append(
            {
                "memory_layer": "project",
                "category": "purpose",
                "kind": "unverified",
                "title": "Project purpose not evidenced in docs",
                "content": (
                    f"No README/docs purpose paragraph found for '{name_guess}'. "
                    "Business goals remain unverified."
                ),
                "confidence": 0.25,
                "source_type": "agent",
                "source_path": None,
                "evidence": {"docs_scanned": [d[0] for d in docs]},
            }
        )

    return result
