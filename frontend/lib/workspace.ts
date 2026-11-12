import { API_URL } from "@/lib/api";
import { apiBaseForProject, resolveProjectApiBase } from "@/lib/projectApi";

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

function syncBase(projectId: string): string {
  return apiBaseForProject(projectId) || API_URL;
}

async function withProjectBase(
  projectId: string,
  run: (base: string) => Promise<Response>,
): Promise<Response | null> {
  const tried = new Set<string>();
  const bases: string[] = [];
  try {
    bases.push(await resolveProjectApiBase(projectId));
  } catch {
    bases.push(syncBase(projectId));
  }
  for (const extra of [syncBase(projectId), API_URL, "http://127.0.0.1:7000", "http://localhost:7000"]) {
    const cleaned = String(extra || "").replace(/\/$/, "");
    if (cleaned && !bases.includes(cleaned)) bases.push(cleaned);
  }

  for (const base of bases) {
    if (tried.has(base)) continue;
    tried.add(base);
    try {
      const res = await run(base);
      if (res.ok) return res;
      // 404/5xx on wrong host — try next candidate
      if (res.status === 404 || res.status >= 500) continue;
      return res;
    } catch {
      /* try next host */
    }
  }
  return null;
}

export async function fetchWorkspaceTree(projectId: string): Promise<TreeResponse> {
  const res = await withProjectBase(projectId, (base) =>
    fetch(`${base}/api/projects/${projectId}/workspace/tree`, { cache: "no-store" }),
  );
  if (!res || !res.ok) return { entries: [] };
  const data = await res.json().catch(() => ({ entries: [] }));
  return {
    root: data?.root,
    entries: Array.isArray(data?.entries) ? data.entries : [],
    count: data?.count,
    truncated: data?.truncated,
  };
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
  const res = await withProjectBase(projectId, (base) =>
    fetch(`${base}/api/projects/${projectId}/workspace/file?path=${encodeURIComponent(path)}`, {
      cache: "no-store",
    }),
  );
  const data = res ? await res.json().catch(() => ({})) : {};
  if (!res || !res.ok) return { ok: false, error: data.detail || "read_failed" };
  return { ok: true, ...data };
}

export function workspaceRawUrl(projectId: string, path: string): string {
  return `${syncBase(projectId)}/api/projects/${projectId}/workspace/raw?path=${encodeURIComponent(path)}`;
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
  const res = await withProjectBase(projectId, (base) =>
    fetch(`${base}/api/projects/${projectId}/workspace/terminal`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command, cwd: cwd || null, timeout: 60 }),
    }),
  );
  const data = res ? await res.json().catch(() => ({})) : {};
  if (!res || !res.ok) return { ok: false, error: String(data.detail || "terminal_failed") };
  return data;
}

export async function fetchCompletions(
  projectId: string,
  payload: { path: string; language: string; prefix: string; suffix: string },
): Promise<{ insertText: string; label?: string }[]> {
  const res = await withProjectBase(projectId, (base) =>
    fetch(`${base}/api/projects/${projectId}/workspace/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
  if (!res || !res.ok) return [];
  const data = await res.json().catch(() => ({}));
  return Array.isArray(data.suggestions) ? data.suggestions : [];
}

export async function saveWorkspaceFile(
  projectId: string,
  path: string,
  content: string,
): Promise<{ ok: boolean; error?: string }> {
  const res = await withProjectBase(projectId, (base) =>
    fetch(`${base}/api/projects/${projectId}/workspace/file`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, content }),
    }),
  );
  const data = res ? await res.json().catch(() => ({})) : {};
  if (!res || !res.ok) return { ok: false, error: String(data.detail || "save_failed") };
  return { ok: true };
}

export async function createWorkspaceEntry(
  projectId: string,
  path: string,
  kind: "file" | "dir" = "file",
): Promise<{ ok: boolean; error?: string }> {
  const res = await withProjectBase(projectId, (base) =>
    fetch(`${base}/api/projects/${projectId}/workspace/file`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, kind, content: "" }),
    }),
  );
  const data = res ? await res.json().catch(() => ({})) : {};
  if (!res || !res.ok) return { ok: false, error: String(data.detail || "create_failed") };
  return { ok: true };
}
