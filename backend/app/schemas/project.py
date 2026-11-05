from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str | None = None
    owner_email: str | None = None
    slug: str | None = Field(default=None, max_length=120)
    local_path: str | None = None  # optional: create blank on this folder / Desktop child


class ProjectCreateGit(ProjectCreate):
    git_url: HttpUrl
    branch: str | None = None


class ProjectCreatePath(ProjectCreate):
    local_path: str


class ProjectOut(BaseModel):
    id: UUID
    slug: str
    name: str
    description: str | None
    status: str
    source_type: str
    source_uri: str | None
    workspace_path: str
    isolation_namespace: str
    languages: list[Any]
    frameworks: list[Any]
    tech_stack: dict[str, Any]
    file_stats: dict[str, Any]
    understanding_progress: float
    last_analyzed_at: datetime | None
    last_evolution_at: datetime | None
    owner_email: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeNodeOut(BaseModel):
    id: UUID
    memory_layer: str
    category: str
    kind: str
    title: str
    content: str
    confidence: float
    source_type: str
    source_path: str | None
    evidence: dict[str, Any]
    is_stale: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UnderstandingRunOut(BaseModel):
    project_id: UUID
    status: str
    understanding_progress: float
    knowledge_written: int
    summary: str | None = None
    scan: dict[str, Any] = Field(default_factory=dict)
    intelligence: dict[str, Any] = Field(default_factory=dict)
    knowledge_graph: dict[str, Any] = Field(default_factory=dict)
    multi_agent: dict[str, Any] = Field(default_factory=dict)
    analysis: dict[str, Any] = Field(default_factory=dict)
    planning: dict[str, Any] = Field(default_factory=dict)
    proposals: dict[str, Any] = Field(default_factory=dict)
    autonomy: dict[str, Any] = Field(default_factory=dict)


class ProposalOut(BaseModel):
    id: UUID
    title: str
    problem: str
    proposal: str
    rationale: str
    impact: str
    risks: str
    acceptance_criteria: str
    priority: int
    complexity: str
    status: str
    category: str
    affected_parts: list[Any]
    dependencies: list[Any]
    origin: str
    revision_notes: str | None
    user_request: str | None
    roadmap_item_id: UUID | None
    created_at: datetime
    approved_at: datetime | None

    model_config = {"from_attributes": True}


class ProposalActionIn(BaseModel):
    notes: str = ""


class ExecutionResultOut(BaseModel):
    status: str
    branch: str | None = None
    commit: str | None = None
    applied: dict[str, Any] | None = None
    review: dict[str, Any] | None = None
    merged: bool = False
    sandbox: dict[str, Any] | None = None
    next_step: str | None = None


class ChatSessionOut(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    status: str
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChatSessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ChatSessionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = Field(default=None, max_length=32)


class ChatMessageIn(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    # Chief: auto | internal | openrouter | openai/gpt-4.1 | anthropic/claude-…
    preferred_provider: str | None = Field(default=None, max_length=80)
    # Specialist worker under the chief (optional): BackendDeveloper, …
    preferred_agent: str | None = Field(default=None, max_length=80)
    mode: str | None = Field(default=None, max_length=32)  # agent | ask | edit
    attachments: list[str] = Field(default_factory=list, max_length=20)
    # Continue from a stopped/partial turn
    resume: bool = False
    # Per-session ceilings (tab budgets)
    max_tokens_budget: int | None = Field(default=None, ge=256, le=200000)
    max_seconds: int | None = Field(default=None, ge=5, le=3600)
    allow_teacher: bool | None = Field(default=True)


class ChatMessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime
    tool_payload: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class ChatReplyOut(BaseModel):
    session_id: UUID
    reply: str
    proposal: dict[str, Any] | None = None
    tools_used: list[str] = Field(default_factory=list)
    model: str | None = None
    simulated: bool = False
    # cache | internal | teacher | simulate — ownership cost path
    route_tier: str | None = None
    conductor: str | None = None
    intent: str | None = None
    intent_label: str | None = None
    specialists: list[str] = Field(default_factory=list)
    session_title: str | None = None
    handoff: dict[str, Any] | None = None


class RoadmapItemOut(BaseModel):
    id: UUID
    title: str
    description: str
    rationale: str
    goal: str
    category: str
    priority: int
    complexity: str
    impact_score: float
    risk_score: float
    status: str
    affected_parts: list[Any]
    dependencies: list[Any]
    risks: str
    acceptance_criteria: str
    sort_order: int

    model_config = {"from_attributes": True}


class RoadmapOut(BaseModel):
    id: UUID
    version: int
    title: str
    vision: str
    status: str
    summary: dict[str, Any]
    autonomous: bool
    generated_by: str
    created_at: datetime
    items: list[RoadmapItemOut] = Field(default_factory=list)


class FindingOut(BaseModel):
    id: UUID
    category: str
    kind: str
    severity: str
    status: str
    title: str
    description: str
    recommendation: str
    confidence: float
    affected_parts: list[Any]
    evidence: dict[str, Any]
    source_agent: str
    fingerprint: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentTaskOut(BaseModel):
    id: UUID
    department: str
    agent_name: str
    objective: str
    status: str
    model_used: str | None
    parent_task_id: UUID | None
    output_payload: dict[str, Any]
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeEdgeOut(BaseModel):
    id: UUID
    from_node_id: UUID = Field(alias="from")
    to_node_id: UUID = Field(alias="to")
    relation: str
    confidence: float

    model_config = {"populate_by_name": True}


class KnowledgeGraphOut(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    layers: dict[str, int]
