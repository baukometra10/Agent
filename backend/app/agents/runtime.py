"""Multi-agent runtime — permissions, dispatch, parallel execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentResult, AgentSpec, BaseAgent
from app.agents.registry import AGENT_REGISTRY, get_agent_spec
from app.db.models import AgentDepartment, AgentTask, TaskStatus
from app.gateway.router import get_model_gateway


@dataclass
class DispatchRequest:
    agent_name: str
    objective: str
    context: dict[str, Any] = field(default_factory=dict)
    parent_task_id: UUID | None = None


@dataclass
class DispatchResult:
    agent_name: str
    department: str
    result: AgentResult
    task_id: UUID | None = None
    model_used: str | None = None
    rejected: bool = False
    reject_reason: str | None = None


class PermissionError(RuntimeError):
    pass


class AgentRuntime:
    """Central runtime used by Master Orchestrator to run specialists safely."""

    def __init__(self, session: AsyncSession | None = None, project_id: UUID | None = None) -> None:
        self.session = session
        self.project_id = project_id
        self.gateway = get_model_gateway()
        self._implementations: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._implementations[agent.spec.name] = agent

    def resolve_spec(self, name: str) -> AgentSpec:
        spec = get_agent_spec(name)
        if not spec:
            raise KeyError(f"Unknown agent: {name}")
        return spec

    def assert_allowed(self, spec: AgentSpec, *, require_code: bool = False) -> None:
        if spec.can_self_approve:
            raise PermissionError(f"{spec.name} cannot self-approve by policy")
        if require_code and not spec.can_execute_code:
            raise PermissionError(f"{spec.name} is not allowed to execute code")
        if spec.department == AgentDepartment.development and spec.can_self_approve:
            raise PermissionError("Developers cannot self-approve")

    async def _execute_agent(self, spec: AgentSpec, request: DispatchRequest) -> AgentResult:
        agent = self._implementations.get(spec.name)
        if agent is None:
            return AgentResult(
                success=False,
                summary=f"Agent {spec.name} has no implementation yet",
                error="not_implemented",
                evidence={"department": spec.department.value},
            )
        ctx = {
            **request.context,
            "objective": request.objective,
            "agent_name": spec.name,
            "model_role": spec.model_role.value,
        }
        try:
            return await agent.run(ctx)
        except Exception as exc:  # noqa: BLE001
            return AgentResult(success=False, summary=str(exc), error=str(exc))

    async def _persist_task(
        self,
        spec: AgentSpec,
        request: DispatchRequest,
        result: AgentResult,
        model_id: str,
        started: datetime,
    ) -> UUID | None:
        if not self.session or not self.project_id:
            return None
        task = AgentTask(
            project_id=self.project_id,
            department=spec.department,
            agent_name=spec.name,
            objective=request.objective,
            status=TaskStatus.succeeded if result.success else TaskStatus.failed,
            model_used=model_id,
            input_payload={
                "objective": request.objective,
                "context_keys": list(request.context.keys()),
            },
            output_payload={
                "summary": result.summary,
                "needs_human": result.needs_human,
                "knowledge_count": len(result.knowledge),
            },
            evidence=result.evidence,
            error_message=result.error,
            parent_task_id=request.parent_task_id,
            started_at=started,
            finished_at=datetime.now(timezone.utc),
        )
        self.session.add(task)
        await self.session.flush()
        return task.id

    async def run_one(self, request: DispatchRequest) -> DispatchResult:
        spec = self.resolve_spec(request.agent_name)
        self.assert_allowed(spec)
        _, model_id = self.gateway.resolve(spec.model_role)
        started = datetime.now(timezone.utc)
        result = await self._execute_agent(spec, request)
        task_id = await self._persist_task(spec, request, result, model_id, started)
        return DispatchResult(
            agent_name=spec.name,
            department=spec.department.value,
            result=result,
            task_id=task_id,
            model_used=model_id,
        )

    async def run_parallel(self, requests: list[DispatchRequest]) -> list[DispatchResult]:
        """Run agent compute concurrently; persist DB rows sequentially (session-safe)."""
        if not requests:
            return []

        async def compute(req: DispatchRequest) -> tuple[DispatchRequest, AgentSpec, str, datetime, AgentResult]:
            spec = self.resolve_spec(req.agent_name)
            self.assert_allowed(spec)
            _, model_id = self.gateway.resolve(spec.model_role)
            started = datetime.now(timezone.utc)
            result = await self._execute_agent(spec, req)
            return req, spec, model_id, started, result

        computed = await asyncio.gather(*[compute(req) for req in requests])

        outputs: list[DispatchResult] = []
        for req, spec, model_id, started, result in computed:
            task_id = await self._persist_task(spec, req, result, model_id, started)
            outputs.append(
                DispatchResult(
                    agent_name=spec.name,
                    department=spec.department.value,
                    result=result,
                    task_id=task_id,
                    model_used=model_id,
                )
            )
        return outputs


def departments_overview() -> list[dict[str, Any]]:
    by_dept: dict[str, list[dict]] = {}
    for spec in AGENT_REGISTRY:
        by_dept.setdefault(spec.department.value, []).append(
            {
                "name": spec.name,
                "description": spec.description,
                "model_role": spec.model_role.value,
                "can_execute_code": spec.can_execute_code,
                "can_self_approve": spec.can_self_approve,
            }
        )
    return [{"department": dept, "agents": agents} for dept, agents in by_dept.items()]
