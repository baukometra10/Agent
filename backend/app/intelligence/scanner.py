"""Deterministic Code Intelligence — Phase 1 structural scan (no LLM required)."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.intelligence.languages import EXT_TO_LANGUAGE

IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".next",
    "dist",
    "build",
    "target",
    ".idea",
    ".vscode",
    "coverage",
    "vendor",
}

# Polyglot map — kept in languages.LANGUAGE_PACKS and re-exported here.
EXT_LANGUAGE = dict(EXT_TO_LANGUAGE)
EXT_LANGUAGE.setdefault(".h", "C/C++ Header")
EXT_LANGUAGE.setdefault(".scss", "CSS")

MANIFEST_HINTS = {
    "package.json": "Node.js",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "Yarn",
    "package-lock.json": "npm",
    "requirements.txt": "Python",
    "pyproject.toml": "Python",
    "Pipfile": "Python",
    "poetry.lock": "Poetry",
    "go.mod": "Go",
    "Cargo.toml": "Rust",
    "pom.xml": "Maven",
    "build.gradle": "Gradle",
    "build.gradle.kts": "Gradle",
    "composer.json": "PHP",
    "Gemfile": "Ruby",
    "Dockerfile": "Docker",
    "docker-compose.yml": "Docker Compose",
    "docker-compose.yaml": "Docker Compose",
    "next.config.js": "Next.js",
    "next.config.mjs": "Next.js",
    "next.config.ts": "Next.js",
    "vite.config.ts": "Vite",
    "vite.config.js": "Vite",
    "tsconfig.json": "TypeScript",
    "manage.py": "Django",
    "artisan": "Laravel",
    "Makefile": "Make",
    "makefile": "Make",
    "GNUmakefile": "Make",
    "schema.prisma": "Prisma",
    "hardhat.config.js": "Hardhat",
    "foundry.toml": "Foundry",
    "mix.exs": "Elixir",
    "pubspec.yaml": "Flutter/Dart",
}


@dataclass
class ProjectScanResult:
    languages: list[dict]
    frameworks: list[str]
    tech_stack: dict
    file_stats: dict
    entry_points: list[str] = field(default_factory=list)
    top_directories: list[dict] = field(default_factory=list)
    facts: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        yield path


def _detect_frameworks(root: Path) -> tuple[list[str], dict]:
    frameworks: set[str] = set()
    tech: dict = {"manifests": [], "package_json": None}

    for name, label in MANIFEST_HINTS.items():
        candidate = root / name
        if candidate.exists():
            frameworks.add(label)
            tech["manifests"].append(name)

    pkg = root / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            tech["package_json"] = {
                "name": data.get("name"),
                "scripts": list((data.get("scripts") or {}).keys()),
                "dependencies": list((data.get("dependencies") or {}).keys())[:40],
                "devDependencies": list((data.get("devDependencies") or {}).keys())[:40],
            }
            deps = {
                **(data.get("dependencies") or {}),
                **(data.get("devDependencies") or {}),
            }
            mapping = {
                "next": "Next.js",
                "react": "React",
                "vue": "Vue",
                "nuxt": "Nuxt",
                "@angular/core": "Angular",
                "express": "Express",
                "fastify": "Fastify",
                "nestjs": "NestJS",
                "@nestjs/core": "NestJS",
            }
            for key, label in mapping.items():
                if key in deps:
                    frameworks.add(label)
        except (OSError, json.JSONDecodeError):
            pass

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8", errors="ignore").lower()
        for needle, label in [
            ("fastapi", "FastAPI"),
            ("django", "Django"),
            ("flask", "Flask"),
            ("langgraph", "LangGraph"),
            ("sqlalchemy", "SQLAlchemy"),
        ]:
            if needle in text:
                frameworks.add(label)

    req = root / "requirements.txt"
    if req.exists():
        text = req.read_text(encoding="utf-8", errors="ignore").lower()
        for needle, label in [
            ("fastapi", "FastAPI"),
            ("django", "Django"),
            ("flask", "Flask"),
        ]:
            if needle in text:
                frameworks.add(label)

    return sorted(frameworks), tech


def _entry_points(root: Path) -> list[str]:
    candidates = [
        "main.py",
        "app.py",
        "manage.py",
        "src/main.py",
        "app/main.py",
        "index.js",
        "index.ts",
        "src/index.ts",
        "src/main.ts",
        "src/app/page.tsx",
        "pages/index.tsx",
        "cmd/main.go",
        "main.go",
    ]
    found = []
    for rel in candidates:
        if (root / rel).exists():
            found.append(rel)
    return found


def scan_workspace(workspace: Path) -> ProjectScanResult:
    workspace = workspace.resolve()
    lang_counter: Counter[str] = Counter()
    ext_counter: Counter[str] = Counter()
    dir_counter: Counter[str] = Counter()
    total_files = 0
    total_bytes = 0

    for path in _iter_files(workspace):
        total_files += 1
        try:
            total_bytes += path.stat().st_size
        except OSError:
            pass
        ext = path.suffix.lower()
        if path.name.lower() == "dockerfile":
            ext = ".dockerfile"
        ext_counter[ext or "<none>"] += 1
        language = EXT_LANGUAGE.get(ext)
        if language:
            lang_counter[language] += 1
        try:
            rel = path.relative_to(workspace)
            if rel.parts:
                dir_counter[rel.parts[0]] += 1
        except ValueError:
            pass

    frameworks, tech = _detect_frameworks(workspace)
    languages = [
        {"name": name, "files": count, "share": round(count / max(sum(lang_counter.values()), 1), 4)}
        for name, count in lang_counter.most_common()
    ]
    entry_points = _entry_points(workspace)
    top_directories = [
        {"name": name, "files": count} for name, count in dir_counter.most_common(20)
    ]

    facts: list[dict] = []
    if languages:
        primary = languages[0]["name"]
        facts.append(
            {
                "memory_layer": "project",
                "category": "language",
                "kind": "fact",
                "title": f"Primary language appears to be {primary}",
                "content": f"File extension scan found {languages[0]['files']} {primary} files.",
                "confidence": 0.9,
                "source_type": "file",
                "source_path": ".",
                "evidence": {"languages": languages[:5]},
            }
        )
    for fw in frameworks:
        facts.append(
            {
                "memory_layer": "architecture",
                "category": "framework",
                "kind": "fact",
                "title": f"Detected {fw}",
                "content": f"Manifest or dependency scan detected {fw}.",
                "confidence": 0.85,
                "source_type": "file",
                "source_path": ".",
                "evidence": {"framework": fw, "manifests": tech.get("manifests", [])},
            }
        )
    for ep in entry_points:
        facts.append(
            {
                "memory_layer": "architecture",
                "category": "entrypoint",
                "kind": "fact",
                "title": f"Entry point candidate: {ep}",
                "content": f"File exists at {ep} and is a common application entry point.",
                "confidence": 0.8,
                "source_type": "file",
                "source_path": ep,
                "evidence": {"path": ep},
            }
        )

    if not languages and not frameworks:
        facts.append(
            {
                "memory_layer": "project",
                "category": "coverage",
                "kind": "unverified",
                "title": "Insufficient signal to determine stack",
                "content": "No recognized languages or manifests were found. Needs deeper inspection.",
                "confidence": 0.2,
                "source_type": "agent",
                "source_path": ".",
                "evidence": {"total_files": total_files},
            }
        )

    return ProjectScanResult(
        languages=languages,
        frameworks=frameworks,
        tech_stack=tech,
        file_stats={
            "total_files": total_files,
            "total_bytes": total_bytes,
            "extensions": dict(ext_counter.most_common(40)),
        },
        entry_points=entry_points,
        top_directories=top_directories,
        facts=facts,
    )
