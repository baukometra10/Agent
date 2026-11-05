/** Per-tab cost / time ceilings before teacher escalate. */

export type TabBudget = {
  maxTokens: number;
  maxSeconds: number;
  allowTeacher: boolean;
  tokensUsed: number;
  turns: number;
};

export const DEFAULT_BUDGET: TabBudget = {
  maxTokens: 32000,
  maxSeconds: 180,
  allowTeacher: true,
  tokensUsed: 0,
  turns: 0,
};

export const TOKEN_PRESETS = [2000, 8000, 32000] as const;
export const TIME_PRESETS = [30, 120, 300] as const;

function key(projectId: string) {
  return `spixa.ide.budgets.${projectId}`;
}

export function readBudgets(projectId: string): Record<string, TabBudget> {
  try {
    const raw = JSON.parse(localStorage.getItem(key(projectId)) || "{}");
    return raw && typeof raw === "object" ? raw : {};
  } catch {
    return {};
  }
}

export function getBudget(projectId: string, sessionId: string): TabBudget {
  return { ...DEFAULT_BUDGET, ...(readBudgets(projectId)[sessionId] || {}) };
}

export function setBudget(projectId: string, sessionId: string, patch: Partial<TabBudget>) {
  const all = readBudgets(projectId);
  all[sessionId] = { ...DEFAULT_BUDGET, ...(all[sessionId] || {}), ...patch };
  try {
    localStorage.setItem(key(projectId), JSON.stringify(all));
  } catch {
    /* ignore */
  }
  return all[sessionId];
}

export function estimateTokensFromText(text: string): number {
  // Rough: ~4 chars / token for mixed AR/EN
  return Math.max(1, Math.ceil((text || "").length / 4));
}
