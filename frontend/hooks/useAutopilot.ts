"use client";

import { useCallback, useEffect, useState } from "react";
import {
  disableAutopilot,
  enableAutopilot,
  fetchAutopilot,
  resumeAutopilot,
  runAutopilot,
} from "@/lib/api";

export type AutopilotSnapshot = {
  enabled: boolean;
  paused: boolean;
  loopRunning: boolean;
  uiMode: string;
  intervalSeconds: number;
  lastRun: string | null;
  doctrine: string;
  loading: boolean;
  busy: boolean;
  error: string | null;
};

const initial: AutopilotSnapshot = {
  enabled: false,
  paused: false,
  loopRunning: false,
  uiMode: "manual",
  intervalSeconds: 300,
  lastRun: null,
  doctrine: "",
  loading: true,
  busy: false,
  error: null,
};

export function useAutopilot() {
  const [state, setState] = useState<AutopilotSnapshot>(initial);

  const refresh = useCallback(async () => {
    const data = await fetchAutopilot();
    const auto = (data?.autopilot || {}) as Record<string, unknown>;
    setState((s) => ({
      ...s,
      loading: false,
      enabled: Boolean(auto.enabled),
      paused: Boolean(auto.paused_for_manual),
      loopRunning: Boolean(auto.loop_running),
      uiMode: String(auto.ui_mode || "manual"),
      intervalSeconds: Number(auto.interval_seconds || 300),
      lastRun: (auto.last_run as string) || null,
      doctrine: String(auto.doctrine || ""),
      error: data ? null : "تعذر الاتصال بمساعد الطيار",
    }));
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 12000);
    const onFocus = () => void refresh();
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(id);
      window.removeEventListener("focus", onFocus);
    };
  }, [refresh]);

  const setEnabled = useCallback(
    async (on: boolean, notifyEmail?: string) => {
      setState((s) => ({ ...s, busy: true, error: null }));
      try {
        if (on) {
          await enableAutopilot(notifyEmail);
          await runAutopilot(notifyEmail);
        } else {
          await disableAutopilot();
        }
        await refresh();
      } catch {
        setState((s) => ({ ...s, error: "فشل تبديل مساعد الطيار" }));
      } finally {
        setState((s) => ({ ...s, busy: false }));
      }
    },
    [refresh],
  );

  const resume = useCallback(async () => {
    setState((s) => ({ ...s, busy: true, error: null }));
    try {
      await resumeAutopilot();
      await refresh();
    } finally {
      setState((s) => ({ ...s, busy: false }));
    }
  }, [refresh]);

  return { ...state, refresh, setEnabled, resume };
}
