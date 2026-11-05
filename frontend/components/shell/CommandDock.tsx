"use client";

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { API_URL, fetchProjects } from "@/lib/api";
import { spendTokens } from "@/lib/billing";
import { hasFeature, hasTokens, loadUser } from "@/lib/user";

type Msg = { role: "user" | "assistant"; text: string };

/**
 * Manual command surface — available on most pages.
 * Hidden on /ide (workspace already has Spixa Agent panel).
 * Ctrl/Cmd+J toggles elsewhere.
 */
export function CommandDock() {
  const pathname = usePathname() || "";
  const hideOnIde = pathname === "/ide" || pathname.startsWith("/ide/");
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [projectName, setProjectName] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (hideOnIde) setOpen(false);
  }, [hideOnIde]);

  const loadProject = useCallback(async () => {
    const projects = await fetchProjects();
    const first = projects[0];
    if (first) {
      setProjectId(first.id);
      setProjectName(first.name);
    } else {
      setProjectId(null);
      setProjectName("");
    }
  }, []);

  useEffect(() => {
    void loadProject();
  }, [loadProject]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (hideOnIde) return;
      const meta = e.ctrlKey || e.metaKey;
      if (meta && e.key.toLowerCase() === "j") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [hideOnIde]);

  useEffect(() => {
    if (open) {
      window.setTimeout(() => inputRef.current?.focus(), 40);
    }
  }, [open]);

  async function ensureSession(pid: string): Promise<string | null> {
    if (sessionId) return sessionId;
    const res = await fetch(`${API_URL}/api/projects/${pid}/chat/sessions`, {
      method: "POST",
    });
    if (!res.ok) return null;
    const data = await res.json();
    const id = String(data.id || data.session_id || "");
    setSessionId(id || null);
    return id || null;
  }

  async function onSend() {
    const message = text.trim();
    if (!message || busy) return;
    if (!projectId) {
      setError("أضف مشروعاً أولاً من إدارة المشاريع.");
      return;
    }
    const profile = loadUser();
    if (!hasFeature(profile, "chat")) {
      setError("المحادثة غير مفعّلة في خطتك — رقِّ من /pricing.");
      return;
    }
    if (!hasTokens(profile, 1)) {
      setError("نفدت التوكنز — راجع /console أو رقِّ الخطة.");
      return;
    }
    setBusy(true);
    setError("");
    setMsgs((m) => [...m, { role: "user", text: message }]);
    setText("");
    try {
      const sid = await ensureSession(projectId);
      if (!sid) {
        setError("تعذّر فتح جلسة أوامر.");
        setBusy(false);
        return;
      }
      const res = await fetch(
        `${API_URL}/api/projects/${projectId}/chat/sessions/${sid}/messages`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message }),
        },
      );
      if (!res.ok) {
        setError("فشل إرسال الأمر.");
        setBusy(false);
        return;
      }
      const data = await res.json();
      setMsgs((m) => [
        ...m,
        { role: "assistant", text: String(data.reply || data.message || "تم.") },
      ]);
      await spendTokens(1, "command_dock");
    } catch {
      setError("تعذّر الاتصال بالوكيل.");
    }
    setBusy(false);
  }

  if (hideOnIde) return null;

  return (
    <>
      <button
        type="button"
        className={`cmd-fab ${open ? "is-open" : ""}`}
        onClick={() => setOpen((v) => !v)}
        title="أوامر يدوية (Ctrl+J)"
        aria-label="فتح لوحة الأوامر اليدوية"
      >
        <span className="cmd-fab__glyph">⌘</span>
        <span className="cmd-fab__label">أمر</span>
      </button>

      {open && (
        <div className="cmd-dock" role="dialog" aria-label="لوحة الأوامر اليدوية">
          <header className="cmd-dock__head">
            <div>
              <strong>أوامر يدوية</strong>
              <span>
                {projectName
                  ? `المشروع النشط: ${projectName}`
                  : "لا مشروع — افتح مشروعاً أولاً"}
              </span>
            </div>
            <button type="button" className="btn btn-ghost" onClick={() => setOpen(false)}>
              إغلاق
            </button>
          </header>

          <div className="cmd-dock__thread">
            {msgs.length === 0 && (
              <p className="cmd-dock__hint">
                اكتب أمراً مباشراً: «أصلح الاختبارات»، «افهم المشروع»، «اقترح تحسينات أمنية».
                الوكيل يقترح فقط — التنفيذ بعد موافقتك.
              </p>
            )}
            {msgs.map((m, i) => (
              <div key={i} className={`cmd-bubble cmd-bubble--${m.role}`}>
                {m.text}
              </div>
            ))}
            {error ? <p className="cmd-dock__error">{error}</p> : null}
          </div>

          <div className="cmd-dock__composer">
            <textarea
              ref={inputRef}
              rows={3}
              value={text}
              placeholder="اكتب أمراً يدوياً للوكيل…"
              disabled={busy}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void onSend();
                }
              }}
            />
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy || !text.trim()}
              onClick={() => void onSend()}
            >
              {busy ? "…" : "إرسال"}
            </button>
          </div>
          <p className="cmd-dock__kbd">
            <kbd>Ctrl</kbd>+<kbd>J</kbd> تبديل · <kbd>Enter</kbd> إرسال · <kbd>Shift+Enter</kbd>{" "}
            سطر جديد
          </p>
        </div>
      )}
    </>
  );
}
