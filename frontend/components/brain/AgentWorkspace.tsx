"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { API_URL } from "@/lib/api";
import { spendTokens } from "@/lib/billing";
import { hasFeature, hasTokens, loadUser } from "@/lib/user";
import type { Project } from "@/lib/types";
import { CodeStream } from "./CodeStream";
import { NeuralNet } from "./NeuralNet";
import { ThinkingStream } from "./ThinkingStream";
import { useAgentLive } from "@/hooks/useAgentLive";

type Props = {
  projects: Project[];
  initialProjectId?: string;
};

type ChatSession = {
  id: string;
  title: string;
  status: string;
  created_at?: string;
};

type ThreadMsg = {
  role: "user" | "assistant";
  text: string;
  intent?: string | null;
  intent_label?: string | null;
  proposal_id?: string | null;
};

function draftKey(projectId: string, sessionId: string | null) {
  return `spixa.chat.draft.${projectId}.${sessionId || "new"}`;
}

function titleFromText(text: string) {
  const line = text.trim().split(/\r?\n/)[0] || "أمر محفوظ";
  return line.length > 72 ? `${line.slice(0, 72)}…` : line;
}

export function AgentWorkspace({ projects, initialProjectId }: Props) {
  const [projectId, setProjectId] = useState(initialProjectId || projects[0]?.id || "");
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionTitle, setSessionTitle] = useState("أمر جديد");
  const [renaming, setRenaming] = useState(false);
  const [message, setMessage] = useState("");
  const [thread, setThread] = useState<ThreadMsg[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const { events, focus, connected, codeEvents, thinkEvents, intensity } = useAgentLive(
    projectId || undefined,
  );

  const loadSessions = useCallback(async (pid: string) => {
    try {
      const res = await fetch(`${API_URL}/api/projects/${pid}/chat/sessions`, {
        cache: "no-store",
      });
      if (!res.ok) return [];
      const rows = (await res.json()) as ChatSession[];
      setSessions(rows);
      return rows;
    } catch {
      setSessions([]);
      return [];
    }
  }, []);

  const loadMessages = useCallback(async (pid: string, sid: string) => {
    try {
      const res = await fetch(
        `${API_URL}/api/projects/${pid}/chat/sessions/${sid}/messages`,
        { cache: "no-store" },
      );
      if (!res.ok) {
        setThread([]);
        return;
      }
      const rows = (await res.json()) as {
        role: string;
        content: string;
        tool_payload?: Record<string, unknown>;
      }[];
      setThread(
        rows
          .filter((m) => m.role === "user" || m.role === "assistant")
          .map((m) => ({
            role: m.role as "user" | "assistant",
            text: m.content,
            intent: (m.tool_payload?.intent as string) || null,
            intent_label: null,
            proposal_id:
              ((m.tool_payload?.proposal as Record<string, unknown> | undefined)
                ?.proposal_id as string) || null,
          })),
      );
    } catch {
      setThread([]);
    }
  }, []);

  const createSession = useCallback(
    async (pid: string, title?: string) => {
      const res = await fetch(`${API_URL}/api/projects/${pid}/chat/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: title || null }),
      });
      if (!res.ok) return null;
      const data = (await res.json()) as ChatSession;
      await loadSessions(pid);
      setSessionId(data.id);
      setSessionTitle(data.title || "أمر جديد");
      setThread([]);
      setMessage("");
      return data;
    },
    [loadSessions],
  );

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    (async () => {
      const rows = await loadSessions(projectId);
      if (cancelled) return;
      if (rows[0]) {
        setSessionId(rows[0].id);
        setSessionTitle(rows[0].title || "أمر محفوظ");
        await loadMessages(projectId, rows[0].id);
      } else {
        await createSession(projectId);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, loadSessions, loadMessages, createSession]);

  useEffect(() => {
    if (!projectId) return;
    try {
      const saved = localStorage.getItem(draftKey(projectId, sessionId));
      if (saved != null) setMessage(saved);
    } catch {
      /* ignore */
    }
  }, [projectId, sessionId]);

  useEffect(() => {
    if (!projectId) return;
    try {
      localStorage.setItem(draftKey(projectId, sessionId), message);
    } catch {
      /* ignore */
    }
  }, [message, projectId, sessionId]);

  async function openSession(s: ChatSession) {
    if (!projectId || s.id === sessionId) return;
    setSessionId(s.id);
    setSessionTitle(s.title);
    setRenaming(false);
    setError("");
    await loadMessages(projectId, s.id);
  }

  async function onNewSession() {
    if (!projectId || busy) return;
    await createSession(projectId);
  }

  async function onRename() {
    if (!projectId || !sessionId) return;
    const title = sessionTitle.trim() || "أمر محفوظ";
    setSessionTitle(title);
    setRenaming(false);
    try {
      await fetch(`${API_URL}/api/projects/${projectId}/chat/sessions/${sessionId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      await loadSessions(projectId);
    } catch {
      /* ignore */
    }
  }

  async function onDeleteSession(id: string) {
    if (!projectId || busy) return;
    try {
      await fetch(`${API_URL}/api/projects/${projectId}/chat/sessions/${id}`, {
        method: "DELETE",
      });
      try {
        localStorage.removeItem(draftKey(projectId, id));
      } catch {
        /* ignore */
      }
      const rows = await loadSessions(projectId);
      if (sessionId === id) {
        if (rows[0]) {
          setSessionId(rows[0].id);
          setSessionTitle(rows[0].title);
          await loadMessages(projectId, rows[0].id);
        } else {
          await createSession(projectId);
        }
      }
    } catch {
      setError("تعذّر حذف الأمر المحفوظ.");
    }
  }

  async function send() {
    if (!projectId || !sessionId || !message.trim() || busy) return;
    const profile = loadUser();
    if (!hasFeature(profile, "chat")) {
      setError("محادثة الوكيل غير مفعّلة في خطتك — رقِّ من صفحة الخطط.");
      return;
    }
    if (!hasTokens(profile, 1)) {
      setError("نفدت التوكنز لهذا الشهر — راجع الاستخدام أو رقِّ الخطة.");
      return;
    }
    const text = message.trim();
    setBusy(true);
    setError("");
    setThread((t) => [...t, { role: "user", text }]);
    setMessage("");
    try {
      localStorage.removeItem(draftKey(projectId, sessionId));
    } catch {
      /* ignore */
    }
    try {
      const res = await fetch(
        `${API_URL}/api/projects/${projectId}/chat/sessions/${sessionId}/messages`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text }),
        },
      );
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        const proposalId =
          (data.proposal && (data.proposal.proposal_id || data.proposal.id)) || null;
        setThread((t) => [
          ...t,
          {
            role: "assistant",
            text: String(data.reply || "تم."),
            intent: data.intent || null,
            intent_label: data.intent_label || null,
            proposal_id: proposalId ? String(proposalId) : null,
          },
        ]);
        if (data.session_title) {
          setSessionTitle(String(data.session_title));
        } else if (sessionTitle === "أمر جديد") {
          setSessionTitle(titleFromText(text));
        }
        await loadSessions(projectId);
        await spendTokens(1, "chat");
      } else {
        setError(String(data.detail || "تعذّر إرسال الرسالة"));
      }
    } catch {
      setError("تعذّر الاتصال بالوكيل");
    } finally {
      setBusy(false);
    }
  }

  const active = focus.active || busy;
  const sessionList = useMemo(() => sessions, [sessions]);

  return (
    <div className="agent-workspace">
      <section className="brain-hero">
        <div className="brain-hero__copy">
          <span className={`live-pill ${active ? "is-hot" : ""}`}>
            <i className="live-pill__dot" />
            {active ? "الوكيل يعمل الآن" : connected ? "جاهز" : "غير متصل"}
          </span>
          <h1>عقل الوكيل</h1>
          <p>
            اكتب وصف البرنامج أو الموقع — يُحفظ الأمر باسم، ويمكنك الرجوع أو الحذف. النظام ينفّذ
            البناء عبر المحرّكات ويقترح الملفات (الدمج بعد موافقتك).
          </p>
          {focus.resume_hint && (
            <p className="brain-hero__resume">
              <strong>أين توقفت:</strong> {focus.resume_hint}
            </p>
          )}
          <label className="brain-hero__project">
            المشروع النشط
            <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
              {!projects.length && <option value="">لا مشاريع</option>}
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className={`brain-hero__viz ${active ? "is-active" : ""}`}>
          <NeuralNet active={active} intensity={intensity} />
        </div>
      </section>

      <section className="brain-grid">
        <ThinkingStream events={thinkEvents.length ? thinkEvents : events.slice(-16)} />
        <CodeStream events={codeEvents} />
      </section>

      <section className="agent-chat-layout glass-card">
        <aside className="agent-sessions" aria-label="الأوامر المحفوظة">
          <header className="agent-sessions__head">
            <strong>أوامر محفوظة</strong>
            <button type="button" className="btn btn-ghost" onClick={() => void onNewSession()}>
              جديد
            </button>
          </header>
          <ul className="agent-sessions__list">
            {sessionList.map((s) => (
              <li key={s.id} className={s.id === sessionId ? "is-active" : ""}>
                <button type="button" className="agent-sessions__item" onClick={() => void openSession(s)}>
                  <span>{s.title || "بدون عنوان"}</span>
                </button>
                <button
                  type="button"
                  className="agent-sessions__del"
                  title="حذف"
                  onClick={() => void onDeleteSession(s.id)}
                >
                  ×
                </button>
              </li>
            ))}
            {!sessionList.length && <li className="agent-sessions__empty">لا أوامر بعد</li>}
          </ul>
        </aside>

        <div className="agent-chat">
          <header className="glass-card__head agent-chat__head">
            {renaming ? (
              <input
                className="agent-chat__title-input"
                value={sessionTitle}
                autoFocus
                onChange={(e) => setSessionTitle(e.target.value)}
                onBlur={() => void onRename()}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    void onRename();
                  }
                }}
              />
            ) : (
              <button type="button" className="agent-chat__title" onClick={() => setRenaming(true)}>
                {sessionTitle || "أمر جديد"}
              </button>
            )}
            <span>{events.length} حدثًا</span>
          </header>

          <div className="agent-chat__thread">
            {!thread.length && (
              <p className="agent-chat__hint">
                مثال: «ابني موقع حجوزات بسيط بواجهة عربية وAPI للصحة» — يُحفظ الأمر ويمكن الرجوع إليه.
              </p>
            )}
            {thread.map((m, i) => (
              <div key={`${m.role}-${i}`} className={`agent-chat__bubble is-${m.role}`}>
                <pre dir="auto">{m.text}</pre>
                {m.role === "assistant" && (m.intent_label || m.proposal_id) ? (
                  <div className="agent-chat__meta">
                    {m.intent_label ? <span>نية: {m.intent_label}</span> : null}
                    {m.proposal_id ? (
                      <Link href="/proposals" className="agent-chat__proposal">
                        فتح المقترح ←
                      </Link>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ))}
          </div>

          {error ? <p className="agent-chat__error">{error}</p> : null}

          <div className="agent-chat__composer">
            <textarea
              rows={4}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="صف البرنامج أو الموقع أو التعديل المطلوب…"
              disabled={!projectId || busy}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
            />
            <div className="agent-chat__actions">
              <button
                type="button"
                className="btn btn-ghost"
                disabled={!message.trim()}
                onClick={() => setMessage("")}
              >
                اترك / امسح المسودة
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void send()}
                disabled={busy || !sessionId || !message.trim()}
              >
                {busy ? "ينفّذ…" : "نفّذ الأمر"}
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
