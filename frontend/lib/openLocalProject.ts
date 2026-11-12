"use client";

import type { Project } from "@/lib/types";
import { resolveDiskApiBase } from "@/lib/localDisk";
import { rememberProjectApiBase } from "@/lib/projectApi";

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

async function readErrorDetail(res: Response): Promise<string> {
  try {
    const data = await res.json();
    const detail = data?.detail;
    if (typeof detail === "string" && detail.trim()) return detail.trim();
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  } catch {
    /* ignore */
  }
  return `http_${res.status}`;
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
    if (!res.ok) {
      const detail = await readErrorDetail(res);
      if (/connect|refused|database|postgres|operational/i.test(detail)) {
        return {
          ok: false,
          error: "database_unavailable",
        };
      }
      return { ok: false, error: detail || "create_failed" };
    }
    const project = (await res.json()) as Project;
    if (project?.id) {
      rememberProjectApiBase(String(project.id), disk.diskBase);
    }
    return { ok: true, project };
  } catch {
    return { ok: false, error: "create_failed" };
  }
}

export function openFolderErrorMessage(code: string): string {
  if (code === "local_api_unreachable") {
    return "شغّل الـ API محلياً (start.ps1 على المنفذ 7000) حتى يمكن قراءة مجلدات جهازك.";
  }
  if (code === "database_unavailable") {
    return "قاعدة البيانات غير متاحة. شغّل Docker لـ PostgreSQL أو أعد تشغيل start.ps1.";
  }
  if (code === "empty_path") return "المسار فارغ.";
  if (code === "create_failed") {
    return "تعذّر فتح المجلد — تأكد أن المسار موجود وأن الـ API المحلي يعمل.";
  }
  return `تعذّر فتح المجلد: ${code}`;
}
