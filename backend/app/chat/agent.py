"""Cursor-like interactive chat — delegated to MasterConductor + specialists."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.master import MasterConductor
from app.db.models import AgentMessage, AgentSession, Project
from app.learning.experience import get_experience_journal
from app.memory import ProjectLongTermMemory
from app.ownership import get_ownership_handoff


class ChatAgentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_session(self, project_id: UUID, title: str | None = None) -> AgentSession:
        project = await self._project(project_id)
        cleaned = (title or "").strip()
        session = AgentSession(
            project_id=project.id,
            title=cleaned or "أمر جديد",
            status="active",
            meta={
                "mode": "cursor_like",
                "conductor": "MasterOrchestrator",
                "untitled": not bool(cleaned),
            },
        )
        self.session.add(session)
        await self.session.commit()
        await self.session.refresh(session)
        return session

    async def get_session(self, project_id: UUID, session_id: UUID) -> AgentSession | None:
        result = await self.session.execute(
            select(AgentSession)
            .where(
                AgentSession.id == session_id,
                AgentSession.project_id == project_id,
            )
            .options(selectinload(AgentSession.messages))
        )
        return result.scalar_one_or_none()

    async def list_sessions(
        self,
        project_id: UUID,
        *,
        status: str | None = None,
    ) -> list[AgentSession]:
        """List sessions. status: active | archived | all (default all non-deleted)."""
        q = select(AgentSession).where(AgentSession.project_id == project_id)
        wanted = (status or "all").strip().lower()
        if wanted == "active":
            q = q.where(AgentSession.status == "active")
        elif wanted == "archived":
            q = q.where(AgentSession.status == "archived")
        else:
            q = q.where(AgentSession.status != "deleted")
        result = await self.session.execute(
            q.order_by(AgentSession.updated_at.desc(), AgentSession.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_session(
        self,
        project_id: UUID,
        session_id: UUID,
        *,
        title: str | None = None,
        status: str | None = None,
    ) -> AgentSession:
        session = await self.get_session(project_id, session_id)
        if not session:
            raise ValueError("Session not found")
        if title is not None:
            cleaned = title.strip()
            if not cleaned:
                raise ValueError("Title required")
            session.title = cleaned[:255]
            meta = dict(session.meta or {})
            meta["untitled"] = False
            session.meta = meta
        if status is not None:
            cleaned_status = status.strip().lower()
            if cleaned_status not in {"active", "archived", "deleted"}:
                raise ValueError("Invalid status")
            session.status = cleaned_status
            meta = dict(session.meta or {})
            if cleaned_status == "archived":
                meta["archived_at"] = datetime.now(timezone.utc).isoformat()
            elif cleaned_status == "active":
                meta.pop("archived_at", None)
            session.meta = meta
        await self.session.commit()
        await self.session.refresh(session)
        return session

    async def archive_session(self, project_id: UUID, session_id: UUID) -> AgentSession:
        """Cursor-like: close tab → keep conversation in archive."""
        return await self.update_session(project_id, session_id, status="archived")

    async def unarchive_session(self, project_id: UUID, session_id: UUID) -> AgentSession:
        return await self.update_session(project_id, session_id, status="active")

    async def delete_session(self, project_id: UUID, session_id: UUID) -> None:
        session = await self.get_session(project_id, session_id)
        if not session:
            raise ValueError("Session not found")
        # Soft-delete so archive history stays recoverable if needed later
        session.status = "deleted"
        meta = dict(session.meta or {})
        meta["deleted_at"] = datetime.now(timezone.utc).isoformat()
        session.meta = meta
        await self.session.commit()

    async def purge_session(self, project_id: UUID, session_id: UUID) -> None:
        """Hard-delete session + messages (permanent archive removal)."""
        session = await self.get_session(project_id, session_id)
        if not session:
            raise ValueError("Session not found")
        await self.session.delete(session)
        await self.session.commit()

    async def get_resume_checkpoint(self, project_id: UUID, session_id: UUID) -> dict[str, Any] | None:
        session = await self.get_session(project_id, session_id)
        if not session:
            raise ValueError("Session not found")
        meta = dict(session.meta or {})
        cp = meta.get("resume_checkpoint")
        return dict(cp) if isinstance(cp, dict) and cp.get("user_topic") is not None else None

    async def set_resume_checkpoint(
        self,
        project_id: UUID,
        session_id: UUID,
        *,
        user_topic: str,
        partial_reply: str = "",
        attachments: list[str] | None = None,
        mode: str | None = None,
        preferred_provider: str | None = None,
        last_status: str = "aborted",
    ) -> dict[str, Any]:
        session = await self.get_session(project_id, session_id)
        if not session:
            raise ValueError("Session not found")
        meta = dict(session.meta or {})
        cp = {
            "user_topic": (user_topic or "")[:2000],
            "partial_reply": (partial_reply or "")[:12000],
            "attachments": list(attachments or [])[:12],
            "mode": mode,
            "preferred_provider": preferred_provider,
            "last_status": last_status,
            "aborted_at": datetime.now(timezone.utc).isoformat(),
        }
        meta["resume_checkpoint"] = cp
        meta["resume_hint"] = f"توقف عند: {cp['user_topic'][:120]}"
        session.meta = meta
        await self.session.commit()
        return cp

    async def clear_resume_checkpoint(self, project_id: UUID, session_id: UUID) -> None:
        session = await self.get_session(project_id, session_id)
        if not session:
            raise ValueError("Session not found")
        meta = dict(session.meta or {})
        if "resume_checkpoint" in meta:
            meta.pop("resume_checkpoint", None)
            session.meta = meta
            await self.session.commit()

    async def list_messages(self, project_id: UUID, session_id: UUID) -> list[AgentMessage]:
        session = await self.get_session(project_id, session_id)
        if not session:
            raise ValueError("Session not found")
        msgs = list(session.messages or [])
        msgs.sort(key=lambda m: m.created_at)
        return msgs

    _PLACEHOLDER_TITLES = frozenset(
        {
            "أمر جديد",
            "Agent",
            "Agent session",
            "New Agent",
            "New chat",
            "Chat",
            "Untitled",
            "أمر محفوظ",
        }
    )

    @staticmethod
    def _extract_user_topic(text: str) -> str:
        """Pull the real user ask out of IDE scaffold / mode wrappers."""
        raw = text or ""
        for marker in (
            "=== USER MESSAGE (reply in this language) ===",
            "=== USER MESSAGE ===",
            "طلب المستخدم:",
            "User request:",
            "User:",
            "طلب المستخدم",
        ):
            if marker in raw:
                raw = raw.split(marker)[-1]
                break
        # Drop common IDE preamble lines if marker missing
        lines = []
        for line in raw.splitlines():
            s = line.strip()
            if not s:
                continue
            if s.startswith("[mode:"):
                continue
            if s.startswith("أنت وكيل") or s.startswith("العقل الرئيس"):
                continue
            if s.startswith("You are the Spixa") or s.startswith("You are Spixa") or s.startswith("LANGUAGE (mandatory)"):
                continue
            if s.startswith("وضع الوكيل") or s.startswith("وضع السؤال") or s.startswith("وضع التعديل"):
                continue
            if s.startswith("Mode=agent") or s.startswith("Mode=ask") or s.startswith("Mode=edit"):
                continue
            if s.startswith("Execution first") or s.startswith("When creating or editing"):
                continue
            if s.startswith("Build / site") or s.startswith("Ask clarifying"):
                continue
            if s.startswith("شجرة المشروع") or s.startswith("ملف مفتوح") or s.startswith("لا ملف"):
                continue
            if s.startswith("Project tree") or s.startswith("Selected brain"):
                continue
            if s.startswith("الطلب يبدو") or s.startswith("عدّل فقط"):
                continue
            if s.startswith("User clearly asked") or s.startswith("Prefer improving"):
                continue
            if s.startswith("### ") or s.startswith("```"):
                continue
            lines.append(s)
        return " ".join(lines).strip() or (text or "").strip()

    @classmethod
    def _auto_title(cls, text: str) -> str:
        """Cursor-style short topic title from the user's first message."""
        topic = cls._extract_user_topic(text)
        topic = " ".join(topic.split())
        # Strip chatty prefixes so the tab reads as a subject
        for prefix in (
            "من فضلك ",
            "رجاءً ",
            "رجاءا ",
            "لو سمحت ",
            "أريد ",
            "ابي ",
            "أبغى ",
            "please ",
            "can you ",
            "could you ",
            "i want ",
            "i need ",
            "help me ",
        ):
            if topic.lower().startswith(prefix):
                topic = topic[len(prefix) :].lstrip("،, ")
                break
        if not topic:
            return "أمر جديد"
        # Prefer a compact subject window (Cursor ~28–40 visible chars)
        max_len = 48
        if len(topic) <= max_len:
            return topic
        cut = topic[: max_len - 1]
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        return cut.rstrip(".,،؛:") + "…"

    def _should_retitle(self, session: AgentSession, project: Project) -> bool:
        meta = dict(session.meta or {})
        if meta.get("untitled"):
            return True
        title = (session.title or "").strip()
        if title in self._PLACEHOLDER_TITLES:
            return True
        if title == f"Chat — {project.name}":
            return True
        return False

    async def chat(
        self,
        project_id: UUID,
        session_id: UUID,
        user_message: str,
        *,
        preferred_provider: str | None = None,
        preferred_agent: str | None = None,
        mode: str | None = None,
        attachments: list[str] | None = None,
        resume: bool = False,
        max_tokens_budget: int | None = None,
        max_seconds: int | None = None,
        allow_teacher: bool | None = True,
    ) -> dict[str, Any]:
        project = await self._project(project_id)
        session = await self.get_session(project_id, session_id)
        if not session:
            raise ValueError("Session not found")

        # Manual commands take priority: pause autonomous current while human drives
        from app.config import get_settings
        from app.autopilot import get_autopilot
        from app.agents.registry import get_agent_spec
        from app.gateway.catalog import resolve_chief_choice
        from app.gateway.request_context import (
            set_forbid_teacher,
            set_force_internal,
            set_preferred_model,
            set_preferred_provider,
            set_preferred_worker,
        )
        from app.workspace.files import read_text_file

        if get_settings().autopilot_pause_on_manual_chat:
            get_autopilot().pause_for_manual(reason="user_chat")

        chief = resolve_chief_choice(preferred_provider)
        provider = chief.get("preferred_provider")
        preferred_model = chief.get("preferred_model")

        chosen = (preferred_agent or "").strip() or None
        if chosen and chosen.lower() in {"auto", "automatic", ""}:
            chosen = None
        if chosen and not get_agent_spec(chosen):
            raise ValueError(f"Unknown agent: {chosen}")

        # Session usage / budget gate (per IDE tab)
        meta_pre = dict(session.meta or {})
        usage = dict(meta_pre.get("usage") or {})
        tokens_used = int(usage.get("tokens_in") or 0) + int(usage.get("tokens_out") or 0)
        started_at = usage.get("started_at")
        if not started_at:
            started_at = datetime.now(timezone.utc).isoformat()
            usage["started_at"] = started_at
        elapsed = 0.0
        try:
            started_dt = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
            elapsed = (datetime.now(timezone.utc) - started_dt.astimezone(timezone.utc)).total_seconds()
        except Exception:  # noqa: BLE001
            elapsed = 0.0
        budget_hit = False
        if max_tokens_budget is not None and tokens_used >= int(max_tokens_budget):
            budget_hit = True
        # Wall-clock budget is per request (stream timeout), not lifetime of the tab.
        # Cumulative elapsed was falsely gating every later turn on long-lived IDE tabs.
        forbid = allow_teacher is False or budget_hit
        set_forbid_teacher(forbid)
        set_force_internal(forbid)
        set_preferred_provider("internal" if forbid else provider)
        set_preferred_model(None if forbid else preferred_model)
        set_preferred_worker(chosen)

        enriched = user_message
        # Resume: inject prior partial so the model continues instead of restarting
        cp = meta_pre.get("resume_checkpoint") if resume else None
        if resume and isinstance(cp, dict):
            partial = str(cp.get("partial_reply") or "").strip()
            topic = str(cp.get("user_topic") or self._extract_user_topic(user_message))
            resume_block = (
                "هذا استئناف بعد إيقاف المستخدم.\n"
                f"الطلب الأصلي: {topic}\n"
                f"ما كُتب قبل الإيقاف:\n{partial or '(لا يوجد نص جزئي)'}\n"
                "أكمل من هذه النقطة دون إعادة ما تم، وادمج أي طلب متابعة جديد أدناه.\n"
            )
            enriched = f"{resume_block}\n---\nمتابعة المستخدم:\n{user_message}"

        attach_paths = [p.replace("\\", "/").lstrip("/") for p in (attachments or []) if p][:12]
        if attach_paths:
            blocks: list[str] = []
            for rel in attach_paths:
                try:
                    data = read_text_file(project.workspace_path, rel)
                except PermissionError:
                    blocks.append(f"### {rel}\n[permission denied]")
                    continue
                if not data.get("ok"):
                    blocks.append(f"### {rel}\n[{data.get('error') or 'unreadable'}]")
                    continue
                if data.get("kind") and data.get("kind") != "text":
                    blocks.append(
                        f"### {rel}\n[binary/media · kind={data.get('kind')} · size={data.get('size')}]"
                    )
                    continue
                content = str(data.get("content") or "")[:12000]
                blocks.append(f"### {rel}\n```\n{content}\n```")
            enriched = (
                f"{user_message}\n\n---\nAttached workspace files:\n" + "\n\n".join(blocks)
            )

        if mode:
            enriched = f"[mode:{mode}]\n{enriched}"

        meta = dict(session.meta or {})
        meta["last_user_message"] = user_message
        meta["preferred_provider"] = provider
        meta["preferred_model"] = preferred_model
        meta["chief_mode"] = chief.get("mode")
        meta["preferred_agent"] = chosen
        meta["attachments"] = attach_paths
        meta["mode"] = mode
        topic_source = self._extract_user_topic(user_message)
        meta["resume_hint"] = f"توقف عند: {topic_source[:120]}"
        meta["last_user_topic"] = topic_source[:500]
        meta["usage"] = usage
        meta["budget"] = {
            "max_tokens": max_tokens_budget,
            "max_seconds": max_seconds,
            "allow_teacher": allow_teacher is not False,
            "budget_hit": budget_hit,
        }
        if self._should_retitle(session, project):
            session.title = self._auto_title(user_message)
            meta["untitled"] = False
            meta["title_source"] = "auto_topic"
        session.meta = meta

        self.session.add(
            AgentMessage(
                session_id=session.id,
                role="user",
                content=user_message,
                tool_payload={
                    "preferred_provider": provider,
                    "preferred_model": preferred_model,
                    "chief_mode": chief.get("mode"),
                    "preferred_agent": chosen,
                    "attachments": attach_paths,
                    "mode": mode,
                    "display_text": topic_source[:2000],
                },
            )
        )
        ltm = ProjectLongTermMemory(self.session)
        # Store ONLY the real user ask — never the IDE scaffold wrapper (pollutes recall)
        memory_user = (topic_source or self._extract_user_topic(user_message) or "").strip()
        if memory_user:
            await ltm.remember_utterance(
                project.id,
                role="user",
                content=memory_user[:4000],
                session_id=session.id,
            )
        # Commit BEFORE the long model call so SQLite releases the write lock.
        # Otherwise opening a new tab/session while AI runs blocks forever.
        await self.session.commit()
        session_title = session.title
        project_id_str = str(project.id)
        sid = session.id

        result = await MasterConductor(self.session).handle(
            project,
            user_message=enriched,
            session_id=sid,
            preferred_agent=chosen,
            mode=mode,
        )

        evaluations = result.get("evaluations") if isinstance(result.get("evaluations"), list) else []
        # User-facing decision stays clean; grades/specialists stay internal in tool_payload only.
        decision_log = {
            "intent": result.get("intent"),
            "intent_label": result.get("intent_label"),
            "conductor": result.get("conductor") or "MasterOrchestrator",
            "route_tier": result.get("route_tier"),
            "model": result.get("model"),
            "simulated": bool(result.get("simulated")),
            "why": f"execute · {result.get('intent') or 'auto'}",
            "files_hint": [
                p
                for p in (
                    list(attach_paths)
                    + list((result.get("proposal") or {}).get("files") or [])
                )
                if p
            ][:20],
        }
        internal_grades = {
            "specialists": result.get("specialists") or [],
            "tools_used": result.get("tools_used") or [],
            "evaluations": evaluations,
        }
        self.session.add(
            AgentMessage(
                session_id=sid,
                role="assistant",
                content=result["reply"],
                tool_payload={
                    "conductor": result.get("conductor"),
                    "intent": result.get("intent"),
                    "intent_label": result.get("intent_label"),
                    "model": result.get("model"),
                    "simulated": bool(result.get("simulated")),
                    "proposal": result.get("proposal"),
                    "memory_binding": result.get("memory_binding"),
                    "route_tier": result.get("route_tier"),
                    "decision_log": decision_log,
                    "internal": internal_grades,
                },
            )
        )
        from app.memory.pollution import is_pollution_text, strip_pollution

        reply_text = result["reply"] or ""
        clean_reply = strip_pollution(reply_text) or ""
        if clean_reply and not is_pollution_text(clean_reply):
            await ltm.remember_utterance(
                project.id,
                role="assistant",
                content=clean_reply[:6000],
                session_id=sid,
                meta={"intent": result.get("intent"), "conductor": result.get("conductor")},
            )
        # Learn from everything: successes fuel students; failures/errors become lessons
        journal = get_experience_journal()
        is_error = reply_text.startswith("[provider-error") or bool(result.get("error"))
        polluted = is_pollution_text(reply_text) or (not clean_reply and bool(reply_text.strip()))
        specialty = "coding" if result.get("intent") == "implement" else "reasoning"
        if is_error:
            experience = journal.record_error(
                title="Chat provider/tool error",
                detail=f"User: {memory_user[:500]}\nReply: {reply_text[:1500]}",
                specialty=specialty,
                project_id=project_id_str,
                meta={"intent": result.get("intent")},
            )
            handoff = {"accepted": False, "reason": "logged_as_error_lesson"}
        elif polluted:
            experience = journal.record_error(
                title="Prompt-pollution reply blocked from distill",
                detail=f"User: {memory_user[:400]}\nPolluted reply skipped",
                specialty=specialty,
                project_id=project_id_str,
                meta={"pollution": True},
            )
            handoff = {"accepted": False, "reason": "prompt_pollution"}
        else:
            learn_user = (memory_user or topic_source or "")[:2000]
            learn_reply = clean_reply[:4000]
            experience = journal.record_success(
                title="Chat success",
                detail=f"User: {learn_user[:400]}\nReply: {learn_reply[:1200]}",
                specialty=specialty,
                project_id=project_id_str,
                meta={"simulated": bool(result.get("simulated"))},
            )
            handoff = get_ownership_handoff().absorb_chat_turn(
                user_message=learn_user,
                reply=learn_reply,
                intent=result.get("intent"),
                project_id=project_id_str,
                simulated=bool(result.get("simulated")),
            )
        # Refresh usage + clear resume checkpoint after a finished turn
        session = await self.get_session(project_id, sid)
        if session:
            meta2 = dict(session.meta or {})
            usage2 = dict(meta2.get("usage") or usage)
            tin = int(result.get("tokens_in") or 0)
            tout = int(result.get("tokens_out") or 0)
            if tin + tout <= 0:
                # Estimate when providers omit usage
                tout = max(1, len(reply_text) // 4)
                tin = max(1, len(user_message) // 4)
            usage2["tokens_in"] = int(usage2.get("tokens_in") or 0) + tin
            usage2["tokens_out"] = int(usage2.get("tokens_out") or 0) + tout
            usage2["turns"] = int(usage2.get("turns") or 0) + 1
            usage2["started_at"] = usage2.get("started_at") or started_at
            usage2["updated_at"] = datetime.now(timezone.utc).isoformat()
            meta2["usage"] = usage2
            meta2.pop("resume_checkpoint", None)
            # Persist numbered menus so short replies ("4", "ja") stay grounded
            offered = result.get("last_offered_options")
            if isinstance(offered, dict) and offered:
                meta2["last_offered_options"] = {
                    str(k): str(v)[:400] for k, v in offered.items() if str(v).strip()
                }
            session.meta = meta2
            session_title = session.title or session_title
        if budget_hit and reply_text:
            topic_lang = topic_source or user_message
            if any("\u0600" <= ch <= "\u06FF" for ch in topic_lang):
                budget_note = (
                    "⚠ تم تقييد هذا التبويب (سقف توكنز/وقت) — المتابعة بالمسار الداخلي.\n\n"
                )
            elif any(
                w in topic_lang.lower()
                for w in ("ich", "mir", "bau", "bitte", "und", "eine", "app", "projekt")
            ) or any(ch in topic_lang.lower() for ch in "äöüß"):
                budget_note = (
                    "⚠ Tab-Limit (Tokens/Zeit) erreicht — Weiter intern ohne externe Eskalation.\n\n"
                )
            else:
                budget_note = (
                    "⚠ This tab hit its token/time budget — continuing on the internal path.\n\n"
                )
            reply_text = budget_note + reply_text
            # Keep stored message aligned with returned reply
            if session:
                # last assistant message content already added; patch via new note only in return
                pass
        await self.session.commit()

        return {
            "session_id": str(sid),
            "reply": reply_text if budget_hit else result["reply"],
            "proposal": result.get("proposal"),
            "tools_used": result.get("tools_used") or [],
            "model": result.get("model"),
            "simulated": bool(result.get("simulated")),
            "route_tier": result.get("route_tier"),
            "intent": result.get("intent"),
            "intent_label": result.get("intent_label"),
            "specialists": result.get("specialists") or [],
            "conductor": result.get("conductor"),
            "memory_binding": result.get("memory_binding"),
            "handoff": handoff,
            "experience": experience,
            "session_title": session_title,
            "budget_hit": budget_hit,
            "usage": (session.meta or {}).get("usage") if session else usage,
            "decision": decision_log,
        }

    async def _project(self, project_id: UUID) -> Project:
        result = await self.session.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError("Project not found")
        return project
