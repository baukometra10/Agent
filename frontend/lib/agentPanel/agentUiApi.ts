import { API_URL } from "@/lib/api";

export type CommandTemplate = {
  id: string;
  title: string;
  prompt: string;
  created_at?: string | null;
};

export type TabsState = {
  open_ids: string[];
  active_id: string | null;
  pinned_ids: string[];
  updated_at?: string | null;
};

export async function fetchTemplates(projectId: string): Promise<CommandTemplate[]> {
  const res = await fetch(`${API_URL}/api/projects/${projectId}/agent-ui/templates`, {
    cache: "no-store",
  });
  if (!res.ok) return [];
  const data = await res.json();
  return Array.isArray(data.templates) ? data.templates : [];
}

export async function createTemplate(
  projectId: string,
  title: string,
  prompt: string,
): Promise<CommandTemplate | null> {
  const res = await fetch(`${API_URL}/api/projects/${projectId}/agent-ui/templates`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, prompt }),
  });
  if (!res.ok) return null;
  return res.json();
}

export async function deleteTemplate(projectId: string, templateId: string): Promise<boolean> {
  const res = await fetch(`${API_URL}/api/projects/${projectId}/agent-ui/templates/${templateId}`, {
    method: "DELETE",
  });
  return res.ok || res.status === 204;
}

export async function fetchTabsState(projectId: string): Promise<TabsState | null> {
  const res = await fetch(`${API_URL}/api/projects/${projectId}/agent-ui/tabs-state`, {
    cache: "no-store",
  });
  if (!res.ok) return null;
  return res.json();
}

export async function putTabsState(projectId: string, state: TabsState): Promise<TabsState | null> {
  const res = await fetch(`${API_URL}/api/projects/${projectId}/agent-ui/tabs-state`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(state),
  });
  if (!res.ok) return null;
  return res.json();
}

export async function createShareLink(
  projectId: string,
  sessionId: string,
): Promise<{ token: string; path: string } | null> {
  const res = await fetch(
    `${API_URL}/api/projects/${projectId}/agent-ui/sessions/${sessionId}/share`,
    { method: "POST" },
  );
  if (!res.ok) return null;
  return res.json();
}

export async function resolveShare(
  token: string,
): Promise<{ project_id: string; session_id: string; title: string } | null> {
  const res = await fetch(`${API_URL}/api/agent-share/${encodeURIComponent(token)}`, {
    cache: "no-store",
  });
  if (!res.ok) return null;
  return res.json();
}
