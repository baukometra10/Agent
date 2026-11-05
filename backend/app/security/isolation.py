"""Per-project isolation. Projects must never share workspaces or execution context."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from slugify import slugify

from app.config import Settings


_SAFE_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class IsolationContext:
    project_slug: str
    namespace: str
    workspace_path: Path
    allow_code_execution: bool
    network_disabled: bool


def make_namespace(slug: str) -> str:
    digest = hashlib.sha256(slug.encode("utf-8")).hexdigest()[:12]
    return f"spixa-{slug}-{digest}"


def ensure_project_isolation(
    *,
    name: str,
    settings: Settings,
    slug: str | None = None,
) -> IsolationContext:
    project_slug = slug or slugify(name, max_length=80)
    if not _SAFE_SLUG.match(project_slug):
        raise ValueError(f"Unsafe project slug: {project_slug}")

    root = settings.workspaces_root.resolve()
    root.mkdir(parents=True, exist_ok=True)

    namespace = make_namespace(project_slug)
    workspace = root / project_slug
    workspace.mkdir(parents=True, exist_ok=True)

    # Prevent path escape outside workspaces root
    if not str(workspace.resolve()).startswith(str(root)):
        raise PermissionError("Workspace path escapes isolation root")

    return IsolationContext(
        project_slug=project_slug,
        namespace=namespace,
        workspace_path=workspace,
        allow_code_execution=settings.allow_untrusted_code_execution,
        network_disabled=settings.sandbox_network_disabled,
    )


_BLOCKED_ROOT_NAMES = {
    "windows",
    "system32",
    "program files",
    "program files (x86)",
    "$recycle.bin",
}


def default_user_projects_root() -> Path:
    """Prefer Desktop so the user always finds generated code on their machine."""
    home = Path.home()
    candidates = [
        home / "Desktop",
        home / "OneDrive" / "Desktop",
        home / "Documents" / "SpixaProjects",
    ]
    for path in candidates:
        if path.exists() and path.is_dir():
            return path
    fallback = home / "SpixaProjects"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def bind_local_folder(
    *,
    name: str,
    local_path: str | Path,
    settings: Settings,
    slug: str | None = None,
    create_if_missing: bool = False,
) -> IsolationContext:
    """Point workspace_path at a real folder on the user's disk (Cursor-like).

    Knowledge/memory stay namespaced in the DB; files live on the user's machine.
    """
    project_slug = slug or slugify(name, max_length=80)
    if not _SAFE_SLUG.match(project_slug):
        raise ValueError(f"Unsafe project slug: {project_slug}")

    source = Path(local_path).expanduser()
    if create_if_missing and not source.exists():
        source.mkdir(parents=True, exist_ok=True)
    source = source.resolve()
    if not source.exists():
        raise FileNotFoundError(f"Folder not found: {source}")
    if not source.is_dir():
        raise ValueError(f"Path is not a folder: {source}")

    # Soft safety: refuse obvious OS roots / system dirs
    parts_l = {p.lower() for p in source.parts}
    if parts_l & _BLOCKED_ROOT_NAMES:
        raise PermissionError(f"Refusing to bind system path: {source}")
    if source == source.anchor or source == Path(source.anchor):
        raise PermissionError("Refusing to bind drive root")

    return IsolationContext(
        project_slug=project_slug,
        namespace=make_namespace(project_slug),
        workspace_path=source,
        allow_code_execution=settings.allow_untrusted_code_execution,
        network_disabled=settings.sandbox_network_disabled,
    )


def assert_path_inside_workspace(workspace: Path, target: Path) -> Path:
    resolved = target.resolve()
    if not str(resolved).startswith(str(workspace.resolve())):
        raise PermissionError(f"Path outside project workspace: {target}")
    return resolved
