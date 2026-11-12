"""Live preview server for project workspaces (static site while building)."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from app.workspace.files import project_root

_LOCK = threading.Lock()
_SERVERS: dict[str, "PreviewServer"] = {}

PORT_MIN = 5173
PORT_MAX = 5299


@dataclass
class PreviewServer:
    project_id: str
    workspace: str
    serve_root: str
    port: int
    url: str
    pid: int
    process: subprocess.Popen[Any] = field(repr=False)
    started_at: float = field(default_factory=time.time)
    kind: str = "static"


def _free_port() -> int | None:
    for port in range(PORT_MIN, PORT_MAX + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    return None


def _pick_serve_root(workspace: Path) -> tuple[Path, str]:
    root = project_root(workspace)
    candidates = [
        root / "index.html",
        root / "frontend" / "index.html",
        root / "public" / "index.html",
        root / "app" / "index.html",
    ]
    for html in candidates:
        if html.is_file():
            return html.parent, "static"
    # Fallback: serve workspace root even without index.html
    return root, "static"


def preview_status(project_id: UUID | str) -> dict[str, Any]:
    key = str(project_id)
    with _LOCK:
        srv = _SERVERS.get(key)
        if not srv:
            return {"running": False, "project_id": key}
        alive = srv.process.poll() is None
        if not alive:
            _SERVERS.pop(key, None)
            return {"running": False, "project_id": key, "stopped": True}
        return {
            "running": True,
            "project_id": key,
            "url": srv.url,
            "port": srv.port,
            "serve_root": srv.serve_root,
            "pid": srv.pid,
            "kind": srv.kind,
            "started_at": srv.started_at,
        }


def stop_preview(project_id: UUID | str) -> dict[str, Any]:
    key = str(project_id)
    with _LOCK:
        srv = _SERVERS.pop(key, None)
    if not srv:
        return {"ok": True, "running": False, "project_id": key}
    try:
        srv.process.terminate()
        try:
            srv.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            srv.process.kill()
    except OSError:
        pass
    return {"ok": True, "running": False, "project_id": key, "stopped_pid": srv.pid}


def start_preview(project_id: UUID | str, workspace_path: str | Path) -> dict[str, Any]:
    key = str(project_id)
    existing = preview_status(key)
    if existing.get("running"):
        return {"ok": True, **existing}

    workspace = Path(workspace_path)
    if not workspace.exists():
        return {"ok": False, "error": "workspace_missing", "project_id": key}

    serve_dir, kind = _pick_serve_root(workspace)
    port = _free_port()
    if port is None:
        return {"ok": False, "error": "no_free_port", "project_id": key}

    env = os.environ.copy()
    env["SPIXA_PREVIEW"] = "1"
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
            cwd=str(serve_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            creationflags=creationflags,
        )
    except OSError as exc:
        return {"ok": False, "error": str(exc), "project_id": key}

    # Brief settle — fail fast if process died
    time.sleep(0.35)
    if proc.poll() is not None:
        return {"ok": False, "error": "preview_exited", "project_id": key}

    url = f"http://127.0.0.1:{port}/"
    srv = PreviewServer(
        project_id=key,
        workspace=str(workspace),
        serve_root=str(serve_dir),
        port=port,
        url=url,
        pid=int(proc.pid),
        process=proc,
        kind=kind,
    )
    with _LOCK:
        # Stop any race double-start
        old = _SERVERS.pop(key, None)
        if old and old.process.poll() is None:
            try:
                old.process.terminate()
            except OSError:
                pass
        _SERVERS[key] = srv

    return {
        "ok": True,
        "running": True,
        "project_id": key,
        "url": url,
        "port": port,
        "serve_root": str(serve_dir),
        "pid": srv.pid,
        "kind": kind,
        "hint": "Open this URL while building — refresh after file changes.",
    }
