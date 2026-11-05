from pathlib import Path

from app.config import Settings
from app.security.isolation import bind_local_folder, default_user_projects_root


def test_bind_local_folder_points_at_user_path(tmp_path: Path):
    folder = tmp_path / "on-desktop"
    folder.mkdir()
    (folder / "a.py").write_text("x=1\n", encoding="utf-8")
    settings = Settings(workspaces_root=tmp_path / "ws")
    ctx = bind_local_folder(name="Demo", local_path=folder, settings=settings, slug="demo-bind")
    assert ctx.workspace_path.resolve() == folder.resolve()
    assert (ctx.workspace_path / "a.py").exists()


def test_default_user_projects_root_exists():
    root = default_user_projects_root()
    assert root.exists()
    assert root.is_dir()
