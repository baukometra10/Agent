"use client";

import { createProjectFromPath } from "@/lib/api";
import type { Project } from "@/lib/types";

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

export async function openLocalProjectFolder(
  localPath: string,
  description?: string,
): Promise<{ ok: true; project: Project } | { ok: false; error: string }> {
  const cleaned = localPath.trim().replace(/[\\/]+$/, "");
  if (!cleaned) return { ok: false, error: "empty_path" };
  const name = cleaned.split(/[\\/]/).filter(Boolean).pop() || "project";
  const project = await createProjectFromPath({
    name,
    local_path: cleaned,
    description: description || `Bound live folder · ${cleaned}`,
  });
  if (!project) return { ok: false, error: "create_failed" };
  return { ok: true, project };
}
