"""Promote approved مساعد الطيار sandbox experiments onto the real project.

Only called after human approve + execute. Copies allowlisted files from the
sandbox experiment into the project workspace (never the reverse).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from app.security.isolation import assert_path_inside_workspace

# Only these relative paths (or under evolve-sandbox/) may be promoted from a run
ALLOW_PREFIXES = (
    "evolve-sandbox/",
    ".gitignore",
    "tests/",
)

DENY_NAMES = {".evolve-sandbox", ".spixa-sandbox", ".env", ".git"}


def _allowed_rel(rel: str) -> bool:
    rel = rel.replace("\\", "/").lstrip("./")
    if any(part in DENY_NAMES for part in Path(rel).parts):
        return False
    if rel in {".gitignore"}:
        return True
    return any(rel.startswith(p) for p in ALLOW_PREFIXES)


def promote_sandbox_experiment(
    *,
    project_workspace: Path,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Copy sandbox experiment artifacts into the project workspace."""
    workspace = Path(project_workspace).resolve()
    manifest_path = evidence.get("sandbox_path") or evidence.get("manifest_path")
    diff_path = evidence.get("diff_path")
    if not manifest_path:
        # Infer from diff_path
        if diff_path:
            manifest_path = str(Path(diff_path).parent / "manifest.json")
        else:
            raise ValueError("Missing sandbox manifest in proposal evidence")

    manifest_file = Path(manifest_path)
    if not manifest_file.exists():
        raise FileNotFoundError(f"Sandbox manifest missing: {manifest_file}")

    from app.autopilot.markers import has_sandbox_marker

    sandbox_root = manifest_file.parent.parent  # .../evolve-sandbox/manifest.json → sandbox
    if not has_sandbox_marker(sandbox_root):
        raise PermissionError("Source is not a marked Spixa sandbox")

    try:
        meta = json.loads(manifest_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid sandbox manifest") from exc

    files = [f.get("path") for f in (meta.get("files") or []) if f.get("path")]
    # Prefer promoting useful artifacts; skip regenerating experiment.diff into root noise optionally
    copied: list[str] = []
    skipped: list[str] = []

    # Target: prefer repo/ if present
    target_root = workspace / "repo" if (workspace / "repo").exists() else workspace
    assert_path_inside_workspace(workspace, target_root)

    for rel in files:
        rel_n = str(rel).replace("\\", "/")
        if not _allowed_rel(rel_n):
            skipped.append(rel_n)
            continue
        if rel_n.endswith("experiment.diff"):
            # Keep diff under evolve-sandbox only
            pass
        src = sandbox_root / rel_n
        if not src.exists() or not src.is_file():
            skipped.append(rel_n)
            continue
        dest = assert_path_inside_workspace(target_root, target_root / rel_n)
        # Extra guard: dest must stay under workspace
        assert_path_inside_workspace(workspace, dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        # Paths relative to git/repo root when possible (for DevelopmentEngine commit)
        copied.append(str(dest.relative_to(target_root)).replace("\\", "/"))

    return {
        "ok": True,
        "originals_touched": bool(copied),
        "copied": copied,
        "skipped": skipped,
        "sandbox_root": str(sandbox_root),
        "target_root": str(target_root),
        "workspace": str(workspace),
        "source_run": meta.get("generated_at"),
        "note": "Promoted from مساعد الطيار sandbox after human approve+execute",
    }
