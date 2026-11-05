"""Deploy adapter contract — human-gated; real cloud only when explicitly enabled."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class DeployRequest:
    project_name: str
    project_slug: str
    workspace_path: str
    target: str = "staging"
    force_simulate: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeployResult:
    provider: str
    status: str
    simulated: bool
    message: str
    artifact: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status,
            "simulated": self.simulated,
            "message": self.message,
            "artifact": self.artifact,
        }


class DeployAdapter(Protocol):
    name: str
    description: str

    async def deploy(self, request: DeployRequest) -> DeployResult: ...
