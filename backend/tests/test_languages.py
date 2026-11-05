from pathlib import Path

from app.intelligence.code_intelligence import analyze_codebase
from app.intelligence.languages import language_catalog


def test_language_catalog_is_polyglot():
    names = {item["name"] for item in language_catalog()}
    for required in {"Python", "TypeScript", "Go", "Rust", "Java", "C#", "PHP", "Swift"}:
        assert required in names
    assert len(names) >= 25


def test_analyzes_rust_and_java_symbols(tmp_path: Path):
    (tmp_path / "lib.rs").write_text(
        "pub struct App {}\npub fn boot() {}\n",
        encoding="utf-8",
    )
    (tmp_path / "Hello.java").write_text(
        "public class Hello { public void run() {} }\n",
        encoding="utf-8",
    )
    result = analyze_codebase(tmp_path)
    langs = set(result.stats.get("languages_analyzed") or [])
    assert "Rust" in langs
    assert "Java" in langs
    assert any(s.name == "boot" for s in result.symbols)
    assert any(s.name == "Hello" for s in result.symbols)
