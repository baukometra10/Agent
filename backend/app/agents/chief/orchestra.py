"""Chief Agent — owned-model lead that owns a dynamic worker pool.

Doctrine:
- Chief = primary agent (Internal Reasoning student as brain)
- Workers = specialists under Chief; Chief assigns all tasks
- If every worker is busy → Chief spawns + fast-trains a new worker → assigns task
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.activity import get_activity_bus
from app.agents.chief.trainer import fast_train_specialty
from app.agents.chief.types import (
    ChiefTask,
    WorkerAgent,
    WorkerStatus,
    infer_specialty,
    new_task_id,
    new_worker_id,
)
from app.config import Settings, get_settings
from app.gateway.router import ModelGateway, get_model_gateway
from app.gateway.types import ModelRole


SPECIALTY_ROLE: dict[str, ModelRole] = {
    "coding": ModelRole.coding,
    "reasoning": ModelRole.reasoning,
    "critic": ModelRole.critic,
    "project_intelligence": ModelRole.reasoning,
    "vision": ModelRole.multimodal,
}


class ChiefOrchestra:
    """Singleton-ish runtime pool managed by the Chief Agent."""

    def __init__(self, settings: Settings | None = None, gateway: ModelGateway | None = None) -> None:
        self.settings = settings or get_settings()
        self.gateway = gateway or get_model_gateway()
        self.min_workers = int(self.settings.chief_min_workers)
        self.max_workers = int(self.settings.chief_max_workers)
        self.workers: dict[str, WorkerAgent] = {}
        self.tasks: dict[str, ChiefTask] = {}
        self._lock = asyncio.Lock()
        self._ensure_bootstrap_workers()

    def _ensure_bootstrap_workers(self) -> None:
        if self.workers:
            return
        for specialty in ("coding", "reasoning", "critic", "vision"):
            wid = new_worker_id()
            self.workers[wid] = WorkerAgent(
                id=wid,
                name=f"Worker-{specialty}-{wid[-4:]}",
                specialty=specialty,
                status=WorkerStatus.idle,
                trained=True,
                train_meta={"bootstrap": True},
            )

    def status(self) -> dict[str, Any]:
        workers = list(self.workers.values())
        idle = sum(1 for w in workers if w.status == WorkerStatus.idle)
        busy = sum(1 for w in workers if w.status == WorkerStatus.busy)
        training = sum(1 for w in workers if w.status == WorkerStatus.training)
        recent = sorted(self.tasks.values(), key=lambda t: t.created_at, reverse=True)[:20]
        return {
            "chief": {
                "name": "ChiefAgent",
                "role": "General lead — owns internal student brain and assigns all subordinate work",
                "model_preference": "internal/reasoning",
                "doctrine": "Chief distributes; workers execute; spawn+fast-train when saturated",
            },
            "pool": {
                "min_workers": self.min_workers,
                "max_workers": self.max_workers,
                "total": len(workers),
                "idle": idle,
                "busy": busy,
                "training": training,
            },
            "workers": [w.to_dict() for w in workers],
            "recent_tasks": [t.to_dict() for t in recent],
        }

    def _pick_idle(self, specialty: str) -> WorkerAgent | None:
        # Prefer matching specialty, then any idle
        for w in self.workers.values():
            if w.status == WorkerStatus.idle and w.specialty == specialty:
                return w
        for w in self.workers.values():
            if w.status == WorkerStatus.idle:
                return w
        return None

    async def spawn_worker(self, specialty: str, *, reason: str = "pool_saturated") -> WorkerAgent:
        async with self._lock:
            if len(self.workers) >= self.max_workers:
                raise RuntimeError(f"Chief at max_workers={self.max_workers}; cannot spawn")
            wid = new_worker_id()
            worker = WorkerAgent(
                id=wid,
                name=f"Worker-{specialty}-{wid[-4:]}",
                specialty=specialty,
                status=WorkerStatus.training,
                trained=False,
                train_meta={"reason": reason},
            )
            self.workers[wid] = worker

        bus = get_activity_bus()
        bus.emit(
            "decision",
            "الوكيل الرئيس ينشئ عاملًا جديدًا",
            detail=f"{worker.name} · specialty={specialty} · {reason}",
            agent="ChiefAgent",
            intensity=0.95,
            payload={"worker_id": worker.id, "specialty": specialty, "reason": reason},
        )

        train_meta = await fast_train_specialty(specialty, settings=self.settings)
        async with self._lock:
            worker.trained = True
            worker.train_meta = {**worker.train_meta, **train_meta}
            worker.status = WorkerStatus.idle

        bus.emit(
            "tool",
            "تدريب سريع للعامل اكتمل",
            detail=f"{worker.name} ready · dataset={train_meta.get('dataset_count')}",
            agent="ChiefAgent",
            intensity=0.7,
            payload=train_meta,
        )
        return worker

    async def assign(
        self,
        objective: str,
        *,
        agent_role: str = "Specialist",
        specialty: str | None = None,
        intent: str | None = None,
        context: dict[str, Any] | None = None,
        project_id: str | None = None,
        project_name: str | None = None,
    ) -> dict[str, Any]:
        specialty = specialty or infer_specialty(agent_role, intent, objective)
        task = ChiefTask(
            id=new_task_id(),
            objective=objective,
            specialty=specialty,
            agent_role=agent_role,
            metadata={"context_keys": list((context or {}).keys()), "intent": intent},
        )
        self.tasks[task.id] = task

        bus = get_activity_bus()
        bus.emit(
            "think",
            "الوكيل الرئيس يوزّع مهمة",
            detail=f"{agent_role} → {specialty}: {objective[:160]}",
            project_id=project_id,
            project_name=project_name,
            agent="ChiefAgent",
            intensity=0.85,
            payload={"task_id": task.id, "specialty": specialty},
        )

        spawned = False
        worker = self._pick_idle(specialty)
        if worker is None:
            if len(self.workers) < self.max_workers:
                worker = await self.spawn_worker(specialty, reason="all_workers_busy")
                spawned = True
            else:
                # Wait briefly for an idle worker (simple backpressure)
                for _ in range(40):
                    await asyncio.sleep(0.05)
                    worker = self._pick_idle(specialty)
                    if worker:
                        break
                if worker is None:
                    task.status = "failed"
                    task.error = "all workers busy and pool at max"
                    task.finished_at = datetime.now(timezone.utc).isoformat()
                    return {"ok": False, "task": task.to_dict(), "chief": self.status()["pool"]}

        async with self._lock:
            worker.status = WorkerStatus.busy
            worker.task_id = task.id
            task.status = "running"
            task.worker_id = worker.id
            task.spawned_worker = spawned

        try:
            result = await self._run_worker(worker, task, context=context or {})
        except Exception as exc:  # noqa: BLE001
            task.status = "failed"
            task.error = str(exc)
            result = {"summary": f"[chief-worker-error] {exc}", "model_id": None, "simulated": False}
        finally:
            async with self._lock:
                worker.status = WorkerStatus.idle
                worker.task_id = None
                worker.last_task_at = datetime.now(timezone.utc).isoformat()
                if task.status != "failed":
                    worker.completed_tasks += 1

        task.result_summary = result.get("summary")
        task.model_id = result.get("model_id")
        task.simulated = bool(result.get("simulated"))
        if task.status != "failed":
            task.status = "done"
        task.finished_at = datetime.now(timezone.utc).isoformat()

        distill_info = None
        if task.status == "done" and task.result_summary and not task.simulated:
            from app.agents.chief.feedback import distill_chief_outcome

            distill_info = distill_chief_outcome(
                specialty=worker.specialty,
                objective=task.objective,
                summary=task.result_summary,
                agent_role=task.agent_role,
                metadata={"chief_task_id": task.id, "worker_id": worker.id},
                settings=self.settings,
            )
            task.metadata["distillation"] = distill_info

        bus.emit(
            "think",
            f"العامل {worker.name} أنهى المهمة",
            detail=(task.result_summary or "")[:240],
            project_id=project_id,
            project_name=project_name,
            agent=worker.name,
            intensity=0.55,
            payload={"task_id": task.id, "spawned": spawned, "distillation": distill_info},
        )
        return {
            "ok": task.status == "done",
            "task": task.to_dict(),
            "worker": worker.to_dict(),
            "spawned_worker": spawned,
            "distillation": distill_info,
        }

    async def _run_worker(
        self,
        worker: WorkerAgent,
        task: ChiefTask,
        *,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        role = SPECIALTY_ROLE.get(worker.specialty, ModelRole.fast)
        mem = context.get("memory") or {}
        binding = mem.get("binding") or {}
        standing = mem.get("standing_instructions") or []
        standing_txt = "\n".join(f"- {s.get('content', '')[:180]}" for s in standing[:6])
        recent = (mem.get("transcript") or [])[-8:]
        recent_txt = "\n".join(
            f"{r.get('role')}: {str(r.get('content', ''))[:140]}" for r in recent
        )
        # Force internal student path — Chief's army runs on owned models first
        prompt = (
            f"You are subordinate worker '{worker.name}' ({worker.specialty}) under ChiefAgent.\n"
            f"Assigned role label: {task.agent_role}\n"
            f"Workspace (exact): {binding.get('workspace_path') or 'unknown'}\n"
            f"Isolation namespace: {binding.get('isolation_namespace') or 'unknown'}\n"
            f"Standing instructions for THIS project only:\n{standing_txt or '(none)'}\n"
            f"Recent retained words:\n{recent_txt or '(none)'}\n"
            f"Objective: {task.objective}\n"
            f"Context keys: {list(context.keys())}\n"
            f"Knowledge: {(context.get('knowledge') or {}).get('hits', [])[:3]}\n"
            f"Roadmap: {(context.get('roadmap') or {}).get('roadmap')}\n"
            "Report concrete findings and next actions. Do not claim merges/deploys. "
            "Never mix memory with another project. You report only to ChiefAgent."
        )
        response = await self.gateway.complete(
            role,
            prompt,
            system=(
                f"Subordinate of ChiefAgent. Specialty={worker.specialty}. "
                "Cursor-class awareness: know this workspace only, cite paths, "
                "evidence before edit, smallest change, re-verify. "
                "Never self-approve. Never enumerate the user's whole disk. "
                "Obey standing instructions."
            ),
            metadata={
                "force_internal": True,
                "prefer_promoted": True,
                "agent": worker.name,
                "chief_task": task.id,
                "specialty": worker.specialty,
                "skip_cache": False,
            },
        )
        return {
            "summary": response.content,
            "model_id": response.model_id,
            "simulated": response.simulated,
            "route_tier": response.route_tier,
            "confidence": response.confidence,
        }

    async def dispatch_many(
        self,
        jobs: list[dict[str, Any]],
        *,
        project_id: str | None = None,
        project_name: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Chief fans out jobs; pool auto-spawns when saturated."""
        # Bound concurrency by max_workers but allow spawn path inside assign
        sem = asyncio.Semaphore(self.max_workers)

        async def _one(job: dict[str, Any]) -> dict[str, Any]:
            async with sem:
                return await self.assign(
                    job.get("objective") or job.get("user_message") or "",
                    agent_role=job.get("agent_role") or job.get("agent") or "Specialist",
                    specialty=job.get("specialty"),
                    intent=job.get("intent"),
                    context=context,
                    project_id=project_id,
                    project_name=project_name,
                )

        return list(await asyncio.gather(*[_one(j) for j in jobs]))


_chief: ChiefOrchestra | None = None


def get_chief_orchestra() -> ChiefOrchestra:
    global _chief
    if _chief is None:
        _chief = ChiefOrchestra()
    return _chief


def reset_chief_orchestra() -> None:
    global _chief
    _chief = None
