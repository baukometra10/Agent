import type {
  AgentTask,
  ExecutionResult,
  Finding,
  KnowledgeNode,
  Project,
  Proposal,
  Roadmap,
} from "./types";

// Default must match start.ps1 safe port (Windows blocks 8000 via Hyper-V ranges).
export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:7000";

export type SpixaAgentInfo = {
  name: string;
  department: string;
  description: string;
  model_role: string;
  can_execute_code?: boolean;
  tier?: string;
  cursor_role?: string;
};

export async function fetchSpixaAgents(): Promise<SpixaAgentInfo[]> {
  try {
    const res = await fetch(`${API_URL}/system/agents`, { cache: "no-store" });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data.agents) ? data.agents : [];
  } catch {
    return [];
  }
}

export type ChiefModel = {
  id: string;
  label: string;
  group?: string;
  tier?: string;
  detail?: string;
  provider?: string;
};

export type ChiefCatalog = {
  upstream?: string;
  upstream_note?: string;
  openrouter_configured?: boolean;
  auto?: { id: string; label: string; detail?: string };
  groups?: { id: string; label: string; models: ChiefModel[] }[];
  models?: ChiefModel[];
};

export async function fetchChiefModels(): Promise<ChiefCatalog | null> {
  try {
    const res = await fetch(`${API_URL}/system/models`, { cache: "no-store" });
    if (!res.ok) return null;
    const data = await res.json();
    return (data.chiefs as ChiefCatalog) || null;
  } catch {
    return null;
  }
}

export async function fetchProjects(): Promise<Project[]> {
  // Merge primary API + local disk agent so opened folders always show in lists
  const { fetchProjectsMerged } = await import("@/lib/projectApi");
  return fetchProjectsMerged();
}

export async function fetchProject(id: string): Promise<Project | null> {
  try {
    const { apiBaseForProject } = await import("@/lib/projectApi");
    const bases = Array.from(
      new Set([apiBaseForProject(id).replace(/\/$/, ""), API_URL.replace(/\/$/, "")]),
    );
    for (const base of bases) {
      try {
        const res = await fetch(`${base}/api/projects/${id}`, { cache: "no-store" });
        if (!res.ok) continue;
        const project = (await res.json()) as Project;
        const { rememberProjectApiBase } = await import("@/lib/projectApi");
        rememberProjectApiBase(id, base);
        return project;
      } catch {
        /* try next */
      }
    }
    return null;
  } catch {
    return null;
  }
}

export async function fetchKnowledge(id: string): Promise<KnowledgeNode[]> {
  try {
    const res = await fetch(`${API_URL}/api/projects/${id}/knowledge`, { cache: "no-store" });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export async function fetchProjectMemory(
  projectId: string,
): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/api/projects/${projectId}/memory`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function upsertProjectEmbedding(
  projectId: string,
  text: string,
  source = "manual",
): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/api/projects/${projectId}/memory/embeddings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, source }),
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function searchProjectEmbeddings(
  projectId: string,
  query: string,
  topK = 5,
): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/api/projects/${projectId}/memory/embeddings/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, top_k: topK }),
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchProposals(projectId: string, status?: string): Promise<Proposal[]> {
  try {
    const q = status ? `?status=${encodeURIComponent(status)}` : "";
    const res = await fetch(`${API_URL}/api/projects/${projectId}/proposals${q}`, {
      cache: "no-store",
    });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export async function approveProposal(projectId: string, proposalId: string): Promise<Proposal | null> {
  try {
    const res = await fetch(`${API_URL}/api/projects/${projectId}/proposals/${proposalId}/approve`, {
      method: "POST",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function executeProposal(
  projectId: string,
  proposalId: string,
): Promise<ExecutionResult | null> {
  try {
    const res = await fetch(`${API_URL}/api/projects/${projectId}/proposals/${proposalId}/execute`, {
      method: "POST",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function mergeProposal(
  projectId: string,
  proposalId: string,
): Promise<ExecutionResult | null> {
  try {
    const res = await fetch(`${API_URL}/api/projects/${projectId}/proposals/${proposalId}/merge`, {
      method: "POST",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchRoadmap(projectId: string): Promise<Roadmap | null> {
  try {
    const res = await fetch(`${API_URL}/api/projects/${projectId}/roadmap`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchFindings(projectId: string): Promise<Finding[]> {
  try {
    const res = await fetch(`${API_URL}/api/projects/${projectId}/findings`, { cache: "no-store" });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export async function fetchTasks(projectId: string): Promise<AgentTask[]> {
  try {
    const res = await fetch(`${API_URL}/api/projects/${projectId}/tasks`, { cache: "no-store" });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export async function runUnderstanding(projectId: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/api/projects/${projectId}/understand`, { method: "POST" });
    return res.ok;
  } catch {
    return false;
  }
}

export async function runDesign(projectId: string, brief = ""): Promise<Record<string, unknown> | null> {
  try {
    const q = brief ? `?brief=${encodeURIComponent(brief)}` : "";
    const res = await fetch(`${API_URL}/api/projects/${projectId}/design/run${q}`, { method: "POST" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function runQuality(
  projectId: string,
  focus = "full",
): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(
      `${API_URL}/api/projects/${projectId}/quality/run?focus=${encodeURIComponent(focus)}`,
      { method: "POST" },
    );
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function planDeploy(
  projectId: string,
  target = "staging",
): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(
      `${API_URL}/api/projects/${projectId}/deploy/plan?target=${encodeURIComponent(target)}`,
      { method: "POST" },
    );
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function confirmDeploy(
  projectId: string,
  target = "staging",
  proposalId?: string,
): Promise<Record<string, unknown> | null> {
  try {
    const params = new URLSearchParams({ target });
    if (proposalId) params.set("proposal_id", proposalId);
    const res = await fetch(`${API_URL}/api/projects/${projectId}/deploy/confirm?${params}`, {
      method: "POST",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function runEvolution(projectId: string): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/api/projects/${projectId}/evolve`, { method: "POST" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchFleet(): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/api/control-plane/fleet`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function evolveFleet(limit = 20): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/api/control-plane/evolve-all?limit=${limit}`, {
      method: "POST",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function createProjectFromPath(input: {
  name: string;
  local_path: string;
  description?: string;
}): Promise<Project | null> {
  try {
    const { resolveDiskApiBase } = await import("@/lib/localDisk");
    const { rememberProjectApiBase } = await import("@/lib/projectApi");
    const disk = await resolveDiskApiBase();
    const base = disk.unreachable ? API_URL : disk.diskBase;
    const res = await fetch(`${base.replace(/\/$/, "")}/api/projects/from-path`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    if (!res.ok) return null;
    const project = (await res.json()) as Project;
    if (project?.id) rememberProjectApiBase(String(project.id), base);
    return project;
  } catch {
    return null;
  }
}

export async function createBlankProject(input: {
  name: string;
  description?: string;
  owner_email?: string;
}): Promise<Project | null> {
  try {
    const { resolveDiskApiBase } = await import("@/lib/localDisk");
    const { rememberProjectApiBase } = await import("@/lib/projectApi");
    const disk = await resolveDiskApiBase();
    const base = disk.unreachable ? API_URL : disk.diskBase;
    const res = await fetch(`${base.replace(/\/$/, "")}/api/projects/blank`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    if (!res.ok) return null;
    const project = (await res.json()) as Project;
    if (project?.id) rememberProjectApiBase(String(project.id), base);
    return project;
  } catch {
    return null;
  }
}

export type ModelGatewayStatus = {
  routes: Record<string, string>;
  providers: Record<
    string,
    { configured: boolean; live: boolean; tier?: string; host?: string; note?: string }
  >;
  force_simulate: boolean;
  prefer_internal?: boolean;
  teacher_upstream?: string;
  teacher_upstream_active?: string;
  teacher_upstream_live?: boolean;
  teacher_bootstrap_first?: boolean;
  mode: string;
  internal_family?: Array<Record<string, unknown>>;
  router?: Record<string, unknown>;
  ownership_goal?: { target_internal_coverage: number; doctrine: string };
  distillation?: Record<string, unknown>;
};

export async function fetchModelGateway(): Promise<ModelGatewayStatus | null> {
  try {
    const res = await fetch(`${API_URL}/system/models`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function probeModelGateway(
  role = "fast",
): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/system/models/probe?role=${encodeURIComponent(role)}`, {
      method: "POST",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchOwnershipHandoff(): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/system/ownership/handoff`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchOwnershipCoverage(): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/system/ownership/coverage`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function climbOwnershipCoverage(opts?: {
  n?: number;
  reset?: boolean;
  mode?: "meter" | "live";
}): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/system/ownership/coverage/climb`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        n: opts?.n ?? 8,
        role: "coding",
        reset: opts?.reset ?? false,
        mode: opts?.mode ?? "meter",
      }),
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function retireTeachers(opts?: {
  specialty?: string;
  all_ready?: boolean;
}): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/system/ownership/retire`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        specialty: opts?.specialty,
        all_ready: opts?.all_ready ?? !opts?.specialty,
        reason: "ui",
      }),
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function restoreTeachers(
  specialty: string,
): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/system/ownership/restore`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ specialty, reason: "ui_restore" }),
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function distillProjectHandoff(
  projectId: string,
): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/system/ownership/handoff/distill-project`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: projectId, limit: 40 }),
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchCostEfficiency(): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/system/ownership/cost-efficiency`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchOwnership(): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/system/ownership`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function runOwnershipEval(
  specialty = "project_intelligence",
): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(
      `${API_URL}/system/ownership/eval?specialty=${encodeURIComponent(specialty)}`,
      { method: "POST" },
    );
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function trainProjectIntelLora(): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/system/ownership/train/lora`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        specialty: "project_intelligence",
        run_eval: true,
        force_placeholder: false,
      }),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) return data;
    return data;
  } catch {
    return null;
  }
}

export async function seedCodingCurriculum(): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/system/ownership/seed/coding`, { method: "POST" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function seedCodingTutor(): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/system/ownership/seed/coding-tutor`, {
      method: "POST",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function runLearningCycle(): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/system/ownership/learning/cycle`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        specialties: ["project_intelligence", "coding", "reasoning", "critic"],
        seed: true,
        train: true,
      }),
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function growSpecialtyDatasets(): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/system/ownership/seed/grow`, { method: "POST" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function promoteAllSpecialties(): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/system/ownership/promote/all`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ grow_first: true }),
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchAutopilot(): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/system/autopilot`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchAutopilotReports(): Promise<Record<string, unknown>[]> {
  try {
    const res = await fetch(`${API_URL}/system/autopilot/reports?limit=10`, {
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = await res.json();
    return (data.reports || []) as Record<string, unknown>[];
  } catch {
    return [];
  }
}

export async function enableAutopilot(
  notifyEmail?: string,
): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/system/autopilot/enable`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notify_email: notifyEmail || null }),
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function disableAutopilot(): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/system/autopilot/disable`, { method: "POST" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function resumeAutopilot(): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/system/autopilot/resume`, { method: "POST" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function runAutopilot(
  notifyEmail?: string,
): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/system/autopilot/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ force: true, notify_email: notifyEmail || null }),
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchChiefStatus(): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/system/chief`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function chiefSaturateDemo(n = 5): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_URL}/system/chief/demo/saturate?n=${n}`, { method: "POST" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}
