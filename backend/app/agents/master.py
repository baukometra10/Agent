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

        try:
            from app.gateway.request_context import emit_agent_status

            emit_agent_status("reading", "Reading project…")
        except Exception:  # noqa: BLE001
            pass
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

        from app.memory.pollution import is_pollution_text, strip_pollution

        raw_reply = str(synthesis.get("content") or "")
        clean_reply = strip_pollution(raw_reply)
        if not clean_reply or is_pollution_text(clean_reply) or is_pollution_text(raw_reply):
            # Never show scaffold echo to the user — fall back to a short grounded plan
            tree = (context.get("files") or {}).get("files") or []
            hint = ", ".join(str(p) for p in list(tree)[:8]) if isinstance(tree, list) else ""
            um = user_message or ""
            if any("\u0600" <= ch <= "\u06FF" for ch in um):
                clean_reply = (
                    f"فهمت — نكمل على المشروع"
                    f"{f' ({hint})' if hint else ''}.\n"
                    "1) نراجع الملفات ذات الصلة\n"
                    "2) ننفّذ أصغر تغيير مفيد\n"
                    "3) نتحقق بسرعة\n"
                    "بماذا نبدأ؟"
                )
            elif any(
                w in um.lower()
                for w in ("ich", "wir", "bitte", "machen", "können", "projekt", "und", "app", "bau")
            ) or any(ch in um.lower() for ch in "äöüß"):
                clean_reply = (
                    f"Verstanden — wir arbeiten im Projekt weiter"
                    f"{f' ({hint})' if hint else ''}.\n"
                    "1) Ist-Zustand der relevanten Dateien prüfen\n"
                    "2) Kleinste sinnvolle Änderung umsetzen\n"
                    "3) Kurz prüfen\n"
                    "Womit sollen wir starten?"
                )
            else:
                clean_reply = (
                    f"Understood — we'll continue in the project"
                    f"{f' ({hint})' if hint else ''}.\n"
                    "1) Review the relevant files\n"
                    "2) Make the smallest useful change\n"
                    "3) Quick check\n"
                    "Where should we start?"
                )

        offered = self._parse_offered_options(clean_reply)
        return {
            "reply": clean_reply,
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
            "last_offered_options": offered,
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
        files = tools.list_files(".", limit=80)
        snapshot = tools.workspace_snapshot(file_limit=80)
        path_hint = self._extract_path(user_message)
        file_snippet = tools.read_file(path_hint) if path_hint else None
        memory = await ProjectLongTermMemory(self.session).recall(
            project.id, session_id=session_id
        )
        # Durable option menu from prior assistant turn (session.meta)
        if session_id and isinstance(memory, dict):
            try:
                from sqlalchemy import select

                from app.db.models import AgentSession

                res = await self.session.execute(
                    select(AgentSession).where(
                        AgentSession.id == session_id,
                        AgentSession.project_id == project.id,
                    )
                )
                sess = res.scalar_one_or_none()
                meta = dict(sess.meta or {}) if sess else {}
                offered = meta.get("last_offered_options")
                if isinstance(offered, dict) and offered:
                    memory["last_offered_options"] = {
                        str(k): str(v)[:400] for k, v in offered.items() if str(v).strip()
                    }
            except Exception:  # noqa: BLE001
                pass
        return {
            "knowledge": knowledge,
            "roadmap": roadmap,
            "files": files,
            "workspace_snapshot": snapshot,
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
        from app.memory.pollution import is_pollution_text, strip_pollution

        semantic_hits_raw = ((mem.get("semantic") or {}).get("hits") or [])[:12]
        semantic_hits = []
        for h in semantic_hits_raw:
            chunk = strip_pollution(str(h.get("text") or ""))
            if not chunk or is_pollution_text(chunk):
                continue
            semantic_hits.append(chunk[:180])
            if len(semantic_hits) >= 4:
                break
        semantic_txt = "\n".join(f"- {t}" for t in semantic_hits)
        standing_clean = []
        for s in standing[:10]:
            chunk = strip_pollution(str(s.get("content") or ""))
            if chunk and not is_pollution_text(chunk):
                standing_clean.append(chunk[:220])
        standing_txt = "\n".join(f"- {t}" for t in standing_clean)

        # Prefer this chat session's messages; fall back to project transcript.
        history_rows = mem.get("session_history") or mem.get("transcript") or []
        if not isinstance(history_rows, list):
            history_rows = []
        chat_block = self._format_recent_chat(history_rows, limit=10)
        offered_options = mem.get("last_offered_options") if isinstance(mem.get("last_offered_options"), dict) else {}
        # Short replies like "4" / "ja" must resolve against the last assistant options.
        effective_user = self._expand_short_choice(
            user_message,
            history_rows,
            offered_options=offered_options,
        )

        tree = context.get("files") or {}
        snap = context.get("workspace_snapshot") if isinstance(context.get("workspace_snapshot"), dict) else {}
        file_names = tree.get("files") or tree.get("paths") or snap.get("files") or []
        if isinstance(file_names, list):
            tree_hint = ", ".join(str(p) for p in file_names[:60]) or "(empty workspace)"
        else:
            tree_hint = str(tree.get("entries") or tree)[:1200]
        top_dirs = snap.get("top_dirs") if isinstance(snap.get("top_dirs"), list) else []
        top_files = snap.get("top_files") if isinstance(snap.get("top_files"), list) else []
        workspace_abs = str(
            snap.get("workspace_path")
            or binding.get("workspace_path")
            or project.workspace_path
            or ""
        )
        mvp_path = "docs/MVP.md" if "docs" in {str(d).lower() for d in top_dirs} else "MVP.md"
        top_block = ""
        if top_dirs or top_files:
            top_block = (
                f"Top-level folders: {', '.join(str(d) for d in top_dirs[:30]) or '(none)'}\n"
                f"Top-level files: {', '.join(str(f) for f in top_files[:30]) or '(none)'}\n"
            )
        key_files = snap.get("key_files") if isinstance(snap.get("key_files"), dict) else {}
        key_block = ""
        for kname in ("README.md", "VISION.md", "package.json", "pyproject.toml"):
            body = key_files.get(kname)
            if body:
                key_block += f"\n--- {kname} (from bound workspace) ---\n{body}\n"
        offered_block = ""
        if offered_options:
            lines = [f"{k}. {v}" for k, v in sorted(offered_options.items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdigit() else 99)]
            offered_block = "LAST OFFERED OPTIONS (user may answer with a number):\n" + "\n".join(lines) + "\n"
        snippet = context.get("file_snippet") if isinstance(context.get("file_snippet"), dict) else None
        snippet_block = ""
        if snippet and snippet.get("content") and not snippet.get("error"):
            spath = str(snippet.get("path") or context.get("path_hint") or "file")
            snippet_block = (
                f"\nCURRENT FILE `{spath}` (edit from this — Spixa IDE will apply your fence):\n"
                f"```{spath}\n{str(snippet.get('content'))[:8000]}\n```\n"
            )
        elif context.get("path_hint"):
            # Still tell the model the target path even if read failed
            snippet_block = f"\nTarget file path: {context.get('path_hint')}\n"
        if ide_coding:
            try:
                from app.gateway.request_context import emit_agent_status

                emit_agent_status("planning", "Planning next steps…")
            except Exception:  # noqa: BLE001
                pass
            choice_exec = self._is_expanded_choice(effective_user)
            planning_choice = choice_exec and self._choice_is_planning(effective_user)
            prompt = (
                "You are Spixa — talk like a sharp senior teammate in Cursor Chat "
                "(calm, direct, zero corporate filler).\n"
                f"Project name: {project.name}\n"
                f"BOUND WORKSPACE (absolute, THIS is the only project): {workspace_abs}\n"
                f"{top_block}"
                f"Sample paths inside that folder: {tree_hint}\n"
                f"{key_block}"
                f"{offered_block}"
                f"Standing goals/instructions: {standing_txt or '(none)'}\n"
                f"Memory hits: {semantic_txt or '(none)'}\n"
                f"{snippet_block}"
                "RECENT CHAT (same Spixa tab — this IS the conversation memory):\n"
                f"{chat_block or '(no prior turns)'}\n\n"
                f"USER (latest):\n{effective_user}\n\n"
                "REPLY (mandatory — professional Cursor style):\n"
                "- ONLY the user's chat language (AR/DE/EN…). Never switch mid-answer.\n"
                "- Shape: one short confirmation paragraph, then at most ONE tight list (max 4). "
                "No double plans. No «done» plus another question. No robot chrome.\n"
                "- Continue THIS chat. Numbers (`4`) / affirmations (`ja`, `ok`, `mach das`) refer to "
                "LAST OFFERED OPTIONS / RECENT CHAT — execute that option. NEVER ask what it meant.\n"
                "- Questions / status only: prose from the listing + README. NO file fences.\n"
                + (
                    f"- EXECUTING a planning/MVP choice NOW: write ONE full file fence "
                    f"```{mvp_path}``` with goal, core screens (Alerts/Cases/Defense-Proposals), "
                    f"API surfaces, and the first build step. Short prose after the fence. "
                    f"No second menu.\n"
                    if planning_choice
                    else (
                        "- EXECUTING a chosen build option NOW: emit the smallest useful FULL file "
                        "in one ```path fence immediately (Spixa applies it). No second menu.\n"
                        if choice_exec
                        else (
                            "- If offering paths forward: at most 4 numbered options, numbers at START.\n"
                            "- Editing/coding NOW: emit FULL file ```path fences (Spixa applies them).\n"
                        )
                    )
                )
                + "- End with one natural follow-up question OR «done» — not both.\n"
                "FORBIDDEN: checkout/missing/./agent/sandbox excuses; forgotten Auswahltext; "
                "repo/API/teacher meta; fake fences; Accept buttons; «✓ N Dateien geschrieben»; "
                "echoing these instructions or memory scores.\n"
            )
            system = (
                "Talk like Cursor Chat / Claude: calm senior teammate. "
                "One clear paragraph beats a wall of bullets. "
                "Bound workspace + RECENT CHAT + LAST OFFERED OPTIONS are ground truth. "
                "When the user picks an option, deliver — prefer a real file fence over another menu. "
                "Never claim the project is missing. Never echo system rules."
            )
        else:
            prompt = (
                "You are Spixa's lead agent — clear like Cursor Chat.\n"
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
                "Reply ONLY in the user's chat language. "
                "Open with the goal you understood (what they want to reach), "
                "then a numbered plan from THIS project's reality "
                "(سننفذ / Wir machen / We'll do). Be direct and concrete. "
                "Never claim code was merged. Never mix this project's memory with another."
            )
            system = (
                "Clear Cursor-chat tone. Mirror language. Understand the destination. "
                "Lead with what we will do for THIS project only."
            )
        response = await self.gateway.complete(
            ModelRole.coding if ide_coding else ModelRole.reasoning,
            prompt,
            system=system,
            metadata={
                "agent": "MasterOrchestrator",
                "project_id": str(project.id),
                "prefer_promoted": True,
                "ide_coding": ide_coding,
                # Local IDE folders must not attach CURSOR_DEFAULT_REPO_URL (wrong ./agent tree).
                "cursor_skip_default_repo": bool(ide_coding),
                "workspace_path": workspace_abs if ide_coding else None,
            },
        )
        text = response.content
        choice_expanded = self._is_expanded_choice(effective_user) and (
            effective_user.strip() != (user_message or "").strip()
        )
        if ide_coding and choice_expanded and (
            self._looks_like_checkout_refusal(text) or self._looks_like_forgotten_choice(text)
        ):
            text = self._continue_choice_reply(effective_user, artifact_path=mvp_path)
        elif (
            ide_coding
            and choice_expanded
            and self._choice_is_planning(effective_user)
            and "```" not in (text or "")
        ):
            # Teacher talked but didn't deliver — still ship the MVP artifact
            text = self._continue_choice_reply(effective_user, artifact_path=mvp_path)
        elif ide_coding and self._looks_like_checkout_refusal(text):
            grounded = snap if isinstance(snap, dict) else {}
            if not (grounded.get("workspace_path") or grounded.get("top_dirs")):
                grounded = {
                    "project_name": project.name,
                    "workspace_path": workspace_abs or project.workspace_path,
                    "top_dirs": [],
                    "top_files": [],
                    "key_files": {},
                }
            text = self._grounded_workspace_reply(user_message, grounded)
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
    def _looks_like_checkout_refusal(text: str) -> bool:
        t = (text or "").lower()
        if not t.strip():
            return False
        needles = (
            "./agent",
            "kein repository",
            "keinen repository",
            "kein checkout",
            "keinen checkout",
            "ausgechecktes repository",
            "ohne ausgecheckt",
            "no repository",
            "no project checkout",
            "without a checkout",
            "nicht seriös lesen",
            "nicht einsehen",
            "nicht bewerten",
            "repository-zugriff",
            "repository access",
            "start this agent from",
            "start den agent",
            "starte den agenten",
            "umgebung mit projekt-checkout",
            "cursor.com/agents",
            "cursor-workspace",
            "available workspace",
            "not present in the available workspace",
            "läuft ohne",
            "session läuft ohne",
        )
        return any(n in t for n in needles)

    @staticmethod
    def _grounded_workspace_reply(user_message: str, snap: dict[str, Any]) -> str:
        """Human overview from the bound local folder when Cursor refuses checkout."""
        import re

        name = str(snap.get("project_name") or "Projekt")
        path = str(snap.get("workspace_path") or snap.get("root") or "")
        dirs = [str(d) for d in (snap.get("top_dirs") or [])[:12]]
        files = [str(f) for f in (snap.get("top_files") or [])[:12]]
        readme = ""
        keys = snap.get("key_files") if isinstance(snap.get("key_files"), dict) else {}
        if keys.get("README.md"):
            # First meaningful non-heading line
            for line in str(keys["README.md"]).splitlines():
                s = line.strip()
                if s and not s.startswith("#"):
                    readme = s[:180]
                    break
        msg = user_message or ""
        if re.search(r"[\u0600-\u06FF]", msg):
            lang = "ar"
        elif re.search(
            r"\b(ich|du|das|projekt|schau|bitte|wie|was|und|erstmal)\b", msg, re.I
        ) or re.search(r"[äöüß]", msg, re.I):
            lang = "de"
        else:
            lang = "en"

        dir_txt = ", ".join(dirs) if dirs else "—"
        file_txt = ", ".join(files) if files else "—"
        if lang == "de":
            bits = [
                f"Kurz der Stand von **{name}** — Ordner `{path}` ist gebunden und lesbar.",
                f"Oben liegen u. a. die Ordner: {dir_txt}.",
                f"Wichtige Dateien oben: {file_txt}.",
            ]
            if readme:
                bits.append(f"README sagt sinngemäß: {readme}")
            bits.append(
                "Das ist ein volles App-/Backend-/Deploy-Setup, kein leeres Checkout. "
                "Soll ich als Nächstes die Architektur skizzieren oder die App-UI anschauen?"
            )
            return "\n\n".join(bits)
        if lang == "ar":
            bits = [
                f"وضع **{name}** باختصار — المجلد `{path}` مربوط ومقروء.",
                f"المجلدات الظاهرة: {dir_txt}.",
                f"ملفات مهمة فوق: {file_txt}.",
            ]
            if readme:
                bits.append(f"الـ README يقول تقريباً: {readme}")
            bits.append(
                "هذا مشروع كامل (واجهة/Backend/Deploy)، مو checkout فاضي. "
                "تبي بعدها ملخص المعمارية ولا نركز على الواجهة؟"
            )
            return "\n\n".join(bits)
        bits = [
            f"Here's **{name}** at a glance — `{path}` is bound and readable.",
            f"Top folders: {dir_txt}.",
            f"Top files: {file_txt}.",
        ]
        if readme:
            bits.append(f"README roughly says: {readme}")
        bits.append(
            "This is a full app/backend/deploy layout, not an empty checkout. "
            "Want architecture next, or should we look at the app UI?"
        )
        return "\n\n".join(bits)

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
    def _format_recent_chat(history: list[Any], *, limit: int = 10) -> str:
        from app.memory.pollution import is_pollution_text, strip_pollution

        rows: list[str] = []
        for row in history[-limit:]:
            if not isinstance(row, dict):
                continue
            role = str(row.get("role") or "user").strip().lower() or "user"
            if role not in {"user", "assistant", "system"}:
                role = "user"
            raw = str(row.get("content") or row.get("text") or "")
            chunk = strip_pollution(raw) or ""
            if not chunk or is_pollution_text(chunk):
                continue
            # Keep enough of assistant option lists so "4" can be resolved
            max_len = 2200 if role == "assistant" else 800
            rows.append(f"{role}: {chunk[:max_len]}")
        return "\n".join(rows)

    @classmethod
    def _expand_short_choice(
        cls,
        user_message: str,
        history: list[Any],
        *,
        offered_options: dict[str, Any] | None = None,
    ) -> str:
        """Map bare «4» / «ja» onto the last assistant numbered option text."""
        import re

        raw = (user_message or "").strip()
        bare = re.sub(r"^\[mode:[^\]]+\]\s*", "", raw, flags=re.I).strip()
        bare = re.sub(r"^Mode=[a-zA-Z]+:\s*", "", bare, flags=re.I).strip()
        offered = {
            str(k): str(v).strip()
            for k, v in (offered_options or {}).items()
            if str(v).strip()
        }

        num: str | None = None
        m = re.match(r"^([1-9]|10)\s*[.)]?\s*$", bare)
        if m:
            num = m.group(1)
        else:
            m2 = re.match(
                r"^(?:option|punkt|nr\.?|number|رقم|اختيار)\s*([1-9]|10)\s*[.)]?\s*$",
                bare,
                flags=re.I,
            )
            if m2:
                num = m2.group(1)
            elif re.match(
                r"^(ja|j|ok|okay|yes|yep|y|mach\s*das|mach\s*weiter|weiter|los|"
                r"go|do\s*it|نعم|ايوة|أيوة|يلا|تمام|موافق)\s*[.!؟?]?\s*$",
                bare,
                flags=re.I,
            ):
                # Affirmation → last offered option (highest number) or last history option
                if offered:
                    num = sorted(offered.keys(), key=lambda k: int(k) if k.isdigit() else 0)[-1]
                else:
                    num = cls._last_option_number_from_history(history)

        if not num:
            return user_message

        option_line = offered.get(num) or ""
        if not option_line:
            for row in reversed(history):
                if not isinstance(row, dict):
                    continue
                if str(row.get("role") or "").lower() != "assistant":
                    continue
                content = str(row.get("content") or row.get("text") or "")
                for line in content.splitlines():
                    if re.match(rf"^\s*{re.escape(num)}\s*[.)\-–—:]\s+\S", line):
                        option_line = line.strip()
                        break
                if option_line:
                    break
        if not option_line:
            return user_message

        # Normalize "4. text" → keep full line for prompts
        if not re.match(rf"^\s*{re.escape(num)}\s*[.)]", option_line):
            option_line = f"{num}. {option_line}"

        blob = option_line + " " + raw
        if re.search(r"[\u0600-\u06FF]", blob):
            return (
                f"أختار النقطة {num}: {option_line}\n\n"
                "نفّذ هذا الخيار الآن — اكتب الملف المطلوب فوراً، ولا تسألني ماذا تعني."
            )
        if re.search(
            r"\b(ich|du|die|der|das|und|produkt|mvp|backend|frontend|ja|weiter)\b",
            blob,
            re.I,
        ) or re.search(r"[äöüß]", blob, re.I):
            return (
                f"Ich wähle Option {num}: {option_line}\n\n"
                "Setze genau diesen Punkt jetzt um — liefere die Datei(en) sofort, "
                "frage nicht nach, worum es geht."
            )
        return (
            f"I choose option {num}: {option_line}\n\n"
            "Do that next step now — emit the file(s) immediately; "
            "do not ask what the number meant."
        )

    @staticmethod
    def _last_option_number_from_history(history: list[Any]) -> str | None:
        import re

        for row in reversed(history):
            if not isinstance(row, dict):
                continue
            if str(row.get("role") or "").lower() != "assistant":
                continue
            nums: list[int] = []
            for line in str(row.get("content") or "").splitlines():
                m = re.match(r"^\s*([1-9]|10)\s*[.)\-–—:]\s+\S", line)
                if m:
                    nums.append(int(m.group(1)))
            if nums:
                return str(max(nums))
        return None

    @staticmethod
    def _parse_offered_options(text: str) -> dict[str, str]:
        import re

        out: dict[str, str] = {}
        for line in (text or "").splitlines():
            m = re.match(r"^\s*([1-9]|10)\s*[.)\-–—:]\s+(\S.+)$", line.strip())
            if not m:
                continue
            out[m.group(1)] = m.group(2).strip()[:400]
        return out

    @staticmethod
    def _choice_is_planning(text: str) -> bool:
        import re

        return bool(
            re.search(
                r"\b(mvp|produkt|product|dashboard|plan|roadmap|vision|scope)\b",
                text or "",
                re.I,
            )
        )

    @staticmethod
    def _looks_like_forgotten_choice(text: str) -> bool:
        t = (text or "").lower()
        needles = (
            "auswahltext",
            "vorherige auswahl",
            "fehlt der vorherige",
            "mir fehlt",
            "wofür '4'",
            'wofür "4"',
            "wofur",
            "what the number meant",
            "what '4' stood",
            "what \"4\" stood",
            "sag mir kurz, wofür",
            "missing the previous",
            "projekt-roadmap oder",
        )
        return any(n in t for n in needles)

    @staticmethod
    def _is_expanded_choice(text: str) -> bool:
        import re

        t = (text or "").lower()
        return bool(
            re.search(r"(ich w[aä]hle option|i choose option|أختار النقطة)", t)
        )

    @classmethod
    def _continue_choice_reply(
        cls,
        effective_user: str,
        *,
        artifact_path: str = "docs/MVP.md",
    ) -> str:
        """Follow through when Cursor refuses — prose + real file fence for IDE apply."""
        import re

        lines = [ln.strip() for ln in (effective_user or "").splitlines() if ln.strip()]
        head = lines[0] if lines else (effective_user or "").strip()
        m = re.match(
            r"^(?:Ich wähle Option|I choose option|أختار النقطة)\s*\d+\s*:\s*(.+)$",
            head,
            flags=re.I,
        )
        option = (m.group(1).strip() if m else head)[:240]
        path = (artifact_path or "MVP.md").replace("\\", "/").lstrip("/")
        planning = cls._choice_is_planning(effective_user) or cls._choice_is_planning(option)

        if planning:
            body = (
                f"# MVP\n\n"
                f"## Goal\n{option}\n\n"
                f"## Core screens\n"
                f"- Alerts inbox & detail\n"
                f"- Cases / investigation timeline\n"
                f"- Defense proposals & approvals\n\n"
                f"## API surfaces (first cut)\n"
                f"- `GET /alerts`, `GET /alerts/{{id}}`\n"
                f"- `GET|POST /cases`, case timeline events\n"
                f"- `GET|POST /defense-proposals` + approve/reject\n\n"
                f"## First build step\n"
                f"1. Skeleton Security Operations Dashboard shell\n"
                f"2. Wire Alerts list to existing backend/demo data\n"
                f"3. Case detail stub + proposal panel\n"
            )
            fence = f"```{path}\n{body}```"
            if re.search(r"[\u0600-\u06FF]", effective_user or ""):
                return (
                    f"تمام — نكمل على هذا الخيار:\n{option}\n\n"
                    f"كتبت مسودة الـ MVP في `{path}`.\n\n{fence}\n\n"
                    "تبعد نربط الواجهة ولا نكمّل الـ API؟"
                )
            if re.search(r"[äöüß]|wähle|produkt|mvp|backend|frontend", effective_user or "", re.I):
                return (
                    f"Alles klar — wir nehmen genau das:\n{option}\n\n"
                    f"Ich lege den MVP-Schnitt in `{path}` ab.\n\n{fence}\n\n"
                    "Als Nächstes Dashboard-UI verdrahten oder API-Schnitt zuerst?"
                )
            return (
                f"Got it — we go with:\n{option}\n\n"
                f"I wrote the MVP cut to `{path}`.\n\n{fence}\n\n"
                "Next: wire the dashboard UI, or deepen the API surface?"
            )

        # Non-planning: short commit + ask for the smallest file if teacher failed hard
        if re.search(r"[\u0600-\u06FF]", effective_user or ""):
            return (
                f"تمام — نكمل:\n{option}\n\n"
                "أقولك أصغر تغيير ملف مفيد وأطبّقه مباشرة في الرد الجاي."
            )
        if re.search(r"[äöüß]|wähle|backend|frontend|qualität|qualitaet", effective_user or "", re.I):
            return (
                f"Alles klar — wir machen:\n{option}\n\n"
                "Als Nächstes setze ich die kleinste sinnvolle Dateiänderung um."
            )
        return (
            f"Got it — focusing on:\n{option}\n\n"
            "Next I'll apply the smallest useful file change."
        )

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
