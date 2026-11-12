"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { IconBell } from "@/components/icons";
import { fetchAutopilotReports, fetchProjects, fetchProposals } from "@/lib/api";
import { fetchLiveActivity, type ActivityEvent } from "@/lib/activity";
import type { Proposal } from "@/lib/types";

type Item = {
  id: string;
  title: string;
  detail: string;
  href: string;
  kind: "proposal" | "activity" | "copilot";
  ts: number;
};

function formatNotifyWhen(ts: number): string {
  if (!ts || Number.isNaN(ts)) return "";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "";
  try {
    return new Intl.DateTimeFormat("ar", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(d);
  } catch {
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }
}

function kindLabel(kind: Item["kind"]): string {
  if (kind === "proposal") return "مقترح";
  if (kind === "copilot") return "تقرير ذكاء اصطناعي";
  return "نشاط";
}

export function NotificationsMenu() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Item[]>([]);
  const [seenIds, setSeenIds] = useState<Set<string>>(new Set());
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem("evolve.notifySeen");
      if (raw) setSeenIds(new Set(JSON.parse(raw)));
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const projects = await fetchProjects();
      const project = projects[0];
      const [snap, proposals, reports] = await Promise.all([
        fetchLiveActivity(project?.id),
        project ? fetchProposals(project.id) : Promise.resolve([] as Proposal[]),
        fetchAutopilotReports(),
      ]);
      if (cancelled) return;

      const copilotItems: Item[] = (reports || []).slice(0, 6).map((r) => {
        const ts = r.generated_at ? Date.parse(String(r.generated_at)) || Date.now() : Date.now();
        const summary = String(r.summary || "").trim();
        const scanned =
          r.projects_scanned != null ? `مشاريع مفحوصة: ${r.projects_scanned}` : "";
        return {
          id: `c-${String(r.id || r.run_id || r.generated_at)}`,
          title: r.urgent ? "تقرير عاجل · النشاط الآلي" : "تقرير النشاط الآلي",
          detail: [summary, scanned].filter(Boolean).join(" — ") || "تقرير جاهز للمراجعة",
          href: "/copilot",
          kind: "copilot" as const,
          ts,
        };
      });

      const proposalItems: Item[] = (proposals || [])
        .filter((p) => ["awaiting_approval", "awaiting_merge", "revision_requested"].includes(p.status))
        .slice(0, 6)
        .map((p) => ({
          id: `p-${p.id}`,
          title: p.status === "awaiting_merge" ? "بانتظار الدمج" : "مقترح يحتاج قرارك",
          detail: p.title,
          href: p.status === "awaiting_merge" ? "/execution" : "/proposals",
          kind: "proposal" as const,
          ts: Date.now(),
        }));

      const activityItems: Item[] = ((snap?.events || []) as ActivityEvent[])
        .slice(-8)
        .reverse()
        .map((e) => ({
          id: `a-${e.id}`,
          title: e.title,
          detail: e.detail || e.agent || "",
          href: "/log",
          kind: "activity" as const,
          ts: e.ts * 1000,
        }));

      setItems(
        [...copilotItems, ...proposalItems, ...activityItems]
          .sort((a, b) => b.ts - a.ts)
          .slice(0, 14),
      );
    }
    load();
    const t = setInterval(load, 4000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const unread = useMemo(
    () => items.filter((i) => !seenIds.has(i.id)).length,
    [items, seenIds],
  );

  function markAllSeen() {
    const next = new Set(seenIds);
    items.forEach((i) => next.add(i.id));
    setSeenIds(next);
    localStorage.setItem("evolve.notifySeen", JSON.stringify([...next]));
  }

  return (
    <div className="top-menu" ref={root}>
      <button
        type="button"
        className={`icon-btn notify-btn ${open ? "is-open" : ""}`}
        aria-label="الإشعارات"
        aria-expanded={open}
        onClick={() => {
          setOpen((v) => !v);
          if (!open) markAllSeen();
        }}
      >
        <IconBell />
        {unread > 0 && <span className="notify-dot">{unread > 9 ? "9+" : unread}</span>}
      </button>

      {open && (
        <div className="top-popover" role="menu">
          <header className="top-popover__head">
            <strong>الإشعارات</strong>
            <button type="button" className="linkish" onClick={markAllSeen}>
              تعليم الكل كمقروء
            </button>
          </header>
          <ul className="top-popover__list">
            {items.length === 0 && <li className="top-popover__empty">لا إشعارات الآن</li>}
            {items.map((item) => {
              const when = formatNotifyWhen(item.ts);
              return (
                <li key={item.id}>
                  <Link href={item.href} className="top-popover__item" onClick={() => setOpen(false)}>
                    <div className="top-popover__meta">
                      <em>{kindLabel(item.kind)}</em>
                      {when ? (
                        <time className="top-popover__when" dateTime={new Date(item.ts).toISOString()}>
                          {when}
                        </time>
                      ) : null}
                    </div>
                    <strong>{item.title}</strong>
                    {item.detail ? <span>{item.detail}</span> : null}
                  </Link>
                </li>
              );
            })}
          </ul>
          <footer className="top-popover__foot">
            <Link href="/log" onClick={() => setOpen(false)}>
              فتح السجل الكامل
            </Link>
          </footer>
        </div>
      )}
    </div>
  );
}
