"use client";

import type { Project } from "@/lib/types";
import { resolveDiskApiBase } from "@/lib/localDisk";

declare global {
  interface Window {
    spixaDesktop?: {
      isDesktop?: boolean;
      pickFolder?: () => Promise<string | null>;
    };
  }
}

export function isSpixaDesktop(): boolean {
  return typeof window !== "undefined" && Boolean(window.spixaDesktop?.isDesktop);
}

/** Native folder dialog when running inside Spixa Desktop; otherwise null. */
export async function pickLocalFolder(): Promise<string | null> {
  const pick = window.spixaDesktop?.pickFolder;
  if (!pick) return null;
  return pick();
}

/**
 * Bind a real folder on this machine.
 * Uses the same local disk API that can see the path (not a remote Railway FS).
 */
export async function openLocalProjectFolder(
  localPath: string,
  description?: string,
): Promise<{ ok: true; project: Project } | { ok: false; error: string }> {
  const cleaned = localPath.trim().replace(/[\\/]+$/, "");
  if (!cleaned) return { ok: false, error: "empty_path" };
  const name = cleaned.split(/[\\/]/).filter(Boolean).pop() || "project";

  const disk = await resolveDiskApiBase();
  if (disk.unreachable) {
    return { ok: false, error: "local_api_unreachable" };
  }

  try {
    const res = await fetch(`${disk.diskBase}/api/projects/from-path`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        local_path: cleaned,
        description: description || `Bound live folder · ${cleaned}`,
      }),
    });
    if (!res.ok) return { ok: false, error: "create_failed" };
    const project = (await res.json()) as Project;
    return { ok: true, project };
  } catch {
    return { ok: false, error: "create_failed" };
  }
}
