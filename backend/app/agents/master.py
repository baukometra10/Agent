"""Master Conductor — Cursor-class lead agent over Evolve specialists.

User request → classify intent → dispatch specialists (parallel) →
optional IndependentCritic → synthesize answer → optional gated proposal.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.activity import get_activity_bus
from app.agents.hierarchy import IntentRoute, classify_intent, looks_like_product_build
from app.agents.registry import AGENT_INDEX, get_agent_spec
from app.chat.tools import ProjectToolbelt
from app.db.models import Project
from app.gateway.router import ModelRole, get_model_gateway
from app.memory import ProjectLongTermMemory


class MasterConductor:
    """The 'agent' users talk to — same seat as Cursor's primary agent."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.gateway = get_model_gateway()

    async def handle(
        self,
        project: Project,
        *,
        user_message: str,
        session_id: UUID | None = None,
        preferred_agent: str | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        bus = get_activity_bus()
        route = classify_intent(user_message)
        chosen = (preferred_agent or "").strip() or None
        chat_mode = (mode or "").strip().lower() or self._extract_mode(user_message)
        if chosen:
            from dataclasses import replace

            from app.agents.registry import get_agent_spec

            spec = get_agent_spec(chosen)
            if spec:
                # User-picked specialist leads the fan-out; keep route peers as support.
                rest = [s for s in route.specialists if s != chosen]
                route = replace(route, specialists=(chosen, *rest))
                bus.emit(
                    "decision",
                    f"اختيار المستخدم للوكيل: {chosen}",
                    detail=spec.description,
                    project_id=project.id,
                    project_name=project.name,
                    agent=chosen,
                    intensity=0.9,
                    payload={"preferred_agent": chosen, "department": spec.department.value},
                )

        bus.emit(
            "think",
            "الوكيل الأعلى يستلم الطلب",
            detail=user_message[:240],
            project_id=project.id,
            project_name=project.name,
            agent="MasterOrchestrator",
            intensity=0.85,
            payload={
                "user_message": user_message,
                "intent": route.intent,
                "preferred_agent": chosen,
            },
        )
        bus.emit(
            "neural",
            f"توجيه النية: {route.label_ar}",
            detail=f"specialists={', '.join(route.specialists[:4])}…",
            project_id=project.id,
            project_name=project.name,
            agent="MasterOrchestrator",
            intensity=0.95,
            payload={"route": route.intent, "specialists": list(route.specialists)},
        )

        tools = ProjectToolbelt(self.session, project)
        context = await self._gather_context(
            tools, user_message, project=project, session_id=session_id
        )
        binding = (context.get("memory") or {}).get("binding") or {}
        bus.emit(
            "tool",
            "جمع سياق المشروع",
            detail=(
                f"معرفة={context['knowledge'].get('count', 0)} · "
                f"ملفات={context['files'].get('count', 0)} · "
                f"ذاكرة={((context.get('memory') or {}).get('counts') or {}).get('transcript', 0)}"
            ),
            project_id=project.id,
            project_name=project.name,
            agent="MasterOrchestrator",
            intensity=0.55,
            payload={"workspace": binding.get("workspace_path"), "namespace": binding.get("isolation_namespace")},
        )
        bus.emit(
            "memory",
            "ربط مساحة المشروع",
            detail=f"{binding.get('workspace_path') or project.workspace_path}",
            project_id=project.id,
            project_name=project.name,
            agent="MasterOrchestrator",
            intensity=0.45,
            payload=binding,
        )

        # IDE Agent/Edit: applyable file blocks — never DesignEngine/Venture approval gates.
        # Detect early so we skip specialist fan-out (tiny local models collapse under long multi-agent prompts).
        ide_coding = chat_mode in {"agent", "edit"} or self._is_ide_coding_turn(user_message)

        specialist_reports: list[dict[str, Any]] = []
        critic_report = None
        if not ide_coding:
            specialist_reports = await self._run_specialists(
                project, route, user_message, context
            )
            if route.include_critic:
                critic_report = await self._run_named_agent(
                    project,
                    "IndependentCritic",
                    user_message,
                    context,
                    prior=specialist_reports,
                )

        proposal_info = None
        engine_result: dict[str, Any] | None = None
        extra_tools: list[str] = []

        if ide_coding:
            bus.emit(
                "decision",
                "مسار IDE: تنفيذ مباشر بملفات قابلة للتطبيق",
                detail="تخطي بوابة المقترح — Cursor-class apply in workspace",
                project_id=project.id,
                project_name=project.name,
                agent="MasterOrchestrator",
                intensity=0.85,
            )
            extra_tools.append("ide_direct_apply")
        else:
            run_design = route.intent == "design" or (
                route.intent == "implement" and looks_like_product_build(user_message)
            )
            if run_design:
                from app.design.engine import DesignEngine

                bus.emit(
                    "tool",
                    "تنفيذ محرك التصميم / الهيكل",
                    detail=user_message[:200],
                    project_id=project.id,
                    project_name=project.name,
                    agent="UIDesigner",
                    intensity=0.9,
                )
                engine_result = await DesignEngine(self.session).run(
                    project, brief=user_message, draft_proposal=True
                )
                extra_tools.append("design_engine")
                if engine_result.get("proposal_id"):
                    proposal_info = {
                        "proposal_id": engine_result["proposal_id"],
                        "status": "awaiting_approval",
                        "files": engine_result.get("files"),
                    }
            elif route.intent in {"quality", "security"}:
                from app.quality.engine import QualityEngine

                engine_result = await QualityEngine(self.session).run(
                    project, focus=route.intent, draft_proposal=True
                )
                extra_tools.append("quality_engine")
                if engine_result.get("proposal_id"):
                    proposal_info = {
                        "proposal_id": engine_result["proposal_id"],
                        "status": "awaiting_approval",
                        "report": engine_result.get("report"),
                    }
            elif route.intent == "ops":
                from app.deployment.engine import DeploymentEngine

                engine_result = await DeploymentEngine(self.session).plan(
                    project, target="staging", draft_proposal=True
                )
                extra_tools.append("deployment_engine")
                if engine_result.get("proposal_id"):
                    proposal_info = {
                        "proposal_id": engine_result["proposal_id"],
                        "status": "awaiting_approval",
                        "files": engine_result.get("files"),
                        "confirm_required": True,
                    }

            if (
                proposal_info is None
                and route.draft_proposal
                and self._looks_like_change(user_message)
            ):
                bus.emit(
                    "decision",
                    "مسودة مقترح ببوابة بشرية",
                    detail="لا كتابة صامتة — مثل Cursor مع انضباط Evolve",
                    project_id=project.id,
                    project_name=project.name,
                    agent="MasterOrchestrator",
                    intensity=0.7,
                )
                path_hint = context.get("path_hint")
                proposal_info = await tools.draft_change_proposal(
                    title=self._title(user_message),
                    user_request=user_message,
                    plan=(
                        f"Intent={route.intent}\n"
                        f"Specialists={[r['agent'] for r in specialist_reports]}\n"
                        f"Request={user_message}\n"
                        f"Touch={path_hint or 'to be determined'}"
                    ),
                    rationale=(
                        "MasterOrchestrator routed a Cursor-class implement path. "
                        "Execution stays human-gated."
                    ),
                    affected_parts=[path_hint] if path_hint else [],
                )
                extra_tools.append("draft_change_proposal")

        # Release any SQLite write lock before the long synthesis LLM call
        # so other IDE actions (new tab / parallel chat) can proceed.
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()

        evaluations = self._evaluate_specialists(
            specialist_reports, critic=critic_report, user_message=user_message
        )
        if evaluations:
            bus.emit(
                "decision",
                "تقييم المدير التنفيذي للوكلاء",
                detail=f"{len(evaluations)} specialist(s)",
                project_id=project.id,
                project_name=project.name,
                agent="MasterOrchestrator",
                intensity=0.65,
                payload={"evaluations": evaluations},
            )
            try:
                from app.learning.experience import get_experience_journal

                journal = get_experience_journal()
                for ev in evaluations:
                    detail = (
                        f"agent={ev['agent']} score={ev['score']} "
                        f"solved={ev.get('solved')} blocked={ev.get('blocked')} need={ev.get('needs')}"
                    )
                    if float(ev.get("score") or 0) >= 0.6:
                        journal.record_success(
                            title=f"Specialist OK · {ev['agent']}",
                            detail=detail,
                            specialty="reasoning",
                            project_id=str(project.id),
                            meta=ev,
                        )
                    else:
                        journal.record_error(
                            title=f"Specialist gap · {ev['agent']}",
                            detail=detail,
                            specialty="reasoning",
                            project_id=str(project.id),
                            meta=ev,
                        )
            except Exception:
                pass

        synthesis = await self._synthesize(
            project,
            user_message,
            route,
            context,
            specialist_reports,
            critic_report,
            proposal_info,
            engine_result=engine_result,
            ide_coding=ide_coding,
            evaluations=evaluations,
        )

        bus.emit(
            "memory",
            "حفظ نقطة الاستئناف",
            detail=f"توقف عند: {user_message[:120]}",
            project_id=project.id,
            project_name=project.name,
            agent="MasterOrchestrator",
            intensity=0.35,
            payload={"user_message": user_message, "session_id": str(session_id) if session_id else None},
        )
        bus.set_idle(hint=f"توقف عند: {user_message[:120]}")

        return {
            "reply": synthesis["content"],
            "intent": route.intent,
            "intent_label": route.label_ar,
            "specialists": [r["agent"] for r in specialist_reports],
            "reports": specialist_reports,
            "critic": critic_report,
            "evaluations": evaluations,
            "proposal": proposal_info,
            "tools_used": [
                "master_route",
                "search_knowledge",
                "get_roadmap",
                "list_files",
                *[f"agent:{r['agent']}" for r in specialist_reports],
                *(["agent:IndependentCritic"] if critic_report else []),
                *extra_tools,
            ],
            "model": synthesis["model"],
            "simulated": synthesis["simulated"],
            "route_tier": synthesis.get("route_tier"),
            "conductor": "MasterOrchestrator",
            "engine": engine_result,
            "memory_binding": (context.get("memory") or {}).get("binding"),
        }

    async def _gather_context(
        self,
        tools: ProjectToolbelt,
        user_message: str,
        *,
        project: Project,
        session_id: UUID | None = None,
    ) -> dict[str, Any]:
        knowledge = await tools.search_knowledge(user_message[:80])
        roadmap = await tools.get_roadmap_summary()
        files = tools.list_files(".", limit=40)
        path_hint = self._extract_path(user_message)
        file_snippet = tools.read_file(path_hint) if path_hint else None
        memory = await ProjectLongTermMemory(self.session).recall(
            project.id, session_id=session_id
        )
        return {
            "knowledge": knowledge,
            "roadmap": roadmap,
            "files": files,
            "path_hint": path_hint,
            "file_snippet": file_snippet,
            "memory": memory,
        }

    async def _run_specialists(
        self,
        project: Project,
        route: IntentRoute,
        user_message: str,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        # Cap fan-out for latency; conductor still represents the full department map.
        selected = list(route.specialists[:4])
        from app.config import get_settings

        if get_settings().chief_enabled:
            from app.agents.chief import get_chief_orchestra

            chief = get_chief_orchestra()
            bus = get_activity_bus()
            bus.emit(
                "decision",
                "الوكيل الرئيس يوزّع على مجمع العمال",
                detail=f"{len(selected)} مهام · pool={chief.status()['pool']}",
                project_id=project.id,
                project_name=project.name,
                agent="ChiefAgent",
                intensity=0.9,
            )
            jobs = [
                {
                    "agent_role": name,
                    "agent": name,
                    "objective": user_message,
                    "intent": route.intent,
                }
                for name in selected
            ]
            dispatched = await chief.dispatch_many(
                jobs,
                project_id=str(project.id),
                project_name=project.name,
                context=context,
            )
            out: list[dict[str, Any]] = []
            for name, row in zip(selected, dispatched, strict=False):
                task = row.get("task") or {}
                worker = row.get("worker") or {}
                spec = get_agent_spec(name) or AGENT_INDEX.get(name)
                out.append(
                    {
                        "agent": name,
                        "department": spec.department.value if spec else "unknown",
                        "summary": task.get("result_summary") or row.get("error") or "",
                        "model": task.get("model_id"),
                        "simulated": task.get("simulated"),
                        "chief": {
                            "worker": worker.get("name"),
                            "worker_id": worker.get("id"),
                            "spawned_worker": row.get("spawned_worker"),
                            "specialty": worker.get("specialty") or task.get("specialty"),
                            "task_id": task.get("id"),
                        },
                    }
                )
            return [r for r in out if r]

        results = await asyncio.gather(
            *[
                self._run_named_agent(project, name, user_message, context)
                for name in selected
            ]
        )
        return [r for r in results if r]

    async def _run_named_agent(
        self,
        project: Project,
        agent_name: str,
        user_message: str,
        context: dict[str, Any],
        *,
        prior: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        spec = get_agent_spec(agent_name) or AGENT_INDEX.get(agent_name)
        bus = get_activity_bus()
        bus.emit(
            "neural",
            f"تفعيل {agent_name}",
            detail=(spec.description if spec else agent_name),
            project_id=project.id,
            project_name=project.name,
            agent=agent_name,
            intensity=0.9,
        )

        role = spec.model_role if spec else ModelRole.fast
        prior_txt = ""
        if prior:
            prior_txt = "\n".join(f"- {p['agent']}: {p['summary'][:220]}" for p in prior)

        mem = context.get("memory") or {}
        binding = mem.get("binding") or {}
        standing = mem.get("standing_instructions") or []
        recent = (mem.get("transcript") or [])[-12:]
        standing_txt = "\n".join(f"- {s.get('content', '')[:200]}" for s in standing[:8])
        recent_txt = "\n".join(
            f"{r.get('role')}: {str(r.get('content', ''))[:160]}" for r in recent
        )
        lessons = self._teacher_lessons_for(agent_name)
        prompt = (
            f"You are {agent_name}, a specialist taught by the Spixa chief executive.\n"
            f"Project: {project.name}\n"
            f"Workspace (exact): {binding.get('workspace_path') or project.workspace_path}\n"
            f"Isolation namespace: {binding.get('isolation_namespace') or project.isolation_namespace}\n"
            f"Rule: Never mix memory or decisions with any other project.\n"
            f"Standing instructions (must obey):\n{standing_txt or '(none)'}\n"
            f"Lessons from the chief (apply these):\n{lessons or '(none yet)'}\n"
            f"Recent retained words for THIS project only:\n{recent_txt or '(none)'}\n"
            f"User request: {user_message}\n"
            f"Knowledge hits: {(context.get('knowledge') or {}).get('hits', [])[:4]}\n"
            f"Files sample count: {(context.get('files') or {}).get('count')}\n"
            f"File snippet: {context.get('file_snippet')}\n"
            f"Peer specialist notes:\n{prior_txt}\n"
            "Give concrete findings and actionable next steps for the chief to implement. "
            "Do not claim code was applied. Distinguish fact vs inference."
        )
        response = await self.gateway.complete(
            role,
            prompt,
            system=(
                f"Specialist {agent_name}. Learn from the chief's lessons. "
                "Report evidence and next actions only. Never address the end user directly "
                "about ranks, scores, or org structure. Work only inside the bound workspace."
            ),
            metadata={
                "agent": agent_name,
                "project_id": str(project.id),
                "prefer_promoted": True,
            },
        )
        bus.emit(
            "think",
            f"{agent_name} أنهى التحليل",
            detail=response.content[:280],
            project_id=project.id,
            project_name=project.name,
            agent=agent_name,
            intensity=0.55,
        )
        return {
            "agent": agent_name,
            "department": spec.department.value if spec else "unknown",
            "summary": response.content,
            "model": response.model_id,
            "simulated": response.simulated,
        }

    async def _synthesize(
        self,
        project: Project,
        user_message: str,
        route: IntentRoute,
        context: dict[str, Any],
        reports: list[dict[str, Any]],
        critic: dict[str, Any] | None,
        proposal: dict[str, Any] | None,
        *,
        engine_result: dict[str, Any] | None = None,
        ide_coding: bool = False,
        evaluations: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        bus = get_activity_bus()
        bus.emit(
            "decision",
            "الوكيل الأعلى يدمج آراء المتخصصين",
            detail=route.label_ar,
            project_id=project.id,
            project_name=project.name,
            agent="MasterOrchestrator",
            intensity=0.8,
        )
        briefs = "\n".join(f"### {r['agent']}\n{r['summary'][:500]}" for r in reports)
        critic_txt = critic["summary"][:500] if critic else "none"
        eval_txt = ""
        if evaluations:
            eval_txt = "Teacher grades (internal; do not dump raw to user):\n" + "\n".join(
                f"- {e.get('agent')}: score={e.get('score')} solved={e.get('solved')} "
                f"blocked={e.get('blocked')} needs={e.get('needs')}"
                for e in evaluations[:8]
            )
        engine_txt = ""
        if engine_result:
            engine_txt = (
                f"Engine files={engine_result.get('files') or engine_result.get('report')}\n"
                f"Engine status={engine_result.get('status')}\n"
            )
        mem = context.get("memory") or {}
        binding = mem.get("binding") or {}
        standing = mem.get("standing_instructions") or []
        standing_txt = "\n".join(f"- {s.get('content', '')[:220]}" for s in standing[:10])
        semantic_hits = ((mem.get("semantic") or {}).get("hits") or [])[:5]
        semantic_txt = "\n".join(
            f"- ({h.get('score')}) {str(h.get('text') or '')[:200]}" for h in semantic_hits
        )
        tree = context.get("files") or {}
        tree_hint = str(tree.get("paths") or tree.get("entries") or tree)[:1200]
        if ide_coding:
            prompt = (
                "You are Spixa IDE — a Cursor-class coding colleague.\n"
                f"Project: {project.name}\n"
                f"Files: {tree_hint}\n"
                f"Standing: {standing_txt or '(none)'}\n"
                f"Semantic memory: {semantic_txt or '(none)'}\n"
                f"USER:\n{user_message}\n\n"
                "OUTPUT FORMAT (mandatory):\n"
                "1) 2–5 sentences in the USER's language (German if they wrote German, Arabic if Arabic, …).\n"
                "   Acknowledge the ask, give a short numbered plan, say you start now.\n"
                "2) Then real file blocks only:\n"
                "```relative/path.ext\nfull file content\n```\n"
                "3) One short closing sentence in the same language.\n\n"
                "EXAMPLE for German \"weiter mit Entwicklung\":\n"
                "Klar — wir machen weiter. Plan:\n"
                "1) UI/Logik verbessern\n"
                "2) app.js erweitern\n"
                "3) README aktualisieren\n"
                "Ich starte jetzt.\n"
                "```app.js\nconsole.log('ready');\n```\n"
                "Fertig — Dateien geschrieben.\n\n"
                "FORBIDDEN: English-only replies to German/Arabic users; bare `python ```; "
                "`###`; `# README.md` lists; Accept/Approve asks; agent names; Venture gates."
            )
            system = (
                "Mirror the user's language exactly. Colleague tone + short plan + file fences same turn."
            )
        else:
            prompt = (
                "You are MasterOrchestrator — the lead Evolve agent (Cursor-class).\n"
                f"Project: {project.name}\n"
                f"Workspace (exact): {binding.get('workspace_path') or project.workspace_path}\n"
                f"Isolation: {binding.get('isolation_namespace') or project.isolation_namespace}\n"
                f"Standing instructions (execute; never forget for this project):\n"
                f"{standing_txt or '(none)'}\n"
                f"Semantic memory (durable vector recall):\n{semantic_txt or '(none)'}\n"
                f"User: {user_message}\n"
                f"Intent: {route.intent} ({route.label_ar})\n"
                f"Specialist briefs:\n{briefs}\n"
                f"Critic: {critic_txt}\n"
                f"{engine_txt}"
                f"Proposal drafted: {proposal}\n"
                "Write the final user-facing answer in the user's language (Arabic if they wrote Arabic). "
                "Structure: فهم الطلب → ماذا فعل الوكلاء → الخطة → الخطوة البشرية التالية. "
                "Never claim code was merged. Never mix this project's memory with another."
            )
            system = (
                "Lead agent. Clear, decisive, honest about gates. "
                "Retain and execute every user instruction for THIS project only."
            )
        response = await self.gateway.complete(
            ModelRole.reasoning,
            prompt,
            system=system,
            metadata={
                "agent": "MasterOrchestrator",
                "project_id": str(project.id),
                "prefer_promoted": True,
            },
        )
        text = response.content
        if proposal and not ide_coding:
            text += (
                f"\n\n---\nمقترح بانتظار موافقتك: `{proposal.get('proposal_id')}`\n"
                f"الحالة: {proposal.get('status')}\n"
                "بعد الاعتماد: مركز التنفيذ → فرع Git → مراجعة → دمج بشري."
            )
        return {
            "content": text,
            "model": response.model_id,
            "simulated": response.simulated,
            "route_tier": response.route_tier,
        }

    @staticmethod
    def _extract_mode(text: str) -> str | None:
        import re

        m = re.search(r"\[mode:([a-zA-Z]+)\]", text or "")
        if m:
            return m.group(1).lower()
        m = re.search(r"Mode=([a-zA-Z]+):", text or "")
        if m:
            return m.group(1).lower()
        return None

    @staticmethod
    def _teacher_lessons_for(agent_name: str, limit: int = 5) -> str:
        """Chief → specialist teaching: recent lessons from the experience journal."""
        try:
            from app.learning.experience import get_experience_journal

            rows = get_experience_journal().recent(limit=60)
        except Exception:
            return ""
        agent_l = (agent_name or "").lower()
        matched: list[str] = []
        general: list[str] = []
        for row in reversed(rows):
            kind = str(row.get("kind") or "")
            if kind not in {"success", "lesson", "error", "failure"}:
                continue
            title = str(row.get("title") or "").strip()
            detail = str(row.get("detail") or "").strip().replace("\n", " ")
            if not title and not detail:
                continue
            tip = f"- [{kind}] {title}: {detail[:220]}"
            meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
            meta_agent = str(meta.get("agent") or "").lower()
            if meta_agent and (meta_agent == agent_l or meta_agent in agent_l or agent_l in meta_agent):
                matched.append(tip)
            else:
                general.append(tip)
        tips = (matched + general)[:limit]
        return "\n".join(tips)

    @staticmethod
    def _is_ide_coding_turn(text: str) -> bool:
        t = text or ""
        markers = (
            "Spixa IDE coding agent",
            "chief IDE agent",
            "=== USER MESSAGE",
            "[mode:agent]",
            "[mode:edit]",
            "Mode=agent:",
            "Mode=edit:",
            "<<<SPIXA_EDIT",
            "Emit one fenced block per file",
        )
        return any(m in t for m in markers)

    @staticmethod
    def _evaluate_specialists(
        reports: list[dict[str, Any]],
        *,
        critic: dict[str, Any] | None,
        user_message: str,
    ) -> list[dict[str, Any]]:
        """Chief-teacher grades for each specialist — what worked, what stalled, what's next."""
        critic_l = (critic or {}).get("summary") or ""
        critic_l = critic_l.lower()
        out: list[dict[str, Any]] = []
        for r in reports:
            summary = str(r.get("summary") or "")
            s = summary.lower()
            agent = str(r.get("agent") or "unknown")
            score = 0.35
            solved: list[str] = []
            blocked: list[str] = []
            needs: list[str] = []
            if len(summary.strip()) >= 80:
                score += 0.15
                solved.append("produced a usable brief")
            if any(tok in s for tok in ("```", "path", "file", "ملف", "implement", "api", "route")):
                score += 0.2
                solved.append("named concrete artifacts/steps")
            if any(tok in s for tok in ("unclear", "need more", "missing", "غير واضح", "أحتاج", "ناقص")):
                score -= 0.15
                blocked.append("flagged missing information")
                needs.append("clarification from user or peers")
            if agent.lower() in critic_l and any(
                w in critic_l for w in ("risk", "weak", "wrong", "خطر", "ضعف", "خطأ")
            ):
                score -= 0.2
                blocked.append("critic raised concerns")
                needs.append("revise approach before apply")
            if r.get("simulated"):
                score -= 0.1
                blocked.append("simulated model path")
                needs.append("promote/owned model quality")
            score = max(0.05, min(0.98, round(score, 2)))
            if score >= 0.7 and not needs:
                needs.append("continue under master plan")
            if score < 0.5 and not needs:
                needs.append("more domain context or stronger model")
            out.append(
                {
                    "agent": agent,
                    "score": score,
                    "solved": "; ".join(solved) or "partial contribution",
                    "blocked": "; ".join(blocked) or "none",
                    "needs": "; ".join(needs),
                    "intent_hint": (user_message or "")[:120],
                }
            )
        return out

    @staticmethod
    def _looks_like_change(text: str) -> bool:
        t = text.lower()
        verbs = (
            "add",
            "fix",
            "implement",
            "create",
            "build",
            "refactor",
            "update",
            "أضف",
            "صلح",
            "ابني",
            "بني",
            "أنشئ",
            "اصنع",
            "طور",
            "تطبيق",
            "وثق",
            "وثّق",
        )
        return any(v in t for v in verbs)

    @staticmethod
    def _extract_path(text: str) -> str | None:
        import re

        match = re.search(r"([\w./\\-]+\.(?:py|ts|tsx|js|jsx|go|rs|java|cs|rb|php))", text)
        return match.group(1).replace("\\", "/") if match else None

    @staticmethod
    def _title(text: str) -> str:
        cleaned = " ".join(text.strip().split())
        return cleaned[:80] + ("…" if len(cleaned) > 80 else "")
