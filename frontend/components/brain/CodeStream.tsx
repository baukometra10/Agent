"use client";

import { useEffect, useMemo, useState } from "react";
import type { ActivityEvent } from "@/lib/activity";

type Props = {
  events: ActivityEvent[];
  title?: string;
};

export function CodeStream({ events, title = "كتابة الكود لحظة بلحظة" }: Props) {
  const latest = events.at(-1);
  const path = String(latest?.payload?.path || latest?.title || "");
  const full = String(latest?.payload?.content || latest?.detail || "");
  const [shown, setShown] = useState("");

  useEffect(() => {
    setShown("");
    if (!full) return;
    let i = 0;
    const step = Math.max(2, Math.floor(full.length / 80));
    const timer = setInterval(() => {
      i = Math.min(full.length, i + step);
      setShown(full.slice(0, i));
      if (i >= full.length) clearInterval(timer);
    }, 18);
    return () => clearInterval(timer);
  }, [full, latest?.id]);

  const files = useMemo(() => {
    const map = new Map<string, ActivityEvent>();
    for (const ev of events) {
      const p = String(ev.payload?.path || "");
      if (p) map.set(p, ev);
    }
    return [...map.keys()];
  }, [events]);

  return (
    <section className="code-stream">
      <header className="code-stream__head">
        <h3>{title}</h3>
        <span>{path || "لا ملف نشط"}</span>
      </header>
      {files.length > 0 && (
        <div className="code-stream__files">
          {files.map((f) => (
            <span key={f} className={f === path ? "is-active" : ""}>
              {f}
            </span>
          ))}
        </div>
      )}
      <pre className="code-stream__editor" dir="ltr">
        <code>{shown || "// الوكيل سيكتب هنا عند التنفيذ…"}</code>
        {shown && shown.length < full.length && <span className="code-stream__caret">▌</span>}
      </pre>
    </section>
  );
}
