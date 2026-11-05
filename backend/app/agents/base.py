from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.db.models import AgentDepartment
from app.gateway.router import ModelRole


@dataclass
class AgentResult:
    success: bool
    summary: str
    evidence: dict[str, Any] = field(default_factory=dict)
    knowledge: list[dict[str, Any]] = field(default_factory=list)
    needs_human: bool = False
    error: str | None = None


@dataclass
class AgentSpec:
    name: str
    department: AgentDepartment
    description: str
    model_role: ModelRole
    can_execute_code: bool = False
    can_self_approve: bool = False  # always False for developers
    tier: str = "specialist"  # conductor | critic | specialist
    cursor_role: str = ""  # human-facing Cursor-analogue role label


class BaseAgent(ABC):
    spec: AgentSpec

    @abstractmethod
    async def run(self, context: dict[str, Any]) -> AgentResult:
        raise NotImplementedError
