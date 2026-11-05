"""Visual Intelligence — Phase 2 lightweight UI surface inventory (no multimodal yet)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.intelligence.scanner import IGNORE_DIRS

UI_EXTS = {".tsx", ".jsx", ".vue", ".svelte", ".css", ".scss"}
DESIGN_HINT_FILES = {
    "tailwind.config.js",
    "tailwind.config.ts",
    "tailwind.config.mjs",
    "components.json",  # shadcn
    ".storybook",
}


@dataclass
class VisualIntelligenceResult:
    ui_surfaces: list[dict] = field(default_factory=list)
    design_signals: list[str] = field(default_factory=list)
    facts: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def analyze_visual(workspace: Path) -> VisualIntelligenceResult:
    root = workspace.resolve()
    result = VisualIntelligenceResult()

    for hint in DESIGN_HINT_FILES:
        if (root / hint).exists():
            result.design_signals.append(hint)

    pages = []
    components = []
    styles = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        lower_parts = rel.lower().split("/")
        suffix = path.suffix.lower()
        if suffix not in UI_EXTS and path.name not in DESIGN_HINT_FILES:
            continue
        if suffix in {".css", ".scss"}:
            styles.append(rel)
        elif "components" in lower_parts:
            components.append(rel)
        elif any(p in {"pages", "app", "views", "screens"} for p in lower_parts):
            pages.append(rel)
        if len(pages) + len(components) > 120:
            break

    result.ui_surfaces = [
        {"kind": "page", "count": len(pages), "sample": pages[:15]},
        {"kind": "component", "count": len(components), "sample": components[:15]},
        {"kind": "stylesheet", "count": len(styles), "sample": styles[:10]},
    ]

    if pages or components:
        result.facts.append(
            {
                "memory_layer": "architecture",
                "category": "ui_surface",
                "kind": "fact",
                "title": "UI surface inventory",
                "content": (
                    f"Found {len(pages)} page-like files and {len(components)} component files."
                ),
                "confidence": 0.84,
                "source_type": "file",
                "source_path": (pages or components)[0],
                "evidence": {
                    "pages": pages[:10],
                    "components": components[:10],
                    "design_signals": result.design_signals,
                },
            }
        )
    else:
        result.facts.append(
            {
                "memory_layer": "architecture",
                "category": "ui_surface",
                "kind": "unverified",
                "title": "No clear UI surface detected",
                "content": "No common frontend page/component paths found. May be API-only or uses uncommon layout.",
                "confidence": 0.35,
                "source_type": "agent",
                "source_path": None,
                "evidence": {},
            }
        )

    if result.design_signals:
        result.facts.append(
            {
                "memory_layer": "architecture",
                "category": "design_system",
                "kind": "fact",
                "title": "Design-system tooling signals",
                "content": f"Detected: {', '.join(result.design_signals)}",
                "confidence": 0.9,
                "source_type": "file",
                "source_path": result.design_signals[0],
                "evidence": {"signals": result.design_signals},
            }
        )
    else:
        result.facts.append(
            {
                "memory_layer": "architecture",
                "category": "design_system",
                "kind": "inference",
                "title": "No design-system config detected",
                "content": "Tailwind/Storybook/shadcn-style configs not found. Visual system may be ad hoc.",
                "confidence": 0.45,
                "source_type": "agent",
                "source_path": None,
                "evidence": {},
            }
        )

    return result
