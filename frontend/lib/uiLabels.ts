/** Arabic-first display labels for API enums and technical tokens shown in UI. */

const PROPOSAL_STATUS_AR: Record<string, string> = {
  draft: "مسودة",
  awaiting_approval: "بانتظار الموافقة",
  revision_requested: "طلب مراجعة",
  approved: "معتمد",
  awaiting_merge: "بانتظار الدمج",
  executing: "قيد التنفيذ",
  merged: "مُدمج",
  rejected: "مرفوض",
  failed: "فشل",
  cancelled: "ملغى",
};

const PROPOSAL_ORIGIN_AR: Record<string, string> = {
  understanding: "فهم المشروع",
  analysis: "التحليل",
  chat: "محادثة الوكيل",
  agent: "الوكيل",
  autopilot: "مساعد الطيار",
  copilot: "مساعد الطيار",
  roadmap: "خارطة الطريق",
  manual: "يدوي",
  evolution: "دورة التطور",
};

const PROJECT_STATUS_AR: Record<string, string> = {
  active: "نشط",
  ready: "جاهز",
  indexing: "فهرسة",
  understanding: "قيد الفهم",
  paused: "موقوف",
  archived: "مؤرشف",
  error: "خطأ",
  draft: "مسودة",
};

const WORKER_STATUS_AR: Record<string, string> = {
  idle: "خامل",
  busy: "مشغول",
  training: "قيد التدريب",
  ready: "جاهز",
  offline: "غير متصل",
  error: "خطأ",
};

const MEMORY_LAYER_AR: Record<string, string> = {
  fact: "حقيقة",
  inference: "استنتاج",
  uncertain: "غير مؤكد",
  episodic: "عرضي",
  semantic: "دلالي",
  procedural: "إجرائي",
  working: "عمل",
  long_term: "طويل الأمد",
  short_term: "قصير الأمد",
};

const SOURCE_TYPE_AR: Record<string, string> = {
  code: "كود",
  file: "ملف",
  docs: "وثائق",
  chat: "محادثة",
  agent: "وكيل",
  analysis: "تحليل",
  understanding: "فهم",
  user: "مستخدم",
  system: "نظام",
  git: "Git",
};

const DEPARTMENT_AR: Record<string, string> = {
  engineering: "الهندسة",
  product: "المنتج",
  design: "التصميم",
  security: "الأمن",
  quality: "الجودة",
  operations: "التشغيل",
  research: "البحث",
  leadership: "القيادة",
  coding: "البرمجة",
  review: "المراجعة",
  planning: "التخطيط",
};

const PLAN_AR: Record<string, string> = {
  free: "مجاني",
  pro: "احترافي",
  team: "فريق",
  enterprise: "مؤسسات",
};

const ACCOUNT_STATUS_AR: Record<string, string> = {
  active: "نشط",
  suspended: "موقوف",
  banned: "محظور",
  pending: "قيد الانتظار",
};

const ROLE_AR: Record<string, string> = {
  user: "عضو",
  admin: "مسؤول",
  member: "عضو",
  owner: "مالك",
};

const AGENT_NAME_AR: Record<string, string> = {
  ChiefAgent: "الوكيل الرئيس",
  MasterOrchestrator: "منسّق المحادثة",
  IndependentCritic: "الناقد المستقل",
  Conductor: "قائد الأوركسترا",
};

function lookup(map: Record<string, string>, raw: string | null | undefined, fallback?: string): string {
  const key = String(raw || "").trim();
  if (!key) return fallback || "—";
  if (map[key]) return map[key];
  const lower = key.toLowerCase();
  if (map[lower]) return map[lower];
  return fallback ?? key;
}

export function proposalStatusLabel(status: string | null | undefined): string {
  return lookup(PROPOSAL_STATUS_AR, status);
}

export function proposalOriginLabel(origin: string | null | undefined): string {
  return lookup(PROPOSAL_ORIGIN_AR, origin);
}

export function projectStatusLabel(status: string | null | undefined): string {
  return lookup(PROJECT_STATUS_AR, status);
}

export function workerStatusLabel(status: string | null | undefined): string {
  return lookup(WORKER_STATUS_AR, status);
}

export function memoryLayerLabel(layer: string | null | undefined): string {
  return lookup(MEMORY_LAYER_AR, layer);
}

export function sourceTypeLabel(source: string | null | undefined): string {
  return lookup(SOURCE_TYPE_AR, source);
}

export function departmentLabel(dept: string | null | undefined): string {
  return lookup(DEPARTMENT_AR, dept);
}

export function planLabel(plan: string | null | undefined): string {
  return lookup(PLAN_AR, plan);
}

export function accountStatusLabel(status: string | null | undefined): string {
  return lookup(ACCOUNT_STATUS_AR, status, "نشط");
}

export function roleLabel(role: string | null | undefined): string {
  return lookup(ROLE_AR, role, String(role || "عضو"));
}

export function agentDisplayName(name: string | null | undefined): string {
  return lookup(AGENT_NAME_AR, name);
}

export function formatNotifyWhen(ts: number): string {
  if (!ts || Number.isNaN(ts)) return "";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "";
  try {
    return new Intl.DateTimeFormat("ar", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(d);
  } catch {
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }
}

export function formatIsoWhen(iso: string | null | undefined): string {
  if (!iso) return "";
  const ts = Date.parse(String(iso));
  if (Number.isNaN(ts)) return String(iso);
  return formatNotifyWhen(ts);
}
