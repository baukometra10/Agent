"""Polyglot language pack — expandable map of languages Evolve understands."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguagePack:
    name: str
    extensions: tuple[str, ...]
    family: str  # systems|managed|scripting|web|data|mobile|functional|markup
    deep_analysis: str  # ast|regex|treesitter|pending
    notes: str = ""


LANGUAGE_PACKS: tuple[LanguagePack, ...] = (
    LanguagePack("Python", (".py", ".pyi"), "scripting", "ast", "Primary deep AST"),
    LanguagePack("JavaScript", (".js", ".mjs", ".cjs"), "web", "regex"),
    LanguagePack("TypeScript", (".ts", ".tsx"), "web", "regex"),
    LanguagePack("JSX", (".jsx",), "web", "regex"),
    LanguagePack("Go", (".go",), "systems", "regex"),
    LanguagePack("Rust", (".rs",), "systems", "regex"),
    LanguagePack("Java", (".java",), "managed", "regex"),
    LanguagePack("Kotlin", (".kt", ".kts"), "managed", "regex"),
    LanguagePack("C#", (".cs",), "managed", "regex"),
    LanguagePack("C", (".c", ".h"), "systems", "regex"),
    LanguagePack("C++", (".cpp", ".cc", ".cxx", ".hpp", ".hh"), "systems", "regex"),
    LanguagePack("Ruby", (".rb",), "scripting", "regex"),
    LanguagePack("PHP", (".php",), "web", "regex"),
    LanguagePack("Swift", (".swift",), "mobile", "regex"),
    LanguagePack("Scala", (".scala", ".sc"), "functional", "regex"),
    LanguagePack("Dart", (".dart",), "mobile", "regex"),
    LanguagePack("Elixir", (".ex", ".exs"), "functional", "regex"),
    LanguagePack("Clojure", (".clj", ".cljs", ".cljc"), "functional", "regex"),
    LanguagePack("Haskell", (".hs",), "functional", "pending"),
    LanguagePack("Lua", (".lua",), "scripting", "regex"),
    LanguagePack("R", (".r", ".R"), "data", "pending"),
    LanguagePack("Shell", (".sh", ".bash", ".zsh"), "scripting", "regex"),
    LanguagePack("PowerShell", (".ps1", ".psm1"), "scripting", "regex"),
    LanguagePack("SQL", (".sql",), "data", "regex"),
    LanguagePack("HTML", (".html", ".htm"), "markup", "regex"),
    LanguagePack("CSS", (".css", ".scss", ".sass", ".less"), "markup", "regex"),
    LanguagePack("Vue", (".vue",), "web", "regex"),
    LanguagePack("Svelte", (".svelte",), "web", "regex"),
    LanguagePack("Protobuf", (".proto",), "data", "regex"),
    LanguagePack("Terraform", (".tf", ".tfvars"), "systems", "regex"),
    LanguagePack("YAML", (".yml", ".yaml"), "markup", "regex"),
    LanguagePack("JSON", (".json",), "markup", "regex"),
    LanguagePack("TOML", (".toml",), "markup", "regex"),
    LanguagePack("Markdown", (".md", ".mdx"), "markup", "regex"),
    LanguagePack("Dockerfile", (".dockerfile",), "systems", "regex"),
    # Phase 37 — expanded polyglot coverage
    LanguagePack("Zig", (".zig",), "systems", "regex"),
    LanguagePack("Nim", (".nim",), "systems", "regex"),
    LanguagePack("OCaml", (".ml", ".mli"), "functional", "pending"),
    LanguagePack("F#", (".fs", ".fsi", ".fsx"), "functional", "regex"),
    LanguagePack("Solidity", (".sol",), "systems", "regex"),
    LanguagePack("GraphQL", (".graphql", ".gql"), "data", "regex"),
    LanguagePack("Prisma", (".prisma",), "data", "regex"),
    LanguagePack("Erlang", (".erl", ".hrl"), "functional", "pending"),
    LanguagePack("Julia", (".jl",), "data", "pending"),
    LanguagePack("Groovy", (".groovy",), "managed", "regex"),
    LanguagePack("Objective-C", (".m", ".mm"), "mobile", "regex"),
    LanguagePack("Assembly", (".asm", ".s"), "systems", "pending"),
    LanguagePack("Makefile", (".mk",), "systems", "regex", "Also matches files named Makefile"),
)


EXT_TO_LANGUAGE: dict[str, str] = {}
for pack in LANGUAGE_PACKS:
    for ext in pack.extensions:
        EXT_TO_LANGUAGE[ext] = pack.name


DEEP_SOURCE_EXTS = {
    ext
    for pack in LANGUAGE_PACKS
    if pack.deep_analysis in {"ast", "regex", "treesitter"}
    for ext in pack.extensions
    if pack.family not in {"markup"} or pack.name in {"Vue", "Svelte", "HTML"}
}


def language_catalog() -> list[dict]:
    return [
        {
            "name": p.name,
            "extensions": list(p.extensions),
            "family": p.family,
            "deep_analysis": p.deep_analysis,
            "notes": p.notes,
        }
        for p in LANGUAGE_PACKS
    ]
