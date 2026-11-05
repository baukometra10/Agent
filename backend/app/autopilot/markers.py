"""Sandbox markers — Spixa (+ legacy Evolve) markers both accepted."""

from __future__ import annotations

from pathlib import Path

MARKERS = (".spixa-sandbox", ".evolve-sandbox")


def has_sandbox_marker(sandbox: Path) -> bool:
    return any((sandbox / name).exists() for name in MARKERS)


def write_sandbox_marker(sandbox: Path) -> Path:
    path = sandbox / ".spixa-sandbox"
    path.write_text("spixa\n", encoding="utf-8")
    # Keep legacy marker for older promote paths during transition
    legacy = sandbox / ".evolve-sandbox"
    if not legacy.exists():
        legacy.write_text("spixa\n", encoding="utf-8")
    return path


def require_sandbox_marker(sandbox: Path) -> None:
    if not has_sandbox_marker(sandbox):
        raise PermissionError("Refusing to patch: missing .spixa-sandbox marker")
