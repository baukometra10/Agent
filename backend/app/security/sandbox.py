"""Docker sandbox stubs. Untrusted project code must never run on the host."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.security.isolation import IsolationContext


@dataclass
class SandboxResult:
    allowed: bool
    reason: str
    container_spec: dict | None = None


def plan_sandbox_run(
    isolation: IsolationContext,
    settings: Settings,
    *,
    command: list[str],
    workdir: Path | None = None,
) -> SandboxResult:
    if not settings.allow_untrusted_code_execution:
        return SandboxResult(
            allowed=False,
            reason="Untrusted code execution is disabled. Enable only after Docker sandbox is verified.",
        )

    if not isolation.allow_code_execution:
        return SandboxResult(allowed=False, reason="Project isolation forbids code execution")

    return SandboxResult(
        allowed=True,
        reason="Planned Docker sandbox execution",
        container_spec={
            "image": "evolve-sandbox:latest",
            "command": command,
            "network_disabled": isolation.network_disabled,
            "binds": {
                str(isolation.workspace_path): {"bind": "/workspace", "mode": "rw"},
            },
            "working_dir": str(workdir or "/workspace"),
            "mem_limit": "1g",
            "nano_cpus": 1_000_000_000,
            "read_only": False,
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges:true"],
        },
    )
