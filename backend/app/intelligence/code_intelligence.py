"""Code Intelligence — symbols, imports, APIs, entry flows (deterministic)."""

from __future__ import annotations

import ast
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.intelligence.languages import DEEP_SOURCE_EXTS, EXT_TO_LANGUAGE
from app.intelligence.scanner import IGNORE_DIRS

MAX_FILES = 600
MAX_FILE_BYTES = 400_000


@dataclass
class SymbolInfo:
    name: str
    kind: str  # class|function|method
    path: str
    line: int
    parent: str | None = None


@dataclass
class ImportEdge:
    from_path: str
    imported: str
    resolved_path: str | None = None


@dataclass
class ApiEndpoint:
    method: str
    path: str
    handler: str
    source_path: str
    line: int
    framework: str


@dataclass
class CodeIntelligenceResult:
    symbols: list[SymbolInfo] = field(default_factory=list)
    import_edges: list[ImportEdge] = field(default_factory=list)
    api_endpoints: list[ApiEndpoint] = field(default_factory=list)
    modules: list[dict] = field(default_factory=list)
    entry_flows: list[dict] = field(default_factory=list)
    facts: list[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _iter_source_files(root: Path):
    count = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        suffix = path.suffix.lower()
        if path.name.lower() == "dockerfile":
            suffix = ".dockerfile"
        if suffix not in DEEP_SOURCE_EXTS and suffix not in {
            ".py",
            ".ts",
            ".tsx",
            ".js",
            ".jsx",
            ".go",
            ".rs",
            ".java",
            ".kt",
            ".cs",
            ".rb",
            ".php",
            ".swift",
            ".scala",
            ".dart",
            ".ex",
            ".exs",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
        }:
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        yield path
        count += 1
        if count >= MAX_FILES:
            return


def _analyze_python(root: Path, path: Path, result: CodeIntelligenceResult) -> None:
    rel = str(path.relative_to(root)).replace("\\", "/")
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source)
    except (OSError, SyntaxError):
        return

    classes = 0
    functions = 0
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            classes += 1
            result.symbols.append(
                SymbolInfo(name=node.name, kind="class", path=rel, line=node.lineno)
            )
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions += 1
                    result.symbols.append(
                        SymbolInfo(
                            name=child.name,
                            kind="method",
                            path=rel,
                            line=child.lineno,
                            parent=node.name,
                        )
                    )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions += 1
            result.symbols.append(
                SymbolInfo(name=node.name, kind="function", path=rel, line=node.lineno)
            )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result.import_edges.append(ImportEdge(from_path=rel, imported=alias.name))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            result.import_edges.append(ImportEdge(from_path=rel, imported=mod))

        # FastAPI / Starlette style decorators
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                method, route = _fastapi_route(dec)
                if method and route is not None:
                    result.api_endpoints.append(
                        ApiEndpoint(
                            method=method,
                            path=route,
                            handler=node.name,
                            source_path=rel,
                            line=node.lineno,
                            framework="FastAPI",
                        )
                    )

    result.modules.append(
        {
            "path": rel,
            "language": "Python",
            "classes": classes,
            "functions": functions,
        }
    )


def _fastapi_route(dec: ast.AST) -> tuple[str | None, str | None]:
    if not isinstance(dec, ast.Call):
        return None, None
    func = dec.func
    attr = None
    if isinstance(func, ast.Attribute):
        attr = func.attr.lower()
    if attr not in {"get", "post", "put", "patch", "delete", "options", "head"}:
        return None, None
    if not dec.args:
        return attr.upper(), ""
    arg0 = dec.args[0]
    if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
        return attr.upper(), arg0.value
    return attr.upper(), None


_JS_EXPORT_RE = re.compile(
    r"export\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let|var)\s+([A-Za-z0-9_]+)"
)
_JS_IMPORT_RE = re.compile(r"""import\s+(?:.+\s+from\s+)?['\"]([^'\"]+)['\"]""")
_JS_ROUTE_RE = re.compile(
    r"""(?:app|router|Router)\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]+)['\"]""",
    re.I,
)
_NEXT_ROUTE_HINT = re.compile(r"(page|route|layout)\.(tsx|ts|jsx|js)$")


def _analyze_js_like(root: Path, path: Path, result: CodeIntelligenceResult) -> None:
    rel = str(path.relative_to(root)).replace("\\", "/")
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return

    exports = _JS_EXPORT_RE.findall(source)
    for name in exports[:50]:
        result.symbols.append(SymbolInfo(name=name, kind="export", path=rel, line=1))

    for imp in _JS_IMPORT_RE.findall(source):
        result.import_edges.append(ImportEdge(from_path=rel, imported=imp))

    for method, route in _JS_ROUTE_RE.findall(source):
        result.api_endpoints.append(
            ApiEndpoint(
                method=method.upper(),
                path=route,
                handler=rel,
                source_path=rel,
                line=1,
                framework="Express/Router",
            )
        )

    if _NEXT_ROUTE_HINT.search(path.name):
        # Approximate Next.js App Router path from filesystem
        parts = Path(rel).parts
        if "app" in parts:
            idx = parts.index("app")
            segs = [p for p in parts[idx + 1 : -1] if not p.startswith("(")]
            route = "/" + "/".join(segs) if segs else "/"
            result.api_endpoints.append(
                ApiEndpoint(
                    method="PAGE",
                    path=route,
                    handler=path.name,
                    source_path=rel,
                    line=1,
                    framework="Next.js",
                )
            )

    result.modules.append(
        {
            "path": rel,
            "language": "JavaScript/TypeScript",
            "exports": len(exports),
        }
    )


def _analyze_go(root: Path, path: Path, result: CodeIntelligenceResult) -> None:
    rel = str(path.relative_to(root)).replace("\\", "/")
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return
    for match in re.finditer(r"func\s+(?:\([^)]+\)\s*)?([A-Za-z0-9_]+)\s*\(", source):
        result.symbols.append(SymbolInfo(name=match.group(1), kind="function", path=rel, line=1))
    for match in re.finditer(
        r"""\.(Get|Post|Put|Patch|Delete)\(\s*"([^"]+)" """, source
    ):
        result.api_endpoints.append(
            ApiEndpoint(
                method=match.group(1).upper(),
                path=match.group(2),
                handler=rel,
                source_path=rel,
                line=1,
                framework="Go HTTP",
            )
        )
    result.modules.append({"path": rel, "language": "Go"})


_GENERIC_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "Rust": [
        (r"\bfn\s+([A-Za-z0-9_]+)\s*[<(]", "function"),
        (r"\bstruct\s+([A-Za-z0-9_]+)", "class"),
        (r"\benum\s+([A-Za-z0-9_]+)", "class"),
        (r"\bmod\s+([A-Za-z0-9_]+)", "module"),
    ],
    "Java": [
        (r"\bclass\s+([A-Za-z0-9_]+)", "class"),
        (r"\binterface\s+([A-Za-z0-9_]+)", "class"),
        (r"(?:public|private|protected)\s+(?:static\s+)?[\w<>\[\]]+\s+([A-Za-z0-9_]+)\s*\(", "method"),
    ],
    "Kotlin": [
        (r"\bclass\s+([A-Za-z0-9_]+)", "class"),
        (r"\bfun\s+([A-Za-z0-9_]+)\s*\(", "function"),
        (r"\bobject\s+([A-Za-z0-9_]+)", "class"),
    ],
    "C#": [
        (r"\bclass\s+([A-Za-z0-9_]+)", "class"),
        (r"\binterface\s+([A-Za-z0-9_]+)", "class"),
        (r"(?:public|private|protected|internal)\s+(?:static\s+|async\s+)*[\w<>\[\]]+\s+([A-Za-z0-9_]+)\s*\(", "method"),
    ],
    "Ruby": [
        (r"\bclass\s+([A-Za-z0-9_]+)", "class"),
        (r"\bmodule\s+([A-Za-z0-9_]+)", "module"),
        (r"\bdef\s+([A-Za-z0-9_?!]+)", "function"),
    ],
    "PHP": [
        (r"\bclass\s+([A-Za-z0-9_]+)", "class"),
        (r"\bfunction\s+([A-Za-z0-9_]+)\s*\(", "function"),
    ],
    "Swift": [
        (r"\bclass\s+([A-Za-z0-9_]+)", "class"),
        (r"\bstruct\s+([A-Za-z0-9_]+)", "class"),
        (r"\bfunc\s+([A-Za-z0-9_]+)\s*\(", "function"),
    ],
    "Scala": [
        (r"\bclass\s+([A-Za-z0-9_]+)", "class"),
        (r"\bobject\s+([A-Za-z0-9_]+)", "class"),
        (r"\bdef\s+([A-Za-z0-9_]+)\s*[(\[]", "function"),
    ],
    "Dart": [
        (r"\bclass\s+([A-Za-z0-9_]+)", "class"),
        (r"(?:void|[A-Za-z0-9_<>,\s]+)\s+([A-Za-z0-9_]+)\s*\([^;]*\)\s*\{", "function"),
    ],
    "Elixir": [
        (r"\bdefmodule\s+([A-Za-z0-9_.]+)", "module"),
        (r"\bdef(?:p)?\s+([A-Za-z0-9_?!]+)", "function"),
    ],
    "C": [
        (r"^\s*(?:static\s+)?(?:[\w\s\*]+)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^;]*\)\s*\{", "function"),
        (r"\bstruct\s+([A-Za-z0-9_]+)", "class"),
    ],
    "C++": [
        (r"\bclass\s+([A-Za-z0-9_]+)", "class"),
        (r"\bstruct\s+([A-Za-z0-9_]+)", "class"),
        (r"^\s*(?:[\w:<>\*&]+\s+)+([A-Za-z_][A-Za-z0-9_]*)\s*\([^;]*\)\s*\{", "function"),
    ],
}


def _analyze_generic(root: Path, path: Path, language: str, result: CodeIntelligenceResult) -> None:
    rel = str(path.relative_to(root)).replace("\\", "/")
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return
    patterns = _GENERIC_PATTERNS.get(language, [])
    seen: set[tuple[str, str]] = set()
    for pattern, kind in patterns:
        for match in re.finditer(pattern, source, flags=re.MULTILINE):
            name = match.group(1)
            key = (kind, name)
            if key in seen:
                continue
            seen.add(key)
            result.symbols.append(SymbolInfo(name=name, kind=kind, path=rel, line=1))
            if len(seen) >= 80:
                break

    # Framework route hints
    if language in {"Java", "Kotlin", "C#"}:
        for match in re.finditer(
            r"""@(?:Get|Post|Put|Patch|Delete|Request)Mapping\(\s*(?:value\s*=\s*)?["']([^"']+)["']""",
            source,
        ):
            result.api_endpoints.append(
                ApiEndpoint(
                    method="HTTP",
                    path=match.group(1),
                    handler=rel,
                    source_path=rel,
                    line=1,
                    framework=f"{language} annotations",
                )
            )
    if language == "PHP":
        for match in re.finditer(
            r"""Route::(get|post|put|patch|delete)\(\s*['\"]([^'\"]+)['\"]""",
            source,
            flags=re.I,
        ):
            result.api_endpoints.append(
                ApiEndpoint(
                    method=match.group(1).upper(),
                    path=match.group(2),
                    handler=rel,
                    source_path=rel,
                    line=1,
                    framework="Laravel",
                )
            )
    if language == "Ruby":
        for match in re.finditer(
            r"""\b(?:get|post|put|patch|delete)\s+['\"]([^'\"]+)['\"]""",
            source,
            flags=re.I,
        ):
            result.api_endpoints.append(
                ApiEndpoint(
                    method="ROUTE",
                    path=match.group(1),
                    handler=rel,
                    source_path=rel,
                    line=1,
                    framework="Rails/Sinatra",
                )
            )

    result.modules.append({"path": rel, "language": language, "symbols": len(seen)})


def _build_entry_flows(root: Path, result: CodeIntelligenceResult) -> None:
    candidates = [
        "main.py",
        "app.py",
        "manage.py",
        "app/main.py",
        "src/main.py",
        "src/index.ts",
        "src/main.ts",
        "src/app/page.tsx",
        "app/page.tsx",
        "main.go",
        "cmd/main.go",
        "src/main.rs",
        "Main.java",
        "Program.cs",
        "src/main/java",
        "lib/main.dart",
        "index.php",
        "config/routes.rb",
    ]
    for rel in candidates:
        if (root / rel).exists():
            result.entry_flows.append(
                {
                    "entry": rel,
                    "kind": "process_entry",
                    "confidence": 0.85,
                    "note": "Common application entry candidate",
                }
            )


def _knowledge_facts(result: CodeIntelligenceResult) -> list[dict]:
    facts: list[dict] = []
    class_count = sum(1 for s in result.symbols if s.kind == "class")
    fn_count = sum(1 for s in result.symbols if s.kind in {"function", "method"})
    if result.symbols:
        facts.append(
            {
                "memory_layer": "architecture",
                "category": "code_symbols",
                "kind": "fact",
                "title": f"Extracted {len(result.symbols)} code symbols",
                "content": f"Found {class_count} classes and {fn_count} functions/methods via AST/static parse.",
                "confidence": 0.92,
                "source_type": "file",
                "source_path": ".",
                "evidence": {
                    "symbols": len(result.symbols),
                    "classes": class_count,
                    "functions": fn_count,
                },
            }
        )
    if result.api_endpoints:
        sample = result.api_endpoints[:8]
        facts.append(
            {
                "memory_layer": "architecture",
                "category": "api",
                "kind": "fact",
                "title": f"Detected {len(result.api_endpoints)} API/page routes",
                "content": "Static analysis found HTTP/page routes in source.",
                "confidence": 0.88,
                "source_type": "file",
                "source_path": sample[0].source_path,
                "evidence": {
                    "endpoints": [
                        {"method": e.method, "path": e.path, "file": e.source_path}
                        for e in sample
                    ]
                },
            }
        )
    else:
        facts.append(
            {
                "memory_layer": "architecture",
                "category": "api",
                "kind": "unverified",
                "title": "No API routes detected yet",
                "content": "Static scanners did not find common route patterns. Needs deeper framework-specific analysis.",
                "confidence": 0.35,
                "source_type": "agent",
                "source_path": None,
                "evidence": {},
            }
        )

    # Hot modules by fan-in (imported name frequency is weak; use files with most outbound imports)
    outbound = defaultdict(int)
    for edge in result.import_edges:
        outbound[edge.from_path] += 1
    hot = sorted(outbound.items(), key=lambda x: x[1], reverse=True)[:5]
    if hot:
        facts.append(
            {
                "memory_layer": "architecture",
                "category": "dependencies",
                "kind": "inference",
                "title": "Modules with highest outbound import activity",
                "content": "These files import many modules and may be orchestration/hub points.",
                "confidence": 0.55,
                "source_type": "agent",
                "source_path": hot[0][0],
                "evidence": {"hot_modules": [{"path": p, "imports": n} for p, n in hot]},
            }
        )
    return facts


def analyze_codebase(workspace: Path) -> CodeIntelligenceResult:
    root = workspace.resolve()
    result = CodeIntelligenceResult()
    languages_seen: set[str] = set()
    for path in _iter_source_files(root):
        suffix = path.suffix.lower()
        language = EXT_TO_LANGUAGE.get(suffix, "Unknown")
        languages_seen.add(language)
        if suffix == ".py":
            _analyze_python(root, path, result)
        elif suffix in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}:
            _analyze_js_like(root, path, result)
        elif suffix == ".go":
            _analyze_go(root, path, result)
        elif language in _GENERIC_PATTERNS:
            _analyze_generic(root, path, language, result)
        elif suffix in {".h", ".hpp", ".hh"}:
            _analyze_generic(root, path, "C++", result)

    _build_entry_flows(root, result)
    result.facts = _knowledge_facts(result)
    if languages_seen:
        result.facts.insert(
            0,
            {
                "memory_layer": "architecture",
                "category": "language",
                "kind": "fact",
                "title": f"Deep analysis covered {len(languages_seen)} languages",
                "content": "Polyglot code intelligence scanned: " + ", ".join(sorted(languages_seen)),
                "confidence": 0.9,
                "source_type": "file",
                "source_path": ".",
                "evidence": {"languages": sorted(languages_seen)},
            },
        )
    result.stats = {
        "modules": len(result.modules),
        "symbols": len(result.symbols),
        "imports": len(result.import_edges),
        "api_endpoints": len(result.api_endpoints),
        "entry_flows": len(result.entry_flows),
        "languages_analyzed": sorted(languages_seen),
    }

    # Truncate heavy arrays for storage/API payloads
    result.symbols = result.symbols[:300]
    result.import_edges = result.import_edges[:400]
    result.api_endpoints = result.api_endpoints[:200]
    result.modules = result.modules[:200]
    return result


def dump_package_scripts(workspace: Path) -> dict | None:
    pkg = workspace / "package.json"
    if not pkg.exists():
        return None
    try:
        return json.loads(pkg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
