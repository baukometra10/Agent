import { API_URL } from "@/lib/api";

export type LocalRoot = {
  id: string;
  path: string;
  label: string;
  label_ar?: string;
};

export type LocalEntry = {
  name: string;
  path: string;
  type: "dir" | "file";
  size?: number;
  has_git?: boolean;
  has_package_json?: boolean;
  has_pyproject?: boolean;
};

export type LocalListResult = {
  path: string;
  name?: string;
  parent: string | null;
  folders: LocalEntry[];
  files: LocalEntry[];
  show_hidden?: boolean;
  q?: string;
};

export type LocalRootsResult = {
  home: string;
  roots: LocalRoot[];
  /** Base URL actually used for disk listing */
  diskBase: string;
  /** True when primary API is remote and we fell back to a local agent */
  usedLocalFallback: boolean;
  /** True when neither primary nor local disk API answered */
  unreachable: boolean;
};

function isLoopbackHost(url: string): boolean {
  try {
    const host = new URL(url).hostname.toLowerCase();
    return host === "127.0.0.1" || host === "localhost" || host === "::1";
  } catch {
    return false;
  }
}

function diskCandidates(): string[] {
  const extra = (process.env.NEXT_PUBLIC_LOCAL_DISK_URL || "").trim();
  const list = [API_URL, extra, "http://127.0.0.1:7000", "http://localhost:7000"];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of list) {
    const base = String(raw || "").replace(/\/$/, "");
    if (!base || seen.has(base)) continue;
    seen.add(base);
    out.push(base);
  }
  // Prefer loopback first when primary API is remote (cloud cannot see this PC)
  if (!isLoopbackHost(API_URL)) {
    out.sort((a, b) => Number(isLoopbackHost(b)) - Number(isLoopbackHost(a)));
  }
  return out;
}

let cachedDiskBase: string | null = null;
let cacheAt = 0;

async function probeRoots(base: string): Promise<{ home: string; roots: LocalRoot[] } | null> {
  try {
    const ctrl = typeof AbortSignal !== "undefined" && "timeout" in AbortSignal
      ? { signal: AbortSignal.timeout(2500) }
      : {};
    const res = await fetch(`${base}/api/projects/local-roots`, {
      cache: "no-store",
      ...ctrl,
    });
    if (!res.ok) return null;
    const data = await res.json();
    const roots = Array.isArray(data?.roots) ? data.roots : [];
    if (!roots.length && !data?.home) return null;
    return { home: String(data.home || ""), roots };
  } catch {
    return null;
  }
}

/** Resolve which API can list this machine's disks (local agent preferred over cloud). */
export async function resolveDiskApiBase(force = false): Promise<LocalRootsResult> {
  const now = Date.now();
  if (!force && cachedDiskBase && now - cacheAt < 30_000) {
    const hit = await probeRoots(cachedDiskBase);
    if (hit) {
      return {
        ...hit,
        diskBase: cachedDiskBase,
        usedLocalFallback: !isLoopbackHost(API_URL) && isLoopbackHost(cachedDiskBase),
        unreachable: false,
      };
    }
  }

  for (const base of diskCandidates()) {
    const hit = await probeRoots(base);
    if (hit && (hit.roots.length > 0 || hit.home)) {
      cachedDiskBase = base;
      cacheAt = Date.now();
      return {
        ...hit,
        diskBase: base,
        usedLocalFallback: !isLoopbackHost(API_URL) && isLoopbackHost(base),
        unreachable: false,
      };
    }
  }

  return {
    home: "",
    roots: [],
    diskBase: API_URL,
    usedLocalFallback: false,
    unreachable: true,
  };
}

export async function fetchLocalRoots(): Promise<LocalRootsResult> {
  return resolveDiskApiBase();
}

export async function fetchLocalList(
  path: string,
  opts?: { showHidden?: boolean; q?: string; diskBase?: string },
): Promise<LocalListResult | null> {
  const base =
    opts?.diskBase ||
    cachedDiskBase ||
    (await resolveDiskApiBase()).diskBase;
  try {
    const params = new URLSearchParams({ path });
    if (opts?.showHidden) params.set("show_hidden", "true");
    if (opts?.q?.trim()) params.set("q", opts.q.trim());
    const res = await fetch(`${base}/api/projects/local-list?${params}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

/** Suggested starter paths when roots API is empty but user is on Windows. */
export function clientFallbackRoots(): LocalRoot[] {
  if (typeof navigator === "undefined") return [];
  const ua = navigator.userAgent || "";
  if (!/Windows/i.test(ua)) {
    return [
      { id: "home_guess", path: "~", label: "home", label_ar: "المجلد الشخصي" },
    ];
  }
  return [
    { id: "c_users", path: "C:\\Users", label: "Users", label_ar: "المستخدمون" },
    { id: "c_root", path: "C:\\", label: "C:", label_ar: "القرص C:" },
    { id: "d_root", path: "D:\\", label: "D:", label_ar: "القرص D:" },
  ];
}
