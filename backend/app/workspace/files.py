"""Project workspace file IO for the Spixa web IDE (isolated per project)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.security.isolation import assert_path_inside_workspace

SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", ".next", "dist", "build", ".tox"}
MAX_READ_CHARS = 400_000
MAX_WRITE_CHARS = 400_000
MAX_TREE_ENTRIES = 2_000


def project_root(workspace_path: str | Path) -> Path:
    workspace = Path(workspace_path)
    repo = workspace / "repo"
    return repo if repo.exists() else workspace


def _safe_target(workspace: Path, relative: str) -> Path:
    rel = (relative or ".").replace("\\", "/").lstrip("/")
    if ".." in Path(rel).parts:
        raise PermissionError("Path escape rejected")
    root = project_root(workspace)
    return assert_path_inside_workspace(workspace, (root / rel).resolve())


def build_tree(workspace_path: str | Path, *, limit: int = MAX_TREE_ENTRIES) -> dict[str, Any]:
    root = project_root(workspace_path)
    workspace = Path(workspace_path)
    if not root.exists():
        return {"root": str(root), "entries": [], "truncated": False}

    entries: list[dict[str, Any]] = []
    truncated = False

    def walk(dir_path: Path, prefix: str = "") -> None:
        nonlocal truncated
        if truncated:
            return
        try:
            children = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return
        for child in children:
            if child.name in SKIP_DIRS or child.name.startswith(".evolve"):
                continue
            rel = f"{prefix}/{child.name}".lstrip("/") if prefix else child.name
            rel = rel.replace("\\", "/")
            try:
                assert_path_inside_workspace(workspace, child.resolve())
            except PermissionError:
                continue
            if child.is_dir():
                entries.append({"path": rel, "name": child.name, "type": "dir"})
                if len(entries) >= limit:
                    truncated = True
                    return
                walk(child, rel)
            elif child.is_file():
                entries.append(
                    {
                        "path": rel,
                        "name": child.name,
                        "type": "file",
                        "size": child.stat().st_size,
                    }
                )
                if len(entries) >= limit:
                    truncated = True
                    return

    walk(root)
    return {
        "root": str(root),
        "entries": entries,
        "count": len(entries),
        "truncated": truncated,
    }


_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico", ".avif"}
_PDF_EXT = {".pdf"}
_AUDIO_EXT = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"}
_VIDEO_EXT = {".mp4", ".webm", ".mov", ".mkv", ".avi"}
_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".bmp": "image/bmp",
    ".ico": "image/x-icon",
    ".avif": "image/avif",
    ".pdf": "application/pdf",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".m4a": "audio/mp4",
    ".flac": "audio/flac",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
}


def _classify(path: Path, raw: bytes) -> str:
    ext = path.suffix.lower()
    if ext in _IMAGE_EXT:
        return "image"
    if ext in _PDF_EXT:
        return "pdf"
    if ext in _AUDIO_EXT:
        return "audio"
    if ext in _VIDEO_EXT:
        return "video"
    if b"\x00" in raw[:8000]:
        return "binary"
    return "text"


def resolve_workspace_file(workspace_path: str | Path, relative: str) -> Path:
    return _safe_target(Path(workspace_path), relative)


def mime_for_path(path: Path) -> str:
    return _MIME.get(path.suffix.lower(), "application/octet-stream")


def read_text_file(workspace_path: str | Path, relative: str) -> dict[str, Any]:
    target = _safe_target(Path(workspace_path), relative)
    if not target.exists() or not target.is_file():
        return {"ok": False, "error": "file_not_found", "path": relative}
    raw = target.read_bytes()
    kind = _classify(target, raw)
    rel = relative.replace("\\", "/")
    base = {
        "ok": True,
        "path": rel,
        "kind": kind,
        "size": len(raw),
        "mime": mime_for_path(target),
        "name": target.name,
    }
    if kind != "text":
        return {
            **base,
            "content": "",
            "truncated": False,
            "chars": 0,
            "previewable": kind in {"image", "pdf", "audio", "video"},
            "error": None,
        }
    text = raw.decode("utf-8", errors="replace")
    truncated = len(text) > MAX_READ_CHARS
    return {
        **base,
        "content": text[:MAX_READ_CHARS],
        "truncated": truncated,
        "chars": len(text),
        "previewable": False,
    }


def write_text_file(workspace_path: str | Path, relative: str, content: str) -> dict[str, Any]:
    if content is None:
        return {"ok": False, "error": "empty_content"}
    if len(content) > MAX_WRITE_CHARS:
        return {"ok": False, "error": "too_large"}
    target = _safe_target(Path(workspace_path), relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")
    return {
        "ok": True,
        "path": relative.replace("\\", "/"),
        "chars": len(content),
        "size": target.stat().st_size,
    }


def create_entry(
    workspace_path: str | Path,
    relative: str,
    *,
    kind: str = "file",
    content: str = "",
) -> dict[str, Any]:
    target = _safe_target(Path(workspace_path), relative)
    if target.exists():
        return {"ok": False, "error": "already_exists", "path": relative}
    if kind == "dir":
        target.mkdir(parents=True, exist_ok=False)
        return {"ok": True, "path": relative.replace("\\", "/"), "type": "dir"}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"ok": True, "path": relative.replace("\\", "/"), "type": "file"}
