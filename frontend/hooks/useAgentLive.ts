"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  fetchActivityEvents,
  fetchLiveActivity,
  type ActivityEvent,
  type AgentFocus,
} from "@/lib/activity";

const idleFocus: AgentFocus = {
  project_id: null,
  project_name: null,
  phase: "idle",
  resume_hint: null,
  last_user_message: null,
  active: false,
  updated_at: 0,
};

export function useAgentLive(projectId?: string, intervalMs = 900) {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [focus, setFocus] = useState<AgentFocus>(idleFocus);
  const [connected, setConnected] = useState(false);
  const afterId = useRef(0);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      const snap = await fetchLiveActivity(projectId);
      if (cancelled || !snap) return;
      setEvents(snap.events);
      setFocus(snap.focus);
      afterId.current = snap.events.at(-1)?.id ?? 0;
      setConnected(true);
    }

    bootstrap();
    const timer = setInterval(async () => {
      const batch = await fetchActivityEvents(afterId.current, projectId);
      if (cancelled || !batch) {
        setConnected(false);
        return;
      }
      setConnected(true);
      setFocus(batch.focus);
      if (batch.events.length) {
        afterId.current = batch.events.at(-1)!.id;
        setEvents((prev) => {
          const merged = [...prev, ...batch.events];
          return merged.slice(-120);
        });
      }
    }, intervalMs);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [projectId, intervalMs]);

  const codeEvents = useMemo(
    () => events.filter((e) => e.kind === "code").slice(-12),
    [events],
  );
  const thinkEvents = useMemo(
    () => events.filter((e) => e.kind === "think" || e.kind === "decision" || e.kind === "neural").slice(-20),
    [events],
  );
  const intensity = useMemo(() => {
    if (!focus.active) return 0.12;
    const last = events.at(-1);
    return last?.intensity ?? 0.55;
  }, [events, focus.active]);

  return { events, focus, connected, codeEvents, thinkEvents, intensity };
}
