import { API_URL } from "@/lib/api";
import { apiBaseForProject } from "@/lib/projectApi";

export type TreeEntry = {
  path: string;
  name: string;
  type: "file" | "dir";
  size?: number;
};

export type TreeResponse = {
  root?: string;
  entries: TreeEntry[];
  count?: number;
  truncated?: boolean;
};

function baseFor(projectId: string): string {
  return apiBaseForProject(projectId) || API_URL;
}

export async function fetchWorkspaceTree(projectId: string): Promise<TreeResponse> {
  const res = await fetch(`${baseFor(projectId)}/api/projects/${projectId}/workspace/tree`, {
    cache: "no-store",
  });
  if (!res.ok) return { entries: [] };
  return res.json();
}

export type WorkspaceFileKind = "text" | "image" | "pdf" | "audio" | "video" | "binary";

export type WorkspaceFileResult = {
  ok: boolean;
  content?: string;
  path?: string;
  error?: string;
  truncated?: boolean;
  kind?: WorkspaceFileKind;
  size?: number;
  mime?: string;
  name?: string;
  previewable?: boolean;
  chars?: number;
};

export async function fetchWorkspaceFile(
  projectId: string,
  path: string,
): Promise<WorkspaceFileResult> {
  const res = await fetch(
    `${baseFor(projectId)}/api/projects/${projectId}/workspace/file?path=${encodeURIComponent(path)}`,
    { cache: "no-store" },
  );
  const data = await res.json().catch(() => ({}));
  if (!res.ok) return { ok: false, error: data.detail || "read_failed" };
  return { ok: true, ...data };
}

export function workspaceRawUrl(projectId: string, path: string): string {
  return `${baseFor(projectId)}/api/projects/${projectId}/workspace/raw?path=${encodeURIComponent(path)}`;
}

export async function runWorkspaceCommand(
  projectId: string,
  command: string,
  cwd?: string,
): Promise<{
  ok: boolean;
  exit_code?: number | null;
  stdout?: string;
  stderr?: string;
  error?: string;
  cwd?: string;
  command?: string;
}> {
  const res = await fetch(`${baseFor(projectId)}/api/projects/${projectId}/workspace/terminal`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command, cwd: cwd || null, timeout: 60 }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) return { ok: false, error: String(data.detail || "terminal_failed") };
  return data;
}

export async function fetchCompletions(
  projectId: string,
  payload: { path: string; language: string; prefix: string; suffix: string },
): Promise<{ insertText: string; label?: string }[]> {
  const res = await fetch(`${baseFor(projectId)}/api/projects/${projectId}/workspace/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) return [];
  const data = await res.json().catch(() => ({}));
  return Array.isArray(data.suggestions) ? data.suggestions : [];
}

export async function saveWorkspaceFile(
  projectId: string,
  path: string,
  content: string,
): Promise<{ ok: boolean; error?: string }> {
  const res = await fetch(`${baseFor(projectId)}/api/projects/${projectId}/workspace/file`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, content }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) return { ok: false, error: String(data.detail || "save_failed") };
  return { ok: true };
}

export async function createWorkspaceEntry(
  projectId: string,
  path: string,
  kind: "file" | "dir" = "file",
): Promise<{ ok: boolean; error?: string }> {
  const res = await fetch(`${baseFor(projectId)}/api/projects/${projectId}/workspace/file`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, kind, content: "" }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) return { ok: false, error: String(data.detail || "create_failed") };
  return { ok: true };
}
