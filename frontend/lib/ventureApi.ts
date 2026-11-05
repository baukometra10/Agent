import { API_URL } from "@/lib/api";

export type VenturePhase = {
  id: string;
  name: string;
  label: string;
  sort_order: number;
  status: string;
  requires_approval: boolean;
  output?: Record<string, unknown>;
  approved_at?: string | null;
  approved_by?: string | null;
};

export type VentureRun = {
  id: string;
  project_id: string;
  title: string;
  brief: string;
  status: string;
  current_phase: string;
  selected_architecture_id?: string | null;
  proposal_id?: string | null;
  decision_log?: unknown[];
  artifacts?: Record<string, unknown>;
  phases: VenturePhase[];
  created_at?: string | null;
};

async function jsonOrNull<T>(res: Response): Promise<T | null> {
  if (!res.ok) return null;
  return res.json();
}

export async function listVentures(projectId: string): Promise<VentureRun[]> {
  const res = await fetch(`${API_URL}/api/projects/${projectId}/ventures`, { cache: "no-store" });
  const data = await jsonOrNull<VentureRun[]>(res);
  return Array.isArray(data) ? data : [];
}

export async function createVenture(
  projectId: string,
  brief: string,
  title?: string,
): Promise<VentureRun | null> {
  const res = await fetch(`${API_URL}/api/projects/${projectId}/ventures`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ brief, title }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(String((err as { detail?: string }).detail || `HTTP ${res.status}`));
  }
  return res.json();
}

export async function startCompanyOsDemo(projectId: string): Promise<VentureRun | null> {
  const res = await fetch(`${API_URL}/api/projects/${projectId}/ventures/demo/company-os`, {
    method: "POST",
  });
  return jsonOrNull<VentureRun>(res);
}

export async function getVenture(projectId: string, ventureId: string): Promise<VentureRun | null> {
  const res = await fetch(`${API_URL}/api/projects/${projectId}/ventures/${ventureId}`, {
    cache: "no-store",
  });
  return jsonOrNull<VentureRun>(res);
}

export async function approveVenture(
  projectId: string,
  ventureId: string,
  selectedArchitectureId?: string | null,
  acknowledgeAdversarial = false,
): Promise<VentureRun | null> {
  const res = await fetch(`${API_URL}/api/projects/${projectId}/ventures/${ventureId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      actor: "human",
      selected_architecture_id: selectedArchitectureId || null,
      acknowledge_adversarial: acknowledgeAdversarial,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(String((err as { detail?: string }).detail || res.statusText));
  }
  return res.json();
}

export async function rejectVenture(
  projectId: string,
  ventureId: string,
  reason = "",
): Promise<VentureRun | null> {
  const res = await fetch(`${API_URL}/api/projects/${projectId}/ventures/${ventureId}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason, actor: "human" }),
  });
  return jsonOrNull<VentureRun>(res);
}

export async function rebuildTwin(projectId: string): Promise<Record<string, unknown> | null> {
  const res = await fetch(`${API_URL}/api/projects/${projectId}/twin/rebuild`, { method: "POST" });
  return jsonOrNull(res);
}

export async function simulateTwin(
  projectId: string,
  changeSummary: string,
  affectedPaths: string[] = [],
): Promise<Record<string, unknown> | null> {
  const res = await fetch(`${API_URL}/api/projects/${projectId}/twin/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ change_summary: changeSummary, affected_paths: affectedPaths }),
  });
  return jsonOrNull(res);
}

export type SpixaPattern = {
  id: string;
  slug: string;
  title: string;
  summary: string;
  category: string;
  approved: boolean;
  confidence?: number;
};

export async function listPatterns(): Promise<SpixaPattern[]> {
  const res = await fetch(`${API_URL}/api/patterns`, { cache: "no-store" });
  const data = await jsonOrNull<{ patterns: SpixaPattern[] }>(res);
  return data?.patterns || [];
}

export async function listResearchExperiments(): Promise<Record<string, unknown>[]> {
  const res = await fetch(`${API_URL}/api/system/research/experiments`, { cache: "no-store" });
  const data = await jsonOrNull<{ experiments: Record<string, unknown>[] }>(res);
  return data?.experiments || [];
}

export async function createResearchExperiment(input: {
  title: string;
  hypothesis: string;
  kind?: string;
}): Promise<Record<string, unknown> | null> {
  const res = await fetch(`${API_URL}/api/system/research/experiments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return jsonOrNull(res);
}

export async function runResearchExperiment(id: string): Promise<Record<string, unknown> | null> {
  const res = await fetch(`${API_URL}/api/system/research/experiments/${id}/run`, { method: "POST" });
  return jsonOrNull(res);
}

export async function requestResearchPromote(id: string): Promise<Record<string, unknown> | null> {
  const res = await fetch(`${API_URL}/api/system/research/experiments/${id}/request-promote`, {
    method: "POST",
  });
  return jsonOrNull(res);
}

export async function decideResearchPromote(
  id: string,
  approve: boolean,
): Promise<Record<string, unknown> | null> {
  const res = await fetch(`${API_URL}/api/system/research/experiments/${id}/decide-promote`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approve, actor: "human" }),
  });
  return jsonOrNull(res);
}
