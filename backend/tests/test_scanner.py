from pathlib import Path

from app.intelligence.scanner import scan_workspace


def test_scan_detects_python_and_fastapi(tmp_path: Path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("print('hi')", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="demo"\ndependencies=["fastapi"]\n',
        encoding="utf-8",
    )

    result = scan_workspace(tmp_path)
    assert any(lang["name"] == "Python" for lang in result.languages)
    assert "FastAPI" in result.frameworks or "Python" in result.frameworks
    assert "app/main.py" in result.entry_points or "main.py" in [
        Path(p).name for p in result.entry_points
    ]
    assert any(f["kind"] == "fact" for f in result.facts)


def test_scan_ignores_node_modules(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.ts").write_text(" consoles.log(1)", encoding="utf-8")
    nm = tmp_path / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    (nm / "index.js").write_text("module.exports=1", encoding="utf-8")

    result = scan_workspace(tmp_path)
    assert result.file_stats["total_files"] == 1
