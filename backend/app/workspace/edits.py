"""Parse agent replies for file edits (shared with IDE apply flow)."""

from __future__ import annotations

import re
from typing import Any


def parse_agent_edits(reply: str) -> list[dict[str, str]]:
    edits: list[dict[str, str]] = []
    for m in re.finditer(
        r"<<<SPIXA_EDIT\s+([^\s>]+)\s*>>>\r?\n?([\s\S]*?)<<<END_SPIXA_EDIT>>>",
        reply,
        flags=re.I,
    ):
        path = m.group(1).replace("\\", "/")
        if path.lower() == "spixa_edit":
            continue
        edits.append({"path": path, "content": m.group(2).replace("\r\n", "\n")})

    for m in re.finditer(r"```([^\n`]*)\r?\n([\s\S]*?)```", reply):
        header = m.group(1).strip()
        body = m.group(2).replace("\r\n", "\n")
        if not header:
            continue
        parts = header.split()
        file_path = ""
        if len(parts) >= 2 and ("/" in parts[1] or "." in parts[1]):
            file_path = parts[1]
        elif "." in parts[0] or "/" in parts[0]:
            file_path = parts[0]
        if not file_path or len(file_path) > 240:
            continue
        if not re.match(r"^[A-Za-z0-9_./\\-]+$", file_path):
            continue
        edits.append({"path": file_path.replace("\\", "/"), "content": body})

    # Markdown heading dumps: # README.md\n...
    current: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal current, buf
        if current and "".join(buf).strip():
            edits.append({"path": current, "content": "\n".join(buf).replace("\r\n", "\n")})
        current = None
        buf = []

    junk = re.compile(r"^#\s*(spixa_edit|end_spixa_edit)\s*$", re.I)
    heading = re.compile(r"^#\s*([A-Za-z0-9_./\\-]+\.[A-Za-z0-9]{1,12})\s*$")
    for line in (reply or "").splitlines():
        if junk.match(line.strip()):
            flush()
            continue
        hm = heading.match(line.strip())
        if hm:
            flush()
            current = hm.group(1).replace("\\", "/")
            continue
        if current is not None:
            buf.append(line)
    flush()

    merged: dict[str, dict[str, str]] = {}
    for e in edits:
        if not str(e.get("content") or "").strip():
            continue
        merged[e["path"]] = e
    return list(merged.values())


def apply_edits_to_workspace(
    workspace_path: str,
    edits: list[dict[str, Any]],
    *,
    record_maturity: bool = True,
    maturity_source: str = "ide_apply",
) -> dict[str, Any]:
    from app.workspace.files import create_entry, write_text_file

    applied = []
    errors = []
    for e in edits:
        path = str(e.get("path") or "").replace("\\", "/").rstrip("/")
        content = str(e.get("content") or "")
        kind = str(e.get("kind") or "file")
        if not path:
            continue
        try:
            if kind == "dir":
                result = create_entry(workspace_path, path, kind="dir")
            else:
                result = write_text_file(workspace_path, path, content)
            if result.get("ok"):
                applied.append(path)
            else:
                # already_exists for dirs is fine during scaffolds
                if result.get("error") == "already_exists" and kind == "dir":
                    applied.append(path)
                else:
                    errors.append({"path": path, "error": result.get("error")})
        except PermissionError as exc:
            errors.append({"path": path, "error": str(exc)})
    result = {"ok": not errors, "applied": applied, "errors": errors}
    if record_maturity and edits:
        try:
            from app.maturity.scorecard import get_maturity_board

            get_maturity_board().record_task_outcome(
                specialty="coding",
                success=bool(result["ok"] and applied),
                source=maturity_source,
            )
        except Exception:  # noqa: BLE001
            pass
    return result
