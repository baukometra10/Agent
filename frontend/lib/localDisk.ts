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

export async function fetchLocalRoots(): Promise<{ home: string; roots: LocalRoot[] }> {
  try {
    const res = await fetch(`${API_URL}/api/projects/local-roots`, { cache: "no-store" });
    if (!res.ok) return { home: "", roots: [] };
    return res.json();
  } catch {
    return { home: "", roots: [] };
  }
}

export async function fetchLocalList(path: string): Promise<{
  path: string;
  name?: string;
  parent: string | null;
  folders: LocalEntry[];
  files: LocalEntry[];
} | null> {
  try {
    const res = await fetch(
      `${API_URL}/api/projects/local-list?path=${encodeURIComponent(path)}`,
      { cache: "no-store" },
    );
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}
