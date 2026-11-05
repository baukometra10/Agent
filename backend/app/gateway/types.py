"""Shared gateway types — kept separate to avoid circular imports."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class ModelRole(str, enum.Enum):
    reasoning = "reasoning"
    coding = "coding"
    fast = "fast"
    multimodal = "multimodal"
    embedding = "embedding"
    critic = "critic"


@dataclass
class ModelInvocation:
    role: ModelRole
    model_id: str
    provider: str
    prompt: str
    system: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelResponse:
    role: ModelRole
    model_id: str
    content: str
    tokens_in: int = 0
    tokens_out: int = 0
    raw: dict[str, Any] = field(default_factory=dict)
    simulated: bool = False
    error: str | None = None
    route_tier: str | None = None
    confidence: float | None = None
