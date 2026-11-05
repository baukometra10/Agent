from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


def enum_column(enum_cls: type[enum.Enum], name: str):
    return Enum(enum_cls, name=name, native_enum=False, values_callable=lambda x: [e.value for e in x])


class ProjectStatus(str, enum.Enum):
    created = "created"
    ingesting = "ingesting"
    understanding = "understanding"
    ready = "ready"
    evolving = "evolving"
    error = "error"
    archived = "archived"


class KnowledgeKind(str, enum.Enum):
    fact = "fact"
    inference = "inference"
    unverified = "unverified"


class TaskStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class ProposalStatus(str, enum.Enum):
    draft = "draft"
    awaiting_approval = "awaiting_approval"
    approved = "approved"
    rejected = "rejected"
    revision_requested = "revision_requested"
    executing = "executing"
    completed = "completed"
    awaiting_merge = "awaiting_merge"
    merged = "merged"
    cancelled = "cancelled"


class FindingKind(str, enum.Enum):
    problem = "problem"
    opportunity = "opportunity"
    risk = "risk"


class FindingSeverity(str, enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"


class FindingStatus(str, enum.Enum):
    open = "open"
    acknowledged = "acknowledged"
    converted_to_proposal = "converted_to_proposal"
    dismissed = "dismissed"
    resolved = "resolved"


class RoadmapStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    superseded = "superseded"
    archived = "archived"


class RoadmapItemStatus(str, enum.Enum):
    planned = "planned"
    ready_for_proposal = "ready_for_proposal"
    in_proposal = "in_proposal"
    in_progress = "in_progress"
    done = "done"
    cancelled = "cancelled"
    deferred = "deferred"


class AgentDepartment(str, enum.Enum):
    understanding = "understanding"
    engineering = "engineering"
    design = "design"
    product = "product"
    development = "development"
    security = "security"
    quality = "quality"
    operations = "operations"
    documentation = "documentation"
    critic = "critic"
    orchestrator = "orchestrator"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        enum_column(ProjectStatus, "project_status"), default=ProjectStatus.created
    )
    source_type: Mapped[str] = mapped_column(String(32))  # git | upload | path
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    workspace_path: Mapped[str] = mapped_column(Text)
    isolation_namespace: Mapped[str] = mapped_column(String(120), unique=True)
    languages: Mapped[list[Any]] = mapped_column(JSON, default=list)
    frameworks: Mapped[list[Any]] = mapped_column(JSON, default=list)
    tech_stack: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    file_stats: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    understanding_progress: Mapped[float] = mapped_column(Float, default=0.0)
    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_evolution_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    owner_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Autonomy defaults: think/plan freely; never execute/merge without human gate.
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=lambda: {
            "autonomy": {
                "auto_understand": True,
                "auto_analyze": True,
                "auto_plan": True,
                "auto_draft_proposals": True,
                "auto_execute": False,
                "auto_merge": False,
                "auto_deploy": False,
            }
        },
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    knowledge_nodes: Mapped[list[KnowledgeNode]] = relationship(back_populates="project")
    tasks: Mapped[list[AgentTask]] = relationship(back_populates="project")
    proposals: Mapped[list[Proposal]] = relationship(back_populates="project")
    decisions: Mapped[list[DecisionRecord]] = relationship(back_populates="project")
    findings: Mapped[list[AnalysisFinding]] = relationship(back_populates="project")
    roadmaps: Mapped[list[Roadmap]] = relationship(back_populates="project")
    sessions: Mapped[list["AgentSession"]] = relationship(back_populates="project")
    ventures: Mapped[list["VentureRun"]] = relationship(back_populates="project")


class KnowledgeNode(Base):
    """Single knowledge atom: fact / inference / unverified, always sourced."""

    __tablename__ = "knowledge_nodes"
    __table_args__ = (
        Index("ix_knowledge_project_kind", "project_id", "kind"),
        Index("ix_knowledge_project_category", "project_id", "category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    memory_layer: Mapped[str] = mapped_column(String(32))  # project|architecture|decision|execution
    category: Mapped[str] = mapped_column(String(64))
    kind: Mapped[KnowledgeKind] = mapped_column(enum_column(KnowledgeKind, "knowledge_kind"))
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    source_type: Mapped[str] = mapped_column(String(64))  # file|git|doc|agent|user
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    project_revision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped[Project] = relationship(back_populates="knowledge_nodes")
    edges_out: Mapped[list[KnowledgeEdge]] = relationship(
        back_populates="from_node",
        foreign_keys="KnowledgeEdge.from_node_id",
    )


class KnowledgeEdge(Base):
    __tablename__ = "knowledge_edges"
    __table_args__ = (UniqueConstraint("from_node_id", "to_node_id", "relation"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    from_node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("knowledge_nodes.id", ondelete="CASCADE")
    )
    to_node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("knowledge_nodes.id", ondelete="CASCADE")
    )
    relation: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    from_node: Mapped[KnowledgeNode] = relationship(
        back_populates="edges_out", foreign_keys=[from_node_id]
    )


class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    department: Mapped[AgentDepartment] = mapped_column(
        enum_column(AgentDepartment, "agent_department")
    )
    agent_name: Mapped[str] = mapped_column(String(120))
    objective: Mapped[str] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(
        enum_column(TaskStatus, "task_status"), default=TaskStatus.pending
    )
    model_used: Mapped[str | None] = mapped_column(String(120), nullable=True)
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    output_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    cost_tokens: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_task_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("agent_tasks.id"), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped[Project] = relationship(back_populates="tasks")


class Roadmap(Base):
    """Phase 6 — autonomously regenerated strategic plan per project."""

    __tablename__ = "roadmaps"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(255))
    vision: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[RoadmapStatus] = mapped_column(
        enum_column(RoadmapStatus, "roadmap_status"), default=RoadmapStatus.active
    )
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    generated_by: Mapped[str] = mapped_column(String(120), default="PlanningEngine")
    autonomous: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped[Project] = relationship(back_populates="roadmaps")
    items: Mapped[list[RoadmapItem]] = relationship(
        back_populates="roadmap", cascade="all, delete-orphan"
    )


class RoadmapItem(Base):
    __tablename__ = "roadmap_items"
    __table_args__ = (Index("ix_roadmap_items_priority", "roadmap_id", "priority"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    roadmap_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("roadmaps.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    finding_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text)
    goal: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(64))
    priority: Mapped[int] = mapped_column(Integer, default=50)  # higher = sooner
    complexity: Mapped[str] = mapped_column(String(32), default="medium")
    impact_score: Mapped[float] = mapped_column(Float, default=0.5)
    risk_score: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[RoadmapItemStatus] = mapped_column(
        enum_column(RoadmapItemStatus, "roadmap_item_status"), default=RoadmapItemStatus.planned
    )
    affected_parts: Mapped[list[Any]] = mapped_column(JSON, default=list)
    dependencies: Mapped[list[Any]] = mapped_column(JSON, default=list)
    risks: Mapped[str] = mapped_column(Text, default="")
    acceptance_criteria: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    roadmap: Mapped[Roadmap] = relationship(back_populates="items")


class Proposal(Base):
    """Human-gated change proposal. Never executes without approval."""

    __tablename__ = "proposals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    roadmap_item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("roadmap_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    problem: Mapped[str] = mapped_column(Text)
    proposal: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text)
    impact: Mapped[str] = mapped_column(Text)
    risks: Mapped[str] = mapped_column(Text)
    acceptance_criteria: Mapped[str] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=50)
    complexity: Mapped[str] = mapped_column(String(32), default="medium")
    status: Mapped[ProposalStatus] = mapped_column(
        enum_column(ProposalStatus, "proposal_status"), default=ProposalStatus.draft
    )
    category: Mapped[str] = mapped_column(String(64), default="improvement")
    affected_parts: Mapped[list[Any]] = mapped_column(JSON, default=list)
    dependencies: Mapped[list[Any]] = mapped_column(JSON, default=list)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    origin: Mapped[str] = mapped_column(String(32), default="roadmap")  # roadmap|chat|manual
    revision_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_request: Mapped[str | None] = mapped_column(Text, nullable=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped[Project] = relationship(back_populates="proposals")


class AgentSession(Base):
    """Cursor-like interactive agent session (project-scoped)."""

    __tablename__ = "agent_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), default="Agent session")
    status: Mapped[str] = mapped_column(String(32), default="active")  # active|archived
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped[Project] = relationship(back_populates="sessions")
    messages: Mapped[list[AgentMessage]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("agent_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(32))  # user|assistant|system|tool
    content: Mapped[str] = mapped_column(Text)
    tool_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tool_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[AgentSession] = relationship(back_populates="messages")


class AnalysisFinding(Base):
    """Phase 5 — discovered problems / opportunities with evidence."""

    __tablename__ = "analysis_findings"
    __table_args__ = (
        Index("ix_findings_project_category", "project_id", "category"),
        Index("ix_findings_project_severity", "project_id", "severity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(64))
    # quality|architecture|performance|security|ux|feature|integration|maintainability
    kind: Mapped[FindingKind] = mapped_column(enum_column(FindingKind, "finding_kind"))
    severity: Mapped[FindingSeverity] = mapped_column(
        enum_column(FindingSeverity, "finding_severity"), default=FindingSeverity.medium
    )
    status: Mapped[FindingStatus] = mapped_column(
        enum_column(FindingStatus, "finding_status"), default=FindingStatus.open
    )
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    affected_parts: Mapped[list[Any]] = mapped_column(JSON, default=list)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_agent: Mapped[str] = mapped_column(String(120), default="AnalysisEngine")
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped[Project] = relationship(back_populates="findings")


class DecisionRecord(Base):
    __tablename__ = "decision_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    decision: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text)
    made_by: Mapped[str] = mapped_column(String(120))  # agent or user
    alternatives: Mapped[list[Any]] = mapped_column(JSON, default=list)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    related_proposal_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped[Project] = relationship(back_populates="decisions")


class AgentScorecard(Base):
    """Quality metrics per agent — Phase 1 schema, filled as agents run."""

    __tablename__ = "agent_scorecards"
    __table_args__ = (UniqueConstraint("project_id", "agent_name", "metric_window"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    agent_name: Mapped[str] = mapped_column(String(120), index=True)
    metric_window: Mapped[str] = mapped_column(String(32), default="all_time")
    tasks_total: Mapped[int] = mapped_column(Integer, default=0)
    tasks_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    analysis_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    test_pass_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_cost_tokens: Mapped[float | None] = mapped_column(Float, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class VentureStatus(str, enum.Enum):
    draft = "draft"
    running = "running"
    awaiting_approval = "awaiting_approval"
    approved = "approved"
    rejected = "rejected"
    completed = "completed"
    cancelled = "cancelled"
    failed = "failed"


class VenturePhaseName(str, enum.Enum):
    understand = "understand"
    capabilities = "capabilities"
    architecture = "architecture"
    prototype = "prototype"
    simulate = "simulate"
    implement = "implement"
    monitor = "monitor"


class VenturePhaseStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    awaiting_approval = "awaiting_approval"
    approved = "approved"
    rejected = "rejected"
    completed = "completed"
    skipped = "skipped"
    failed = "failed"


class VentureRun(Base):
    """Multi-phase venture: business goal → living system (human-gated)."""

    __tablename__ = "venture_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    brief: Mapped[str] = mapped_column(Text)
    status: Mapped[VentureStatus] = mapped_column(
        enum_column(VentureStatus, "venture_status"), default=VentureStatus.draft
    )
    current_phase: Mapped[str] = mapped_column(String(32), default=VenturePhaseName.understand.value)
    decision_log: Mapped[list[Any]] = mapped_column(JSON, default=list)
    artifacts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    selected_architecture_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped[Project] = relationship(back_populates="ventures")
    phases: Mapped[list["VenturePhase"]] = relationship(
        back_populates="venture", cascade="all, delete-orphan", order_by="VenturePhase.sort_order"
    )


class VenturePhase(Base):
    __tablename__ = "venture_phases"
    __table_args__ = (UniqueConstraint("venture_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    venture_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("venture_runs.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(32))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[VenturePhaseStatus] = mapped_column(
        enum_column(VenturePhaseStatus, "venture_phase_status"),
        default=VenturePhaseStatus.pending,
    )
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    output: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    decision_log: Mapped[list[Any]] = mapped_column(JSON, default=list)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    venture: Mapped[VentureRun] = relationship(back_populates="phases")


class SpixaPattern(Base):
    """Curated cross-project engineering patterns (no client secrets/paths)."""

    __tablename__ = "spixa_patterns"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64), default="architecture")
    pattern: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    tags: Mapped[list[Any]] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.6)
    source_project_count: Mapped[int] = mapped_column(Integer, default=0)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ResearchExperiment(Base):
    """Internal Research Lab experiment — never auto-promotes to production."""

    __tablename__ = "research_experiments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    title: Mapped[str] = mapped_column(String(255))
    hypothesis: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(64), default="routing")  # routing|prompt|model|eval
    status: Mapped[str] = mapped_column(String(32), default="draft")  # draft|running|completed|archived
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    results: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    promote_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    promote_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
