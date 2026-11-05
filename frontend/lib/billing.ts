import { API_URL } from "@/lib/api";
import { loadUser, saveUser, hasTokens, type UserProfile } from "@/lib/user";

export const FEATURE_LABELS_AR: Record<string, string> = {
  chat: "محادثة الوكيل",
  projects: "المشاريع",
  proposals: "المقترحات",
  execution: "التنفيذ",
  copilot: "مساعد الطيار",
  understanding: "فهم المشروع",
  analysis: "التحليل الذكي",
  knowledge: "المعرفة",
  roadmap: "خارطة الطريق",
  agents_view: "فريق الوكلاء",
  admin_console: "وحدة التحكم",
  model_training: "تدريب النماذج",
  ownership: "ملكية النماذج",
  fleet: "الأسطول",
  self_maintain: "صيانة ذاتية",
  billing_ops: "عمليات الفوترة",
};

/** Map app routes → required entitlement (null = always allowed when signed in). */
export const ROUTE_FEATURE: Record<string, string | null> = {
  "/": null,
  "/console": null,
  "/pricing": null,
  "/download": null,
  "/help": null,
  "/login": null,
  "/account": null,
  "/log": null,
  "/ide": "projects",
  "/brain": "chat",
  "/projects": "projects",
  "/copilot": "copilot",
  "/understanding": "understanding",
  "/analysis": "analysis",
  "/knowledge": "knowledge",
  "/agents": "agents_view",
  "/roadmap": "roadmap",
  "/proposals": "proposals",
  "/execution": "execution",
  "/admin": "admin_console",
  "/control-plane": "fleet",
  "/maintain": "self_maintain",
  "/settings": "model_training",
};

export function featureForPath(pathname: string): string | null | undefined {
  if (ROUTE_FEATURE[pathname] !== undefined) return ROUTE_FEATURE[pathname];
  const base = "/" + (pathname.split("/").filter(Boolean)[0] || "");
  return ROUTE_FEATURE[base];
}

export async function spendTokens(
  amount = 1,
  reason = "agent_task",
): Promise<{ ok: boolean; tokensRemaining?: number; error?: string }> {
  const profile = loadUser();
  if (!profile.email || !profile.signedIn) {
    return { ok: false, error: "not_signed_in" };
  }
  if (!hasTokens(profile, amount)) {
    return { ok: false, error: "insufficient_tokens", tokensRemaining: profile.tokensRemaining };
  }
  try {
    const res = await fetch(`${API_URL}/system/billing/spend`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: profile.email, amount, reason }),
    });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      return {
        ok: false,
        error: String(data.error || "spend_failed"),
        tokensRemaining: data.tokens_remaining,
      };
    }
    const next: UserProfile = {
      ...profile,
      tokensRemaining: Number(data.tokens_remaining ?? profile.tokensRemaining),
    };
    saveUser(next);
    return { ok: true, tokensRemaining: next.tokensRemaining };
  } catch {
    return { ok: false, error: "network" };
  }
}
