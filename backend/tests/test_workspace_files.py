from pathlib import Path

from app.workspace.files import build_tree, create_entry, read_text_file, write_text_file


def test_tree_read_write_roundtrip(tmp_path: Path):
    ws = tmp_path / "proj"
    repo = ws / "repo"
    repo.mkdir(parents=True)
    (repo / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "util.py").write_text("x=1\n", encoding="utf-8")

    tree = build_tree(ws)
    paths = {e["path"] for e in tree["entries"]}
    assert "main.py" in paths
    assert "src" in paths
    assert "src/util.py" in paths

    read = read_text_file(ws, "main.py")
    assert read["ok"] is True
    assert "print" in read["content"]

    written = write_text_file(ws, "main.py", "print('spixa')\n")
    assert written["ok"] is True
    assert read_text_file(ws, "main.py")["content"].startswith("print('spixa')")

    created = create_entry(ws, "notes.md", kind="file", content="# Spixa\n")
    assert created["ok"] is True
    assert read_text_file(ws, "notes.md")["ok"] is True


def test_path_escape_rejected(tmp_path: Path):
    ws = tmp_path / "proj"
    (ws / "repo").mkdir(parents=True)
    try:
        read_text_file(ws, "../outside.txt")
        assert False, "expected PermissionError"
    except PermissionError:
        pass
