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

export async function fetchLocalRoots(): Promise<{ home: string; roots: LocalRoot[] }> {
  try {
    const res = await fetch(`${API_URL}/api/projects/local-roots`, { cache: "no-store" });
    if (!res.ok) return { home: "", roots: [] };
    return res.json();
  } catch {
    return { home: "", roots: [] };
  }
}

export async function fetchLocalList(
  path: string,
  opts?: { showHidden?: boolean; q?: string },
): Promise<LocalListResult | null> {
  try {
    const params = new URLSearchParams({ path });
    if (opts?.showHidden) params.set("show_hidden", "true");
    if (opts?.q?.trim()) params.set("q", opts.q.trim());
    const res = await fetch(`${API_URL}/api/projects/local-list?${params}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}
