"""Run shell commands inside a project workspace (local IDE terminal)."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

from app.security.isolation import assert_path_inside_workspace
from app.workspace.files import project_root

MAX_OUTPUT = 120_000
DEFAULT_TIMEOUT = 45
MAX_TIMEOUT = 120

_BLOCKED = re.compile(
    r"(?i)(\brm\s+-rf\s+/|\bformat\s+[a-z]:|"
    r"\bdel\s+/[sf]\s+|shutdown\b|reboot\b|"
    r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;|"
    r"\bmkfs\b|\bdd\s+if=|\bcurl\s+[^\n]*\|\s*(ba)?sh\b)",
)


def run_workspace_command(
    workspace_path: str | Path,
    command: str,
    *,
    cwd_rel: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    cmd = (command or "").strip()
    if not cmd:
        return {"ok": False, "error": "empty_command"}
    if len(cmd) > 4000:
        return {"ok": False, "error": "command_too_long"}
    if _BLOCKED.search(cmd):
        return {"ok": False, "error": "command_blocked"}

    root = project_root(workspace_path)
    workspace = Path(workspace_path)
    if not root.exists():
        return {"ok": False, "error": "workspace_missing"}

    cwd = root
    if cwd_rel:
        rel = cwd_rel.replace("\\", "/").lstrip("/")
        if ".." in Path(rel).parts:
            return {"ok": False, "error": "path_escape"}
        candidate = (root / rel).resolve()
        try:
            assert_path_inside_workspace(workspace, candidate)
        except PermissionError:
            return {"ok": False, "error": "cwd_outside_workspace"}
        if candidate.is_dir():
            cwd = candidate

    timeout = max(1, min(int(timeout or DEFAULT_TIMEOUT), MAX_TIMEOUT))
    env = os.environ.copy()
    env["SPIXA_IDE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"

    try:
        completed = subprocess.run(
            cmd,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or "") + (exc.stderr or "")
        return {
            "ok": False,
            "error": "timeout",
            "exit_code": None,
            "stdout": str(out)[:MAX_OUTPUT],
            "stderr": f"Command timed out after {timeout}s",
            "cwd": str(cwd),
            "command": cmd,
        }
    except OSError as exc:
        return {"ok": False, "error": str(exc), "command": cmd, "cwd": str(cwd)}

    stdout = (completed.stdout or "")[:MAX_OUTPUT]
    stderr = (completed.stderr or "")[:MAX_OUTPUT]
    return {
        "ok": completed.returncode == 0,
        "exit_code": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "cwd": str(cwd),
        "command": cmd,
        "truncated": len(completed.stdout or "") > MAX_OUTPUT or len(completed.stderr or "") > MAX_OUTPUT,
    }
