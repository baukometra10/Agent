"""Chief / worker pool types."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


class WorkerStatus(str, enum.Enum):
    idle = "idle"
    busy = "busy"
    training = "training"
    retired = "retired"


# Map Evolve specialist names / intents → ownership specialties (student routes)
SPECIALTY_BY_HINT: dict[str, str] = {
    "coding": "coding",
    "implement": "coding",
    "refactor": "coding",
    "backend": "coding",
    "frontend": "coding",
    "fullstack": "coding",
    "reasoning": "reasoning",
    "plan": "reasoning",
    "analyze": "project_intelligence",
    "understanding": "project_intelligence",
    "architecture": "project_intelligence",
    "critic": "critic",
    "review": "critic",
    "security": "critic",
    "quality": "critic",
    "design": "vision",
    "ui": "vision",
    "vision": "vision",
}


def infer_specialty(agent_name: str | None = None, intent: str | None = None, text: str = "") -> str:
    blob = f"{agent_name or ''} {intent or ''} {text}".lower()
    for key, specialty in SPECIALTY_BY_HINT.items():
        if key in blob:
            return specialty
    return "coding"


@dataclass
class WorkerAgent:
    id: str
    name: str
    specialty: str
    status: WorkerStatus = WorkerStatus.idle
    parent: str = "ChiefAgent"
    task_id: str | None = None
    trained: bool = False
    train_meta: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_task_at: str | None = None
    completed_tasks: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "specialty": self.specialty,
            "status": self.status.value,
            "parent": self.parent,
            "task_id": self.task_id,
            "trained": self.trained,
            "train_meta": self.train_meta,
            "created_at": self.created_at,
            "last_task_at": self.last_task_at,
            "completed_tasks": self.completed_tasks,
        }


@dataclass
class ChiefTask:
    id: str
    objective: str
    specialty: str
    agent_role: str
    status: str = "queued"  # queued | running | done | failed
    worker_id: str | None = None
    spawned_worker: bool = False
    result_summary: str | None = None
    model_id: str | None = None
    simulated: bool = False
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "objective": self.objective,
            "specialty": self.specialty,
            "agent_role": self.agent_role,
            "status": self.status,
            "worker_id": self.worker_id,
            "spawned_worker": self.spawned_worker,
            "result_summary": self.result_summary,
            "model_id": self.model_id,
            "simulated": self.simulated,
            "error": self.error,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "metadata": self.metadata,
        }


def new_worker_id() -> str:
    return f"w-{uuid4().hex[:10]}"


def new_task_id() -> str:
    return f"t-{uuid4().hex[:10]}"
