"use client";

import type { ActivityEvent } from "@/lib/activity";

const kindLabel: Record<string, string> = {
  think: "تفكير",
  neural: "شبكة",
  tool: "أداة",
  decision: "قرار",
  memory: "ذاكرة",
  status: "حالة",
  code: "كود",
};

type Props = {
  events: ActivityEvent[];
  title?: string;
};

export function ThinkingStream({ events, title = "كيف يفكر الوكيل" }: Props) {
  const rows = [...events].reverse();

  return (
    <section className="think-stream">
      <header className="think-stream__head">
        <h3>{title}</h3>
        <span>{rows.length ? "بث مباشر" : "بانتظار نشاط"}</span>
      </header>
      <ul className="think-stream__list">
        {rows.length === 0 && (
          <li className="think-stream__empty">سيظهر هنا مسار التفكير لحظة بدء العمل على مشروع.</li>
        )}
        {rows.map((ev) => (
          <li key={ev.id} className={`think-stream__item kind-${ev.kind}`}>
            <div className="think-stream__meta">
              <em>{kindLabel[ev.kind] || ev.kind}</em>
              <span>{ev.agent}</span>
            </div>
            <strong>{ev.title}</strong>
            {ev.detail && <p>{ev.detail}</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}
