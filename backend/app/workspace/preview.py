"""Live preview for workspaces — static http.server OR npm/vite/next dev."""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from app.workspace.files import project_root

_LOCK = threading.Lock()
_SERVERS: dict[str, "PreviewServer"] = {}
_STARTING: set[str] = set()

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
    command: str = ""


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


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.35)
        try:
            sock.connect(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _npm_cmd() -> str | None:
    return shutil.which("npm.cmd") or shutil.which("npm")


def _read_package_json(root: Path) -> dict[str, Any] | None:
    path = root / "package.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _pick_dev_plan(workspace: Path) -> dict[str, Any]:
    """Prefer Vite/Next/npm dev when package.json has a suitable script."""
    root = project_root(workspace)
    candidates = [root, root / "frontend", root / "web", root / "app", root / "client"]
    for base in candidates:
        pkg = _read_package_json(base)
        if not pkg:
            continue
        scripts = pkg.get("scripts") if isinstance(pkg.get("scripts"), dict) else {}
        deps = {}
        if isinstance(pkg.get("dependencies"), dict):
            deps.update(pkg["dependencies"])
        if isinstance(pkg.get("devDependencies"), dict):
            deps.update(pkg["devDependencies"])
        script_name = None
        for name in ("dev", "preview", "start"):
            if name in scripts and str(scripts[name]).strip():
                script_name = name
                break
        if not script_name:
            continue
        npm = _npm_cmd()
        if not npm:
            continue
        kind = "npm"
        if "next" in deps:
            kind = "next"
        elif "vite" in deps:
            kind = "vite"
        elif "react-scripts" in deps:
            kind = "cra"
        return {
            "kind": kind,
            "cwd": base,
            "script": script_name,
            "npm": npm,
            "has_node_modules": (base / "node_modules").is_dir(),
        }

    # Static fallback
    for html in (
        root / "index.html",
        root / "frontend" / "index.html",
        root / "public" / "index.html",
        root / "app" / "index.html",
    ):
        if html.is_file():
            return {"kind": "static", "cwd": html.parent}
    return {"kind": "static", "cwd": root}


def _status_unlocked(key: str) -> dict[str, Any]:
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
        "command": srv.command,
        "started_at": srv.started_at,
    }


def preview_status(project_id: UUID | str) -> dict[str, Any]:
    key = str(project_id)
    with _LOCK:
        return _status_unlocked(key)


def stop_preview(project_id: UUID | str) -> dict[str, Any]:
    key = str(project_id)
    with _LOCK:
        srv = _SERVERS.pop(key, None)
        _STARTING.discard(key)
    if not srv:
        return {"ok": True, "running": False, "project_id": key}
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(srv.pid), "/T", "/F"],
                capture_output=True,
                check=False,
            )
        else:
            srv.process.terminate()
            try:
                srv.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                srv.process.kill()
    except OSError:
        pass
    return {"ok": True, "running": False, "project_id": key, "stopped_pid": srv.pid}


def _wait_http(url: str, *, timeout: float = 25.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                if 200 <= int(resp.status) < 500:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.4)
    return False


def verify_preview(project_id: UUID | str) -> dict[str, Any]:
    """HTTP-check the running preview — feeds post-build learning."""
    status = preview_status(project_id)
    if not status.get("running") or not status.get("url"):
        return {"ok": False, "running": False, "error": "preview_not_running", **status}
    url = str(status["url"])
    try:
        with urllib.request.urlopen(url, timeout=4) as resp:
            body = resp.read(8000)
            code = int(resp.status)
            text = body.decode("utf-8", errors="ignore")
            return {
                "ok": 200 <= code < 400,
                "running": True,
                "url": url,
                "status_code": code,
                "kind": status.get("kind"),
                "bytes": len(body),
                "has_html": bool(re.search(r"<html|<!doctype", text, re.I)),
                "snippet": text[:180],
            }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "running": True,
            "url": url,
            "kind": status.get("kind"),
            "error": str(exc)[:300],
        }


def start_preview(project_id: UUID | str, workspace_path: str | Path) -> dict[str, Any]:
    key = str(project_id)
    workspace = Path(workspace_path)
    if not workspace.exists():
        return {"ok": False, "error": "workspace_missing", "project_id": key}

    plan = _pick_dev_plan(workspace)

    with _LOCK:
        existing = _status_unlocked(key)
        if existing.get("running"):
            return {"ok": True, **existing}
        if key in _STARTING:
            return {"ok": False, "error": "preview_starting", "project_id": key}
        _STARTING.add(key)

    env = os.environ.copy()
    env["SPIXA_PREVIEW"] = "1"
    env["BROWSER"] = "none"
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

    try:
        if plan.get("kind") != "static":
            return _start_npm_preview(key, workspace, plan, env, creationflags)
        return _start_static_preview(key, workspace, plan, env, creationflags)
    finally:
        with _LOCK:
            _STARTING.discard(key)


def _register(key: str, srv: PreviewServer) -> dict[str, Any]:
    with _LOCK:
        old = _SERVERS.pop(key, None)
        _SERVERS[key] = srv
        _STARTING.discard(key)
    if old and old.process.poll() is None and int(old.pid) != int(srv.pid):
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/PID", str(old.pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                )
            else:
                old.process.terminate()
        except OSError:
            pass
    hint = (
        "Vite/Next hot reload — edit and watch the preview update."
        if srv.kind in {"vite", "next", "npm", "cra"}
        else "Static preview — refresh after file changes."
    )
    return {
        "ok": True,
        "running": True,
        "project_id": key,
        "url": srv.url,
        "port": srv.port,
        "serve_root": srv.serve_root,
        "pid": srv.pid,
        "kind": srv.kind,
        "command": srv.command,
        "hint": hint,
    }


def _start_static_preview(
    key: str,
    workspace: Path,
    plan: dict[str, Any],
    env: dict[str, str],
    creationflags: int,
) -> dict[str, Any]:
    serve_dir = Path(plan["cwd"])
    last_error = "no_free_port"
    for _attempt in range(5):
        port = _free_port()
        if port is None:
            break
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
        time.sleep(0.35)
        if proc.poll() is not None:
            last_error = "preview_exited"
            continue
        url = f"http://127.0.0.1:{port}/"
        srv = PreviewServer(
            project_id=key,
            workspace=str(workspace),
            serve_root=str(serve_dir),
            port=port,
            url=url,
            pid=int(proc.pid),
            process=proc,
            kind="static",
            command=f"python -m http.server {port}",
        )
        return _register(key, srv)
    return {"ok": False, "error": last_error, "project_id": key}


def _start_npm_preview(
    key: str,
    workspace: Path,
    plan: dict[str, Any],
    env: dict[str, str],
    creationflags: int,
) -> dict[str, Any]:
    cwd = Path(plan["cwd"])
    npm = str(plan["npm"])
    script = str(plan["script"])
    kind = str(plan["kind"])

    if not plan.get("has_node_modules"):
        # Best-effort install (bounded)
        try:
            install = subprocess.run(
                [npm, "install", "--no-fund", "--no-audit"],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=180,
                env=env,
            )
            if install.returncode != 0:
                return {
                    "ok": False,
                    "error": "npm_install_failed",
                    "detail": (install.stderr or install.stdout or "")[:500],
                    "project_id": key,
                    "hint": "Run npm install in the project, then retry Preview.",
                }
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "error": f"npm_install:{exc}", "project_id": key}

    port = _free_port()
    if port is None:
        return {"ok": False, "error": "no_free_port", "project_id": key}

    env = dict(env)
    env["PORT"] = str(port)
    env["HOST"] = "127.0.0.1"
    # Vite
    cmd = [npm, "run", script, "--", "--host", "127.0.0.1", "--port", str(port)]
    if kind == "next":
        cmd = [npm, "run", script, "--", "-H", "127.0.0.1", "-p", str(port)]
    elif kind == "cra":
        cmd = [npm, "run", script]
        env["PORT"] = str(port)

    log_path = cwd / ".spixa" / "preview.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_fh = log_path.open("ab")
    except OSError:
        log_fh = subprocess.DEVNULL

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            env=env,
            creationflags=creationflags,
        )
    except OSError as exc:
        if hasattr(log_fh, "close"):
            try:
                log_fh.close()
            except Exception:  # noqa: BLE001
                pass
        return {"ok": False, "error": str(exc), "project_id": key}

    url = f"http://127.0.0.1:{port}/"
    # Wait until port accepts connections or process dies
    ready = False
    for _ in range(60):
        if proc.poll() is not None:
            break
        if _port_open(port) or _wait_http(url, timeout=0.8):
            ready = True
            break
        time.sleep(0.35)

    if not ready:
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                )
            else:
                proc.kill()
        except OSError:
            pass
        return {
            "ok": False,
            "error": "dev_server_timeout",
            "project_id": key,
            "kind": kind,
            "command": " ".join(cmd),
            "log": str(log_path),
            "hint": "Dev server did not become ready — check .spixa/preview.log",
        }

    srv = PreviewServer(
        project_id=key,
        workspace=str(workspace),
        serve_root=str(cwd),
        port=port,
        url=url,
        pid=int(proc.pid),
        process=proc,
        kind=kind,
        command=" ".join(cmd),
    )
    return _register(key, srv)
