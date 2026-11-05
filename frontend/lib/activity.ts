import { API_URL } from "./api";

export type ActivityEvent = {
  id: number;
  ts: number;
  kind: string;
  title: string;
  detail: string;
  project_id: string | null;
  project_name: string | null;
  agent: string;
  intensity: number;
  payload: Record<string, unknown>;
};

export type AgentFocus = {
  project_id: string | null;
  project_name: string | null;
  phase: string;
  resume_hint: string | null;
  last_user_message: string | null;
  active: boolean;
  updated_at: number;
};

export type LiveSnapshot = {
  focus: AgentFocus;
  events: ActivityEvent[];
  server_time: number;
};

export async function fetchLiveActivity(projectId?: string): Promise<LiveSnapshot | null> {
  try {
    const q = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
    const res = await fetch(`${API_URL}/api/activity/live${q}`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchActivityEvents(
  afterId = 0,
  projectId?: string,
): Promise<{ events: ActivityEvent[]; focus: AgentFocus } | null> {
  try {
    const params = new URLSearchParams({ after_id: String(afterId) });
    if (projectId) params.set("project_id", projectId);
    const res = await fetch(`${API_URL}/api/activity/events?${params}`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}
