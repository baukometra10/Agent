import { API_URL } from "@/lib/api";
import { resolveDiskApiBase } from "@/lib/localDisk";
import type { Project } from "@/lib/types";

const HOST_KEY = "spixa.projectApiHosts";

function isLoopback(url: string): boolean {
  try {
    const host = new URL(url).hostname.toLowerCase();
    return host === "127.0.0.1" || host === "localhost" || host === "::1";
  } catch {
    return false;
  }
}

function readHostMap(): Record<string, string> {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(HOST_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function writeHostMap(map: Record<string, string>) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(HOST_KEY, JSON.stringify(map));
  } catch {
    /* ignore */
  }
}

/** Remember which API base owns this project (local disk vs cloud). */
export function rememberProjectApiBase(projectId: string, base: string) {
  const id = String(projectId || "").trim();
  const cleaned = String(base || "").replace(/\/$/, "");
  if (!id || !cleaned) return;
  const map = readHostMap();
  map[id] = cleaned;
  writeHostMap(map);
}

/** API base for workspace/project calls for a known project id. */
export function apiBaseForProject(projectId: string): string {
  const map = readHostMap();
  const hit = map[String(projectId || "")];
  return hit || API_URL;
}

/**
 * Resolve (and remember) the API that actually owns this project.
 * When NEXT_PUBLIC_API_URL points at a tunnel/cloud host, local-bound
 * projects still live on the disk agent — probe it once and stick.
 */
export async function resolveProjectApiBase(projectId: string): Promise<string> {
  const id = String(projectId || "").trim();
  if (!id) return API_URL.replace(/\/$/, "");

  const map = readHostMap();
  if (map[id]) return map[id].replace(/\/$/, "");

  if (isLoopback(API_URL)) {
    rememberProjectApiBase(id, API_URL);
    return API_URL.replace(/\/$/, "");
  }

  try {
    const disk = await resolveDiskApiBase();
    if (!disk.unreachable && disk.diskBase) {
      const base = disk.diskBase.replace(/\/$/, "");
      const ctrl =
        typeof AbortSignal !== "undefined" && "timeout" in AbortSignal
          ? { signal: AbortSignal.timeout(2500) }
          : {};
      const res = await fetch(`${base}/api/projects/${id}`, { cache: "no-store", ...ctrl });
      if (res.ok) {
        rememberProjectApiBase(id, base);
        return base;
      }
    }
  } catch {
    /* fall through */
  }

  return API_URL.replace(/\/$/, "");
}

async function fetchProjectsFrom(base: string): Promise<Project[]> {
  try {
    const res = await fetch(`${base.replace(/\/$/, "")}/api/projects`, { cache: "no-store" });
    if (!res.ok) return [];
    const rows = await res.json();
    return Array.isArray(rows) ? rows : [];
  } catch {
    return [];
  }
}

/**
 * Merge projects from the primary API and the local disk agent so bound folders
 * always appear in the IDE/project lists and stay routable to the right host.
 */
export async function fetchProjectsMerged(): Promise<Project[]> {
  const bases = new Set<string>([API_URL.replace(/\/$/, "")]);
  try {
    const disk = await resolveDiskApiBase();
    if (!disk.unreachable && disk.diskBase) {
      bases.add(disk.diskBase.replace(/\/$/, ""));
    }
  } catch {
    /* ignore */
  }

  const byId = new Map<string, { project: Project; base: string }>();
  await Promise.all(
    [...bases].map(async (base) => {
      const rows = await fetchProjectsFrom(base);
      for (const project of rows) {
        if (!project?.id) continue;
        rememberProjectApiBase(String(project.id), base);
        const prev = byId.get(String(project.id));
        if (!prev || isLoopback(base)) {
          byId.set(String(project.id), { project, base });
        }
      }
    }),
  );

  return [...byId.values()].map((row) => row.project);
}
