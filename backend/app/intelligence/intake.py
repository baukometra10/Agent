"""Project intake from Git or local paths.

Local folders default to bind mode: workspace_path is the user's real folder.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from git import Repo

from app.security.isolation import IsolationContext, assert_path_inside_workspace


def ingest_git_repo(isolation: IsolationContext, git_url: str, *, branch: str | None = None) -> Path:
    target = isolation.workspace_path / "repo"
    if target.exists():
        shutil.rmtree(target)
    kwargs = {"url": git_url, "to_path": str(target)}
    if branch:
        kwargs["branch"] = branch
    Repo.clone_from(**kwargs)
    return assert_path_inside_workspace(isolation.workspace_path, target)


def ingest_local_path(
    isolation: IsolationContext,
    source: Path,
    *,
    bind: bool = True,
) -> Path:
    """Attach a local folder.

    bind=True (default): workspace IS the user folder — writes go to their disk.
    bind=False: legacy copy into isolated workspace/repo.
    """
    source = source.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"Source path not found: {source}")

    if bind:
        root = isolation.workspace_path.resolve()
        if root != source and not str(source).startswith(str(root)):
            raise ValueError(
                f"Bind mismatch: workspace={root} source={source}. "
                "Use bind_local_folder so workspace_path equals the user folder."
            )
        return assert_path_inside_workspace(isolation.workspace_path, root)

    target = isolation.workspace_path / "repo"
    if target.exists():
        shutil.rmtree(target)

    if source.is_dir():
        shutil.copytree(
            source,
            target,
            ignore=shutil.ignore_patterns(
                ".git",
                "node_modules",
                ".venv",
                "venv",
                "__pycache__",
                ".next",
                "dist",
                "build",
            ),
        )
    else:
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target / source.name)

    return assert_path_inside_workspace(isolation.workspace_path, target)
