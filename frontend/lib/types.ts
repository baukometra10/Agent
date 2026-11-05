export type Project = {
  id: string;
  name: string;
  slug: string;
  status: string;
  description?: string | null;
  frameworks: string[];
  languages: { name: string; files: number }[];
  understanding_progress: number;
  isolation_namespace: string;
  workspace_path?: string | null;
  source_uri?: string | null;
  source_type?: string | null;
  file_stats?: { total_files?: number };
};

export type KnowledgeNode = {
  id: string;
  kind: "fact" | "inference" | "unverified";
  title: string;
  content: string;
  confidence: number;
  memory_layer: string;
  category: string;
  source_type: string;
  source_path: string | null;
};

export type Proposal = {
  id: string;
  title: string;
  problem: string;
  proposal: string;
  status: string;
  priority: number;
  origin: string;
  category: string;
};

export type ExecutionResult = {
  status: string;
  branch?: string | null;
  commit?: string | null;
  merged: boolean;
  next_step?: string | null;
  applied?: Record<string, unknown> | null;
  review?: Record<string, unknown> | null;
  sandbox?: Record<string, unknown> | null;
};

export type RoadmapItem = {
  id: string;
  title: string;
  description: string;
  status: string;
  priority: number;
  category: string;
};

export type Roadmap = {
  id: string;
  title: string;
  vision: string;
  status: string;
  version: number;
  items: RoadmapItem[];
};

export type Finding = {
  id: string;
  title: string;
  description: string;
  kind: string;
  severity: string;
  category: string;
  status: string;
  recommendation?: string;
};

export type AgentTask = {
  id: string;
  agent_name: string;
  department: string;
  objective: string;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
};
