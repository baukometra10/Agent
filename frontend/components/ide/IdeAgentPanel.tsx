"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type MouseEvent,
} from "react";
import { createPortal } from "react-dom";
import { AgentCompareModal } from "@/components/ide/AgentCompareModal";
import { AgentEditReview } from "@/components/ide/AgentEditReview";
import {
  boostCoreSpecialties,
  fetchLearningPulse,
  learnFromOperation,
  rapidLearnFromIdeApply,
  recordCodingHumanAcceptance,
  type LearningPulse,
} from "@/lib/maturity";
import { API_URL, fetchChiefModels, type ChiefCatalog, type ChiefModel } from "@/lib/api";
import { apiBaseForProject, resolveProjectApiBase } from "@/lib/projectApi";
import {
  fetchProjectPreferences,
  fetchWorkspaceFile,
  saveProjectPreferences,
  verifyWorkspacePreview,
  type ProjectPreferences,
} from "@/lib/workspace";
import {
  detectUserLang,
  displayAgentReply,
  ensureBuildEdits,
  userWantsFileWrites,
  filterNoopEdits,
  parseAgentEdits,
  type FileEdit,
} from "@/lib/agentEdits";
import {
  DEFAULT_BUDGET,
  TIME_PRESETS,
  TOKEN_PRESETS,
  estimateTokensFromText,
  getBudget,
  setBudget,
  type TabBudget,
} from "@/lib/agentPanel/budgets";
import {
  clearCheckpoint,
  getCheckpoint,
  readCheckpoints,
  writeCheckpoint,
  type ResumeCheckpoint,
} from "@/lib/agentPanel/checkpoints";
import {
  createShareLink,
  createTemplate,
  deleteTemplate,
  fetchTabsState,
  fetchTemplates,
  putTabsState,
  type CommandTemplate,
} from "@/lib/agentPanel/agentUiApi";
import { buildChatMarkdown, downloadText, openPrintableHtml } from "@/lib/agentPanel/exportChat";
import { ensureNotifyPermission, notifyTabDone } from "@/lib/agentPanel/notify";
import { buildSuggestions } from "@/lib/agentPanel/suggestions";
import type { TabSnapshot } from "@/lib/agentPanel/tabDiff";
import { spendTokens } from "@/lib/billing";
import {
  createLiveSpeechSession,
  dirForLanguage,
  speechSupported,
  type SpeechSession,
} from "@/lib/speechInput";
import { isPlaceholderTitle, topicTitleFromMessage } from "@/lib/topicTitle";
import { hasFeature, hasTokens, loadUser } from "@/lib/user";

type SpecialistEval = {
  agent?: string;
  score?: number;
  solved?: string;
  blocked?: string;
  needs?: string;
};

type DecisionLog = {
  why?: string;
  intent?: string | null;
  intent_label?: string | null;
  conductor?: string | null;
  specialists?: string[];
  tools_used?: string[];
  route_tier?: string | null;
  model?: string | null;
  simulated?: boolean;
  files_hint?: string[];
  evaluations?: SpecialistEval[];
};

type AgentStatus = {
  phase: string;
  label: string;
  step?: number;
  total?: number;
};

type Msg = {
  role: "user" | "assistant";
  text: string;
  edits?: FileEdit[];
  pendingEdits?: FileEdit[];
  specialists?: string[];
  buildPhase?: string | null;
  agent?: string | null;
  routeTier?: string | null;
  model?: string | null;
  simulated?: boolean;
  streaming?: boolean;
  status?: AgentStatus | null;
  decision?: DecisionLog | null;
};

type TabDraft = {
  text: string;
  attachments: string[];
  focusPath?: string | null;
};

type AgentTab = {
  id: string;
  title: string;
  pinned?: boolean;
};

type SessionRow = {
  id: string;
  title: string;
  status: string;
  created_at?: string;
  updated_at?: string;
};

const CHIEF_STORAGE_KEY = "spixa.ide.chief";

function tabsStorageKey(projectId: string) {
  return `spixa.ide.agentTabs.${projectId}`;
}

function archiveStorageKey(projectId: string) {
  return `spixa.ide.agentArchive.${projectId}`;
}

type ArchiveMemory = { id: string; title: string; archived_at: string };

function readLocalArchive(projectId: string): ArchiveMemory[] {
  try {
    const raw = JSON.parse(localStorage.getItem(archiveStorageKey(projectId)) || "[]");
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
}

function writeLocalArchive(projectId: string, rows: ArchiveMemory[]) {
  try {
    localStorage.setItem(archiveStorageKey(projectId), JSON.stringify(rows.slice(0, 80)));
  } catch {
    /* ignore */
  }
}

function rememberLocalArchive(projectId: string, id: string, title: string) {
  const prev = readLocalArchive(projectId).filter((r) => r.id !== id);
  prev.unshift({ id, title: title || "أمر جديد", archived_at: new Date().toISOString() });
  writeLocalArchive(projectId, prev);
}

function updateLocalArchiveTitle(projectId: string, id: string, title: string) {
  const clean = (title || "").trim();
  if (!clean) return;
  const prev = readLocalArchive(projectId);
  let changed = false;
  const next = prev.map((r) => {
    if (r.id !== id) return r;
    changed = true;
    return { ...r, title: clean };
  });
  if (changed) writeLocalArchive(projectId, next);
}

function forgetLocalArchive(projectId: string, id: string) {
  writeLocalArchive(
    projectId,
    readLocalArchive(projectId).filter((r) => r.id !== id),
  );
}

function routeLabel(
  tier: string | null | undefined,
  simulated?: boolean,
  model?: string | null,
): { text: string; kind: string } {
  if (simulated) return { text: "Sim", kind: "sim" };
  const m = (model || "").toLowerCase();
  if (m.includes("cursor")) return { text: "Cursor", kind: "teacher" };
  const t = (tier || "").toLowerCase();
  if (t === "internal" || t === "cache") return { text: "Owned", kind: "owned" };
  if (t === "simulate") return { text: "Sim", kind: "sim" };
  if (t === "teacher") return { text: "Teacher", kind: "teacher" };
  return { text: "Auto", kind: "auto" };
}

function formatRouteModel(model?: string | null, simulated?: boolean): string {
  if (simulated) return "not live";
  const m = (model || "").trim();
  if (!m) return "";
  if (m.toLowerCase().includes("cursor")) return "Cursor Cloud Agent";
  // Never dress a simulated/legacy OpenRouter id as the live teacher when Cursor is selected
  return m;
}

const UI_LANG = {
  ar: {
    why: "لماذا؟",
    understood: "فهم الطلب",
    executing: "تنفيذ الطلب في مساحة العمل.",
    thinking: "يفكر…",
    writing: "يكتب الملفات…",
  },
  de: {
    why: "Warum?",
    understood: "Anfrage verstanden",
    executing: "Umsetzung im Workspace.",
    thinking: "Denkt nach…",
    writing: "Schreibt Dateien…",
  },
  en: {
    why: "Why?",
    understood: "Understood",
    executing: "Executing in the workspace.",
    thinking: "Thinking…",
    writing: "Writing files…",
  },
} as const;

const STATUS_PHASE_LABEL: Record<string, { ar: string; de: string; en: string }> = {
  thinking: { ar: "يفكر…", de: "Denkt nach…", en: "Thinking…" },
  understand: { ar: "يفهم الطلب…", de: "Versteht die Anfrage…", en: "Understanding…" },
  reading: { ar: "يقرأ المشروع…", de: "Liest das Projekt…", en: "Reading the project…" },
  plan: { ar: "يضع خطة…", de: "Plant…", en: "Planning…" },
  planning: { ar: "يضع خطة…", de: "Plant den nächsten Schritt…", en: "Planning next steps…" },
  implement: { ar: "يجهّز التنفيذ…", de: "Bereitet Umsetzung vor…", en: "Preparing implement…" },
  generating: { ar: "يكتب الرد…", de: "Schreibt die Antwort…", en: "Writing the reply…" },
  streaming: { ar: "يبث الرد…", de: "Antwort kommt…", en: "Streaming reply…" },
  writing: { ar: "يكتب الملفات…", de: "Schreibt Dateien…", en: "Writing files…" },
  cursor_start: {
    ar: "تشغيل Cursor Cloud Agent…",
    de: "Startet Cursor Cloud Agent…",
    en: "Starting Cursor Cloud Agent…",
  },
  cursor_creating: {
    ar: "Cursor: إنشاء الوكيل…",
    de: "Cursor: Agent wird erstellt…",
    en: "Creating Cursor agent…",
  },
  cursor_pending: { ar: "Cursor: بانتظار…", de: "Cursor: wartet…", en: "Cursor waiting…" },
  cursor_running: {
    ar: "Cursor: يعمل على الكود…",
    de: "Cursor: arbeitet am Code…",
    en: "Cursor working on code…",
  },
  cursor_done: {
    ar: "Cursor انتهى — جاري تطبيق الرد…",
    de: "Cursor fertig — Antwort wird übernommen…",
    en: "Cursor finished — applying reply…",
  },
  cursor_error: { ar: "خطأ Cursor", de: "Cursor-Fehler", en: "Cursor error" },
  cursor_cancelled: { ar: "أُلغي Cursor", de: "Cursor abgebrochen", en: "Cursor cancelled" },
  cursor_expired: { ar: "انتهت مهلة Cursor", de: "Cursor abgelaufen", en: "Cursor expired" },
};

function statusLabelFor(phase: string, fallback: string, lang: "ar" | "de" | "en"): string {
  const row = STATUS_PHASE_LABEL[phase];
  if (row) return row[lang];
  return fallback || UI_LANG[lang].thinking;
}

const INTENT_LABEL: Record<string, { ar: string; de: string; en: string }> = {
  design: { ar: "تصميم وواجهة", de: "Design & UI", en: "Design & UI" },
  security: { ar: "أمن وثغرات", de: "Sicherheit", en: "Security" },
  quality: { ar: "اختبار وجودة", de: "Qualität & Tests", en: "Quality & tests" },
  ops: { ar: "تشغيل ونشر", de: "Betrieb & Deploy", en: "Ops & deploy" },
  docs: { ar: "توثيق", de: "Dokumentation", en: "Docs" },
  refactor: { ar: "إعادة هيكلة", de: "Refactoring", en: "Refactor" },
  implement: { ar: "بناء وتطوير", de: "Bauen & entwickeln", en: "Build & develop" },
  analyze: { ar: "فهم وتحليل", de: "Analyse", en: "Analyze" },
  product: { ar: "منتج ومتطلبات", de: "Produkt & Anforderungen", en: "Product" },
};

function intentLabelFor(intent: string | null | undefined, lang: "ar" | "de" | "en"): string {
  const key = (intent || "").toLowerCase();
  const row = INTENT_LABEL[key];
  if (row) return row[lang];
  // If backend sent Arabic label_ar, map known ones; otherwise show raw only for same lang.
  if (lang === "ar" && intent) return intent;
  for (const [k, v] of Object.entries(INTENT_LABEL)) {
    if (v.ar === intent) return v[lang];
  }
  return intent || (lang === "de" ? "Allgemein" : lang === "ar" ? "عام" : "general");
}

function displayStoredUser(content: string): string {
  const marker = "طلب المستخدم:";
  const i = content.lastIndexOf(marker);
  if (i >= 0) return content.slice(i + marker.length).trim();
  return content;
}

function shortTitle(title: string | null | undefined, fallback = "أمر جديد"): string {
  const t = (title || "").trim() || fallback;
  return t.length > 32 ? `${t.slice(0, 30)}…` : t;
}

type AgentMode = "agent" | "ask" | "edit";

type Props = {
  projectId: string;
  activePath: string | null;
  treePaths?: string[];
  onApplyEdits: (edits: FileEdit[]) => Promise<void>;
  onOpenPath?: (path: string) => void;
  onLog?: (text: string) => void;
  /** Open this session after boot (share link / deep link) */
  initialSessionId?: string | null;
  /** Hand current draft/message to Venture panel */
  onStartVenture?: (brief: string) => void;
  /** Called after agent applies UI/web file edits — start Live Preview */
  onAfterWebEdits?: (paths: string[]) => void;
  /** Current Live Preview URL if running */
  livePreviewUrl?: string | null;
};

const BUILD_PHASE_LABEL: Record<string, { ar: string; de: string; en: string }> = {
  understand: { ar: "فهم", de: "Verstehen", en: "Understand" },
  plan: { ar: "خطة", de: "Plan", en: "Plan" },
  implement: { ar: "تنفيذ", de: "Umsetzen", en: "Implement" },
  idle: { ar: "جاهز", de: "Bereit", en: "Ready" },
};

const SCAFFOLD_RULES =
  "Spixa IDE — answer like Cursor Chat (short, clear, elite engineer).\n" +
  "Reply ONLY in the user's language.\n" +
  "WORKFLOW every turn: (1) understand what they want in 1 sentence, " +
  "(2) plan max 4 steps for THIS workspace, " +
  "(3) implement with ```path fences ONLY if they asked to write/code/apply this turn — " +
  "otherwise ask before coding. Never dump the same boilerplate files again.\n" +
  "When implementing a full app/site: ship a coherent runnable vertical " +
  "(entry + styles + logic), wired together — design what they want, build what they want.\n" +
  "After UI/web edits, remind them to use Live Preview (معاينة) to test while building.\n" +
  "Use the real project files listed below. Do NOT repeat these instructions in your answer.\n";

const MODE_HINT: Record<AgentMode, string> = {
  agent:
    "Mode=agent: understand → plan → ask before writing unless they already said implement/schreib/اكتب/طبق; then real file fences only.",
  ask: "Mode=ask: clear answer/options in user language; no file fences.",
  edit: "Mode=edit: one-sentence plan, then smallest real file change only if they want a write.",
};

const FALLBACK_CHIEFS: ChiefModel[] = [
  { id: "auto", label: "Auto", tier: "", detail: "داخلي أولاً → تصعيد عند الحاجة" },
  { id: "internal", label: "Spixa Internal", tier: "Owned", group: "spixa" },
  { id: "openai/gpt-4.1", label: "GPT-4.1", tier: "High", group: "other" },
  { id: "anthropic/claude-sonnet-4.5", label: "Claude Sonnet 4.5", tier: "High", group: "other" },
];

function isWebPreviewPath(path: string): boolean {
  return /\.(html?|css|jsx?|tsx?|vue|svelte)$/i.test(path || "");
}

export function IdeAgentPanel({
  projectId,
  activePath,
  treePaths = [],
  onApplyEdits,
  onOpenPath,
  onLog,
  initialSessionId = null,
  onStartVenture,
  onAfterWebEdits,
  livePreviewUrl = null,
}: Props) {
  const [tabs, setTabs] = useState<AgentTab[]>([]);
  const [activeTabId, setActiveTabId] = useState<string | null>(null);
  const [msgsByTab, setMsgsByTab] = useState<Record<string, Msg[]>>({});
  const [loadedTabs, setLoadedTabs] = useState<Record<string, boolean>>({});
  const [allSessions, setAllSessions] = useState<SessionRow[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [text, setText] = useState("");
  /** Per-tab running AI — multiple chats can work in parallel */
  const [busyByTab, setBusyByTab] = useState<Record<string, boolean>>({});
  const [draftsByTab, setDraftsByTab] = useState<Record<string, TabDraft>>({});
  const [error, setError] = useState("");
  const [mode, setMode] = useState<AgentMode>("agent");
  const [modeMenu, setModeMenu] = useState(false);
  const [chiefMenu, setChiefMenu] = useState(false);
  const [menuStyle, setMenuStyle] = useState<CSSProperties>({});
  const [creatingTab, setCreatingTab] = useState(false);
  const [attachOpen, setAttachOpen] = useState(false);
  const [attachQ, setAttachQ] = useState("");
  const [archiveQuery, setArchiveQuery] = useState("");
  const [chiefs, setChiefs] = useState<ChiefCatalog | null>(null);
  const [preferredProvider, setPreferredProvider] = useState<string>("auto");
  const [chiefSearch, setChiefSearch] = useState("");
  const [attachments, setAttachments] = useState<string[]>([]);
  const [tabFocusPath, setTabFocusPath] = useState<string | null>(null);
  const [resumeByTab, setResumeByTab] = useState<Record<string, ResumeCheckpoint>>({});
  const [budgetByTab, setBudgetByTab] = useState<Record<string, TabBudget>>({});
  const [budgetOpen, setBudgetOpen] = useState(false);
  // Cursor-like default: write files immediately (no Accept clicks).
  const [reviewBeforeApply, setReviewBeforeApply] = useState(false);
  /** Full vertical app build: plan briefly then implement runnable files this turn */
  const [fullBuild, setFullBuild] = useState(false);
  const [prefs, setPrefs] = useState<ProjectPreferences>({});
  const [prefsOpen, setPrefsOpen] = useState(false);
  const [learnPulse, setLearnPulse] = useState<LearningPulse | null>(null);
  const [learnFlash, setLearnFlash] = useState("");
  const boostStarted = useRef(false);
  const [compareIds, setCompareIds] = useState<[string, string] | null>(null);
  const [pickCompare, setPickCompare] = useState<string | null>(null);
  const [templates, setTemplates] = useState<CommandTemplate[]>([]);
  const [templatesOpen, setTemplatesOpen] = useState(false);
  const [decisionOpen, setDecisionOpen] = useState<Record<string, boolean>>({});
  const syncTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const initialSessionHandled = useRef(false);
  const [lastRoute, setLastRoute] = useState<{ tier?: string | null; model?: string | null; simulated?: boolean }>(
    {},
  );
  const [listening, setListening] = useState(false);
  const [interimSpeech, setInterimSpeech] = useState("");
  const [speechDir, setSpeechDir] = useState<"rtl" | "ltr">("rtl");
  const [detectedLang, setDetectedLang] = useState<string>("auto");
  const [micAvailable, setMicAvailable] = useState(false);
  const [dragTabId, setDragTabId] = useState<string | null>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const tabsRef = useRef<HTMLDivElement>(null);
  const threadRef = useRef<HTMLDivElement>(null);
  const threadEndRef = useRef<HTMLDivElement>(null);
  const modeBtnRef = useRef<HTMLButtonElement>(null);
  const chiefBtnRef = useRef<HTMLButtonElement>(null);
  const creatingTabRef = useRef(false);
  const bootRef = useRef(false);
  const abortByTabRef = useRef<Record<string, AbortController>>({});
  const speechRef = useRef<SpeechSession | null>(null);
  const textRef = useRef(text);
  const speechBaseRef = useRef("");
  textRef.current = text;

  const scrollThreadToEnd = useCallback((smooth = false) => {
    const run = () => {
      const end = threadEndRef.current;
      const thread = threadRef.current;
      if (end) {
        end.scrollIntoView({ block: "end", behavior: smooth ? "smooth" : "auto" });
      }
      if (thread) {
        thread.scrollTop = thread.scrollHeight;
      }
    };
    requestAnimationFrame(() => {
      run();
      // Second pass after layout (images/review blocks / late message patch)
      window.setTimeout(run, 40);
    });
  }, []);

  function placeMenuAbove(btn: HTMLButtonElement | null) {
    if (!btn || typeof window === "undefined") return;
    const r = btn.getBoundingClientRect();
    const width = Math.max(r.width, 220);
    const left = Math.min(Math.max(8, r.right - width), window.innerWidth - width - 8);
    setMenuStyle({
      position: "fixed",
      left,
      top: Math.max(8, r.top - 8),
      transform: "translateY(-100%)",
      width,
      maxHeight: Math.min(360, Math.max(160, r.top - 16)),
      zIndex: 400,
    });
  }

  function closeMenus() {
    setModeMenu(false);
    setChiefMenu(false);
  }

  function joinSpeech(base: string, piece: string) {
    const b = base.trimEnd();
    const p = piece.trim();
    if (!p) return b;
    if (!b) return p;
    return `${b} ${p}`;
  }

  const msgs = activeTabId ? msgsByTab[activeTabId] || [] : [];
  const activeTab = tabs.find((t) => t.id === activeTabId) || null;
  const activeBusy = Boolean(activeTabId && busyByTab[activeTabId]);
  const lastMsg = msgs[msgs.length - 1];
  const lastMsgSig = `${msgs.length}:${lastMsg?.role || ""}:${lastMsg?.streaming ? 1 : 0}:${(lastMsg?.text || "").length}`;

  useEffect(() => {
    // Cursor-like: always land on the latest message when opening/switching/updating chat
    scrollThreadToEnd(false);
  }, [activeTabId, lastMsgSig, scrollThreadToEnd]);

  function setTabBusy(id: string, on: boolean) {
    setBusyByTab((prev) => {
      if (!!prev[id] === on) return prev;
      const next = { ...prev };
      if (on) next[id] = true;
      else delete next[id];
      return next;
    });
  }

  function renameTab(id: string, title: string) {
    const clean = (title || "").trim();
    if (!clean || isPlaceholderTitle(clean)) return;
    setTabs((prev) => {
      const next = prev.map((t) => (t.id === id ? { ...t, title: clean } : t));
      persistTabs(next, activeTabId);
      return next;
    });
    setAllSessions((prev) =>
      prev.map((s) => (s.id === id ? { ...s, title: clean, updated_at: new Date().toISOString() } : s)),
    );
    updateLocalArchiveTitle(projectId, id, clean);
    // Persist AI/topic name on the server so archive keeps it
    void fetch(`${apiBaseForProject(projectId)}/api/projects/${projectId}/chat/sessions/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: clean }),
    }).catch(() => undefined);
  }

  function resolveTabTitle(id: string): string {
    const tab = tabs.find((t) => t.id === id);
    const fromTab = (tab?.title || "").trim();
    if (!isPlaceholderTitle(fromTab)) return fromTab;
    const firstUser = (msgsByTab[id] || []).find((m) => m.role === "user");
    if (firstUser?.text) {
      const topic = topicTitleFromMessage(firstUser.text);
      if (!isPlaceholderTitle(topic)) return topic;
    }
    const fromSessions = (allSessions.find((s) => s.id === id)?.title || "").trim();
    if (!isPlaceholderTitle(fromSessions)) return fromSessions;
    const fromLocal = (readLocalArchive(projectId).find((r) => r.id === id)?.title || "").trim();
    if (!isPlaceholderTitle(fromLocal)) return fromLocal;
    return fromTab || "أمر جديد";
  }

  const persistTabs = useCallback(
    (nextTabs: AgentTab[], nextActive: string | null) => {
      const payload = {
        openIds: nextTabs.map((t) => t.id),
        activeId: nextActive,
        pinnedIds: nextTabs.filter((t) => t.pinned).map((t) => t.id),
        updatedAt: new Date().toISOString(),
      };
      try {
        localStorage.setItem(tabsStorageKey(projectId), JSON.stringify(payload));
      } catch {
        /* ignore */
      }
      // Debounced cross-device sync
      if (syncTimerRef.current) clearTimeout(syncTimerRef.current);
      syncTimerRef.current = setTimeout(() => {
        void putTabsState(projectId, {
          open_ids: payload.openIds,
          active_id: payload.activeId,
          pinned_ids: payload.pinnedIds,
          updated_at: payload.updatedAt,
        });
      }, 450);
    },
    [projectId],
  );

  useEffect(() => {
    try {
      // One-shot migrate to Cursor-like Auto-write (old default was Review=on).
      const migrated = localStorage.getItem("spixa.ide.autoWriteMigrated");
      if (migrated !== "1") {
        localStorage.setItem("spixa.ide.reviewBeforeApply", "0");
        localStorage.setItem("spixa.ide.autoWriteMigrated", "1");
        setReviewBeforeApply(false);
      } else {
        const pref = localStorage.getItem("spixa.ide.reviewBeforeApply");
        setReviewBeforeApply(pref === "1");
      }
    } catch {
      /* ignore */
    }
    void ensureNotifyPermission();
    setResumeByTab(readCheckpoints(projectId));
    void resolveProjectApiBase(projectId).then(() => {
      void fetchTemplates(projectId).then(setTemplates);
    });
    initialSessionHandled.current = false;
  }, [projectId]);

  const refreshSessions = useCallback(async () => {
    const local = readLocalArchive(projectId);
    try {
      const base = await resolveProjectApiBase(projectId);
      const res = await fetch(`${base}/api/projects/${projectId}/chat/sessions?status=all`, {
        cache: "no-store",
      });
      if (!res.ok) {
        // Offline/API down — still show local archive memory
        const fallback = local.map((r) => ({
          id: r.id,
          title: r.title,
          status: "archived",
          updated_at: r.archived_at,
        }));
        setAllSessions(fallback);
        return fallback;
      }
      const data = await res.json();
      const openTitleById = new Map(tabs.map((t) => [t.id, t.title] as const));
      const rows: SessionRow[] = (Array.isArray(data) ? data : []).map((s: Record<string, unknown>) => {
        const id = String(s.id);
        let title = String(s.title || "أمر جديد");
        const openTitle = openTitleById.get(id);
        if (openTitle && !isPlaceholderTitle(openTitle) && isPlaceholderTitle(title)) {
          title = openTitle;
        }
        const mem = local.find((r) => r.id === id);
        if (mem && !isPlaceholderTitle(mem.title) && isPlaceholderTitle(title)) {
          title = mem.title;
        }
        return {
          id,
          title,
          status: String(s.status || "active"),
          created_at: s.created_at ? String(s.created_at) : undefined,
          updated_at: s.updated_at ? String(s.updated_at) : undefined,
        };
      });
      // Merge local archive entries missing from API (e.g. archive call failed earlier)
      const byId = new Set(rows.map((r) => r.id));
      for (const mem of local) {
        if (!byId.has(mem.id)) {
          rows.push({
            id: mem.id,
            title: mem.title,
            status: "archived",
            updated_at: mem.archived_at,
          });
        } else {
          const hit = rows.find((r) => r.id === mem.id);
          if (hit && hit.status === "active" && !tabs.some((t) => t.id === mem.id)) {
            // Closed locally but server still active — treat as archived in UI until synced
            hit.status = "archived";
          }
          if (hit && isPlaceholderTitle(hit.title) && !isPlaceholderTitle(mem.title)) {
            hit.title = mem.title;
          }
        }
      }
      setAllSessions(rows);
      return rows;
    } catch {
      const fallback = local.map((r) => ({
        id: r.id,
        title: r.title,
        status: "archived" as const,
        updated_at: r.archived_at,
      }));
      setAllSessions(fallback);
      return fallback;
    }
  }, [projectId, tabs]);

  async function patchSessionStatus(sessionId: string, status: "active" | "archived" | "deleted") {
    if (status === "archived") {
      const res = await fetch(`${apiBaseForProject(projectId)}/api/projects/${projectId}/chat/sessions/${sessionId}/archive`, {
        method: "POST",
      });
      if (!res.ok) {
        // Fallback PATCH if archive route missing (old API process)
        await fetch(`${apiBaseForProject(projectId)}/api/projects/${projectId}/chat/sessions/${sessionId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: "archived" }),
        });
      }
      return;
    }
    if (status === "active") {
      const res = await fetch(`${apiBaseForProject(projectId)}/api/projects/${projectId}/chat/sessions/${sessionId}/unarchive`, {
        method: "POST",
      });
      if (!res.ok) {
        await fetch(`${apiBaseForProject(projectId)}/api/projects/${projectId}/chat/sessions/${sessionId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: "active" }),
        });
      }
      return;
    }
    await fetch(`${apiBaseForProject(projectId)}/api/projects/${projectId}/chat/sessions/${sessionId}`, {
      method: "DELETE",
    });
  }

  async function sessionHasMessages(sessionId: string): Promise<boolean> {
    try {
      const res = await fetch(`${apiBaseForProject(projectId)}/api/projects/${projectId}/chat/sessions/${sessionId}/messages`, {
        cache: "no-store",
      });
      if (!res.ok) return true; // be safe: keep it
      const data = await res.json();
      return Array.isArray(data) && data.length > 0;
    } catch {
      return true;
    }
  }

  const loadMessages = useCallback(
    async (sessionId: string) => {
      try {
        const res = await fetch(`${apiBaseForProject(projectId)}/api/projects/${projectId}/chat/sessions/${sessionId}/messages`, {
          cache: "no-store",
        });
        if (!res.ok) return;
        const data = await res.json();
        let lastUserText = "";
        const rows: Msg[] = (Array.isArray(data) ? data : []).map((m: Record<string, unknown>) => {
          const role = m.role === "assistant" ? "assistant" : "user";
          const content = String(m.content || "");
          const payload = (m.tool_payload || {}) as Record<string, unknown>;
          if (role === "user") {
            const display =
              typeof payload.display_text === "string" && payload.display_text.trim()
                ? String(payload.display_text)
                : displayStoredUser(content);
            lastUserText = display;
            return { role, text: display };
          }
          const parsed = ensureBuildEdits(content, lastUserText, parseAgentEdits(content));
          const decision = (payload.decision_log || null) as DecisionLog | null;
          const internal = (payload.internal || {}) as Record<string, unknown>;
          const simulated = Boolean(
            payload.simulated ?? (decision as DecisionLog | null)?.simulated,
          );
          const specialistsRaw = Array.isArray(payload.specialists)
            ? payload.specialists
            : Array.isArray(internal.specialists)
              ? internal.specialists
              : Array.isArray(decision?.specialists)
                ? decision!.specialists
                : [];
          const buildPhase = String(payload.build_phase || "");
          const editsState = String(payload.edits_state || "");
          const treatPending =
            parsed.length > 0 &&
            (editsState === "proposed" ||
              editsState === "pending" ||
              (!editsState && (buildPhase === "plan" || buildPhase === "understand")));
          return {
            role,
            text: displayAgentReply(content, parsed, lastUserText),
            edits: treatPending ? undefined : parsed.length ? parsed : undefined,
            pendingEdits: treatPending ? parsed : undefined,
            agent: "Spixa",
            routeTier: payload.route_tier ? String(payload.route_tier) : null,
            model: payload.model ? String(payload.model) : null,
            simulated,
            specialists: specialistsRaw.map(String),
            buildPhase: buildPhase || null,
            decision,
          };
        });
        setMsgsByTab((prev) => ({ ...prev, [sessionId]: rows }));
        setLoadedTabs((prev) => ({ ...prev, [sessionId]: true }));
        // If tab still has a placeholder name, derive topic from first user message
        const firstUser = rows.find((r) => r.role === "user");
        if (firstUser?.text) {
          renameTab(sessionId, topicTitleFromMessage(firstUser.text));
        }
      } catch {
        setLoadedTabs((prev) => ({ ...prev, [sessionId]: true }));
      }
    },
    [projectId],
  );

  const openTab = useCallback(
    async (session: AgentTab, opts?: { load?: boolean }) => {
      // Restore from archive → active
      try {
        await patchSessionStatus(session.id, "active");
      } catch {
        /* ignore */
      }
      forgetLocalArchive(projectId, session.id);
      setTabs((prev) => {
        if (prev.some((t) => t.id === session.id)) {
          persistTabs(prev, session.id);
          return prev;
        }
        const next = [...prev, session];
        persistTabs(next, session.id);
        return next;
      });
      setActiveTabId(session.id);
      setError("");
      setAttachments([]);
      setHistoryOpen(false);
      void refreshSessions();
      if (opts?.load !== false) {
        setLoadedTabs((prev) => {
          if (prev[session.id]) return prev;
          void loadMessages(session.id);
          return prev;
        });
      }
    },
    [loadMessages, persistTabs, projectId, refreshSessions],
  );

  const createNewTab = useCallback(async () => {
    // Cursor-like: + opens a new page immediately — other tabs keep running in parallel
    if (creatingTabRef.current) return;
    creatingTabRef.current = true;
    setCreatingTab(true);
    setError("");
    setHistoryOpen(false);
    closeMenus();
    if (activeTabId) {
      setDraftsByTab((prev) => ({
        ...prev,
        [activeTabId]: { text: textRef.current, attachments, focusPath: tabFocusPath },
      }));
    }
    if (speechRef.current) {
      speechRef.current.stop();
      speechRef.current = null;
      setListening(false);
      setInterimSpeech("");
    }
    // Clear composer right away so the user can type while the session is created
    setAttachments([]);
    setText("");
    textRef.current = "";
    speechBaseRef.current = "";
    setInterimSpeech("");

    try {
      const base = await resolveProjectApiBase(projectId);
      const res = await fetch(`${base}/api/projects/${projectId}/chat/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        setError("تعذّر فتح محادثة جديدة.");
        return;
      }
      const data = await res.json();
      const tab: AgentTab = { id: String(data.id), title: String(data.title || "أمر جديد") };
      setMsgsByTab((prev) => ({ ...prev, [tab.id]: [] }));
      setLoadedTabs((prev) => ({ ...prev, [tab.id]: true }));
      setDraftsByTab((prev) => ({
        ...prev,
        [tab.id]: { text: "", attachments: [], focusPath: activePath },
      }));
      setTabs((prev) => {
        const next = [...prev, tab];
        persistTabs(next, tab.id);
        return next;
      });
      setActiveTabId(tab.id);
      setTabFocusPath(activePath);
      void refreshSessions();
      requestAnimationFrame(() => {
        tabsRef.current?.scrollTo({ left: tabsRef.current.scrollWidth, behavior: "smooth" });
        taRef.current?.focus();
      });
    } catch {
      setError("تعذّر فتح محادثة جديدة.");
    } finally {
      creatingTabRef.current = false;
      setCreatingTab(false);
    }
  }, [activePath, activeTabId, attachments, persistTabs, projectId, refreshSessions, tabFocusPath]);

  const closeTab = useCallback(
    (id: string, e?: MouseEvent) => {
      e?.preventDefault();
      e?.stopPropagation();
      const tabHit = tabs.find((t) => t.id === id);
      if (tabHit?.pinned) {
        setError("التبويب مثبت — أزل التثبيت أولاً.");
        return;
      }
      const title = resolveTabTitle(id);
      // Stop treating this tab as busy once archived away
      setTabBusy(id, false);

      setTabs((prev) => {
        const idx = prev.findIndex((t) => t.id === id);
        if (idx < 0) return prev;
        const next = prev.filter((t) => t.id !== id);
        let nextActive = activeTabId;
        if (activeTabId === id) {
          const neighbor = next[idx] || next[idx - 1] || next[0] || null;
          nextActive = neighbor?.id || null;
          setActiveTabId(nextActive);
          const draft = neighbor ? draftsByTab[neighbor.id] : undefined;
          setText(draft?.text || "");
          textRef.current = draft?.text || "";
          speechBaseRef.current = draft?.text || "";
          setAttachments(draft?.attachments || []);
          setTabFocusPath(draft?.focusPath ?? null);
        }
        persistTabs(next, nextActive);
        return next;
      });

      // Cursor-like: × always drops the conversation into Archive — with AI topic name
      void (async () => {
        try {
          rememberLocalArchive(projectId, id, title);
          if (!isPlaceholderTitle(title)) {
            await fetch(`${apiBaseForProject(projectId)}/api/projects/${projectId}/chat/sessions/${id}`, {
              method: "PATCH",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ title }),
            }).catch(() => undefined);
          }
          await patchSessionStatus(id, "archived");
          await refreshSessions();
          setTabs((prev) => {
            if (prev.length === 0) {
              queueMicrotask(() => {
                void createNewTab();
              });
            }
            return prev;
          });
        } catch {
          rememberLocalArchive(projectId, id, title);
          setError("تعذّر الأرشفة على الخادم — بقيت في الأرشيف المحلي.");
          setTabs((prev) => {
            if (prev.length === 0) {
              queueMicrotask(() => {
                void createNewTab();
              });
            }
            return prev;
          });
        }
      })();
    },
    [activeTabId, createNewTab, draftsByTab, persistTabs, projectId, refreshSessions, tabs, msgsByTab, allSessions],
  );

  const selectTab = useCallback(
    (id: string) => {
      if (id === activeTabId) return;
      // Save draft of current tab before switching
      if (activeTabId) {
        setDraftsByTab((prev) => ({
          ...prev,
          [activeTabId]: {
            text: textRef.current,
            attachments,
            focusPath: tabFocusPath,
          },
        }));
      }
      setActiveTabId(id);
      setError("");
      setHistoryOpen(false);
      const draft = draftsByTab[id];
      setText(draft?.text || "");
      textRef.current = draft?.text || "";
      speechBaseRef.current = draft?.text || "";
      setAttachments(draft?.attachments || []);
      setTabFocusPath(draft?.focusPath ?? null);
      setInterimSpeech("");
      persistTabs(tabs, id);
      if (!loadedTabs[id]) {
        void loadMessages(id);
      }
    },
    [activeTabId, attachments, draftsByTab, loadMessages, loadedTabs, persistTabs, tabFocusPath, tabs],
  );

  useEffect(() => {
    try {
      const saved = localStorage.getItem(CHIEF_STORAGE_KEY);
      if (saved) setPreferredProvider(saved);
    } catch {
      /* ignore */
    }
    setMicAvailable(speechSupported());
    if (typeof navigator !== "undefined") {
      setSpeechDir(dirForLanguage(navigator.language));
    }
    void fetchChiefModels().then(setChiefs);
    return () => {
      speechRef.current?.stop();
      speechRef.current = null;
    };
  }, []);

  function stopListening() {
    speechRef.current?.stop();
    speechRef.current = null;
    setListening(false);
    setInterimSpeech("");
    // Keep whatever is already in the textarea (committed + last interim)
    speechBaseRef.current = textRef.current;
  }

  function startListening() {
    if (!speechSupported()) {
      setError("الميكروفون غير مدعوم هنا — افتح Spixa في Chrome أو Edge.");
      return;
    }
    if (speechRef.current) stopListening();
    setError("");
    setDetectedLang("auto");
    speechBaseRef.current = textRef.current;
    const session = createLiveSpeechSession({
      onStart: () => {
        setListening(true);
      },
      onEnd: () => {
        setListening(false);
        setInterimSpeech("");
      },
      onInterim: (t) => {
        setInterimSpeech(t);
        // Cursor-like: live text stays inside the fixed-height field (scrolls)
        const live = joinSpeech(speechBaseRef.current, t);
        setText(live);
        textRef.current = live;
        requestAnimationFrame(() => {
          const el = taRef.current;
          if (!el) return;
          // Keep box size fixed — only scroll to the end
          el.style.height = "";
          el.selectionStart = el.selectionEnd = el.value.length;
          el.scrollTop = el.scrollHeight;
        });
      },
      onFinal: (payload) => {
        const next = joinSpeech(speechBaseRef.current, payload.text);
        speechBaseRef.current = next;
        setText(next);
        textRef.current = next;
        setInterimSpeech("");
        if (payload.language && payload.language !== "auto") setDetectedLang(payload.language);
        setSpeechDir(payload.dir);
      },
      onLanguage: (code, dir) => {
        if (code !== "auto") setDetectedLang(code);
        setSpeechDir(dir);
      },
      onError: (msg) => {
        setError(msg);
        setListening(false);
        setInterimSpeech("");
      },
    });
    if (!session) {
      setError("تعذّر تهيئة الميكروفون في هذا المتصفح.");
      return;
    }
    speechRef.current = session;
    session.start();
  }

  function toggleMic() {
    if (listening) stopListening();
    else startListening();
  }

  useEffect(() => {
    try {
      localStorage.setItem(CHIEF_STORAGE_KEY, preferredProvider);
    } catch {
      /* ignore */
    }
  }, [preferredProvider]);

  // Keep portal menus aligned + closable
  useEffect(() => {
    if (!modeMenu && !chiefMenu) return;
    const reposition = () => {
      placeMenuAbove(modeMenu ? modeBtnRef.current : chiefBtnRef.current);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeMenus();
    };
    reposition();
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("resize", reposition);
      window.removeEventListener("scroll", reposition, true);
      window.removeEventListener("keydown", onKey);
    };
  }, [modeMenu, chiefMenu]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const hit = await fetchProjectPreferences(projectId);
      if (!cancelled && hit.ok) {
        setPrefs(hit.preferences || {});
        if (hit.preferences?.always_preview) setFullBuild((v) => v);
      }
      const pulse = await fetchLearningPulse();
      if (!cancelled && pulse) setLearnPulse(pulse);
      if (!boostStarted.current) {
        boostStarted.current = true;
        void boostCoreSpecialties().then((ok) => {
          if (ok && !cancelled) {
            setLearnFlash("تعزيز التخصصات الداخلية…");
            window.setTimeout(() => setLearnFlash(""), 4000);
          }
        });
      }
    })();
    const timer = window.setInterval(() => {
      void fetchLearningPulse().then((p) => {
        if (!cancelled && p) setLearnPulse(p);
      });
    }, 45000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [projectId]);

  // Boot tabs for project
  useEffect(() => {
    bootRef.current = false;
    setTabs([]);
    setActiveTabId(null);
    setMsgsByTab({});
    setLoadedTabs({});
    setHistoryOpen(false);
    setText("");
    setError("");

    let cancelled = false;
    (async () => {
      const rows = await refreshSessions();
      if (cancelled) return;
      let saved: {
        openIds?: string[];
        activeId?: string | null;
        pinnedIds?: string[];
        updatedAt?: string;
      } = {};
      try {
        saved = JSON.parse(localStorage.getItem(tabsStorageKey(projectId)) || "{}");
      } catch {
        saved = {};
      }
      const remote = await fetchTabsState(projectId);
      if (remote?.updated_at && (!saved.updatedAt || remote.updated_at >= saved.updatedAt)) {
        saved = {
          openIds: remote.open_ids,
          activeId: remote.active_id,
          pinnedIds: remote.pinned_ids,
          updatedAt: remote.updated_at || undefined,
        };
      }
      const pinned = new Set(saved.pinnedIds || []);
      const activeRows = rows.filter((r) => r.status === "active");
      const allById = new Map(rows.map((r) => [r.id, r]));
      const byId = new Map(activeRows.map((r) => [r.id, r]));
      let openIds = (saved.openIds || []).filter((id) => byId.has(id) || allById.has(id));

      // Deep link / share: force include session
      if (initialSessionId && allById.has(initialSessionId)) {
        if (!openIds.includes(initialSessionId)) openIds = [...openIds, initialSessionId];
        saved.activeId = initialSessionId;
        try {
          await patchSessionStatus(initialSessionId, "active");
        } catch {
          /* ignore */
        }
      }

      if (openIds.length) {
        const restored = openIds
          .map((id) => {
            const row = byId.get(id) || allById.get(id)!;
            return {
              id,
              title: row.title,
              pinned: pinned.has(id),
            };
          })
          .sort((a, b) => Number(!!b.pinned) - Number(!!a.pinned));
        const active =
          saved.activeId && openIds.includes(saved.activeId) ? saved.activeId : openIds[openIds.length - 1];
        setTabs(restored);
        setActiveTabId(active);
        persistTabs(restored, active);
        void loadMessages(active);
      } else if (activeRows[0]) {
        const latest = activeRows[0];
        const restored = [{ id: latest.id, title: latest.title, pinned: pinned.has(latest.id) }];
        setTabs(restored);
        setActiveTabId(latest.id);
        persistTabs(restored, latest.id);
        void loadMessages(latest.id);
      } else {
        await createNewTab();
      }
      bootRef.current = true;
      initialSessionHandled.current = true;
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, initialSessionId]);

  // Keep send visible during mic; only block the active tab if THAT tab is busy
  const draftForSend = text.trim() || interimSpeech.trim() || speechBaseRef.current.trim();
  const canSend =
    Boolean(draftForSend) &&
    !activeBusy &&
    !creatingTab &&
    Boolean(projectId) &&
    Boolean(activeTabId);
  const fileLabel = activePath ? activePath.split(/[\\/]/).pop() : null;

  const allChiefModels = useMemo(() => {
    const rows = chiefs?.models?.length ? chiefs.models : FALLBACK_CHIEFS;
    return rows;
  }, [chiefs]);

  const selectedChief = useMemo(() => {
    return (
      allChiefModels.find((c) => c.id === preferredProvider) || {
        id: preferredProvider,
        label: preferredProvider === "auto" ? "Auto" : preferredProvider,
      }
    );
  }, [allChiefModels, preferredProvider]);

  const filteredChiefGroups = useMemo(() => {
    const q = chiefSearch.trim().toLowerCase();
    const groups =
      chiefs?.groups?.length
        ? chiefs.groups
        : [
            {
              id: "spixa",
              label: "Spixa Models",
              models: FALLBACK_CHIEFS.filter((m) => m.group === "spixa"),
            },
            {
              id: "other",
              label: "Other Models",
              models: FALLBACK_CHIEFS.filter((m) => m.group === "other"),
            },
          ];
    return groups
      .map((g) => ({
        ...g,
        models: g.models.filter(
          (m) =>
            !q ||
            m.label.toLowerCase().includes(q) ||
            m.id.toLowerCase().includes(q) ||
            (m.tier || "").toLowerCase().includes(q),
        ),
      }))
      .filter((g) => g.models.length > 0);
  }, [chiefSearch, chiefs]);

  const attachHits = useMemo(() => {
    const files = treePaths.filter((p) => !p.endsWith("/"));
    const q = attachQ.trim().toLowerCase();
    const base = q ? files.filter((p) => p.toLowerCase().includes(q)) : files;
    return base.slice(0, 80);
  }, [attachQ, treePaths]);

  function toggleAttach(path: string) {
    setAttachments((all) => (all.includes(path) ? all.filter((p) => p !== path) : [...all, path].slice(0, 12)));
  }

  function attachActive() {
    if (!activePath) return;
    setAttachments((all) => (all.includes(activePath) ? all : [...all, activePath].slice(0, 12)));
  }

  function appendTabMsg(sid: string, msg: Msg) {
    setMsgsByTab((all) => ({ ...all, [sid]: [...(all[sid] || []), msg] }));
  }

  function patchLastAssistant(sid: string, patch: Partial<Msg>) {
    setMsgsByTab((all) => {
      const rows = [...(all[sid] || [])];
      for (let i = rows.length - 1; i >= 0; i--) {
        if (rows[i].role === "assistant") {
          rows[i] = { ...rows[i], ...patch };
          break;
        }
      }
      return { ...all, [sid]: rows };
    });
  }

  function stopTab(sid: string) {
    const ac = abortByTabRef.current[sid];
    if (ac) {
      ac.abort();
      delete abortByTabRef.current[sid];
    }
    setTabBusy(sid, false);
    // Capture local resume checkpoint from last user + partial assistant
    const rows = msgsByTab[sid] || [];
    let userMessage = "";
    let partial = "";
    for (let i = rows.length - 1; i >= 0; i--) {
      if (!partial && rows[i].role === "assistant") partial = rows[i].text || "";
      if (!userMessage && rows[i].role === "user") {
        userMessage = rows[i].text || "";
        break;
      }
    }
    if (userMessage) {
      const cp: ResumeCheckpoint = {
        sessionId: sid,
        userMessage,
        partialReply: partial,
        attachments: draftsByTab[sid]?.attachments || attachments,
        focusPath: draftsByTab[sid]?.focusPath || tabFocusPath,
        mode,
        provider: preferredProvider,
        stoppedAt: new Date().toISOString(),
      };
      writeCheckpoint(projectId, cp);
      setResumeByTab((prev) => ({ ...prev, [sid]: cp }));
      void fetch(`${apiBaseForProject(projectId)}/api/projects/${projectId}/chat/sessions/${sid}/resume`, {
        method: "GET",
      })
        .then((r) => (r.ok ? r.json() : null))
        .then((server) => {
          if (!server) return;
          const merged: ResumeCheckpoint = {
            ...cp,
            partialReply: String(server.partial_reply || cp.partialReply || ""),
            userMessage: String(server.user_topic || cp.userMessage),
          };
          writeCheckpoint(projectId, merged);
          setResumeByTab((prev) => ({ ...prev, [sid]: merged }));
        })
        .catch(() => undefined);
    }
  }

  function togglePin(id: string, e?: MouseEvent) {
    e?.preventDefault();
    e?.stopPropagation();
    setTabs((prev) => {
      const next = prev.map((t) => (t.id === id ? { ...t, pinned: !t.pinned } : t));
      // Pinned first
      next.sort((a, b) => Number(!!b.pinned) - Number(!!a.pinned));
      persistTabs(next, activeTabId);
      return next;
    });
  }

  function exportActive(kind: "md" | "pdf") {
    if (!activeTabId) return;
    const title = tabs.find((t) => t.id === activeTabId)?.title || "chat";
    const md = buildChatMarkdown({
      title,
      projectId,
      sessionId: activeTabId,
      messages: (msgsByTab[activeTabId] || []).map((m) => ({
        role: m.role,
        text: m.text,
        agent: m.agent,
        model: m.model,
        edits: m.edits || m.pendingEdits,
      })),
    });
    if (kind === "md") {
      downloadText(`${title.replace(/[^\w\u0600-\u06FF-]+/g, "_").slice(0, 40) || "chat"}.md`, md);
    } else {
      openPrintableHtml({ title, markdownBody: md });
    }
  }

  function lastAssistantSnapshot(id: string): TabSnapshot {
    const tab = tabs.find((t) => t.id === id);
    const rows = msgsByTab[id] || [];
    let reply = "";
    let edits: FileEdit[] = [];
    for (let i = rows.length - 1; i >= 0; i--) {
      if (rows[i].role === "assistant") {
        reply = rows[i].text || "";
        edits = rows[i].edits || rows[i].pendingEdits || [];
        break;
      }
    }
    return { id, title: tab?.title || id.slice(0, 8), reply, edits };
  }

  async function snapshotEdits(edits: FileEdit[]): Promise<FileEdit[]> {
    const out: FileEdit[] = [];
    for (const edit of edits) {
      if (edit.kind === "dir" || typeof edit.previousContent === "string") {
        out.push(edit);
        continue;
      }
      const res = await fetchWorkspaceFile(projectId, edit.path);
      const previousContent =
        res.ok && typeof (res as { content?: string }).content === "string"
          ? String((res as { content?: string }).content)
          : "";
      out.push({ ...edit, previousContent });
    }
    return out;
  }

  async function applyPending(sid: string, msgIndex: number, paths?: string[] | "all") {
    const rows = msgsByTab[sid] || [];
    const msg = rows[msgIndex];
    if (!msg?.pendingEdits?.length) return;
    const take =
      paths === "all" || !paths
        ? msg.pendingEdits
        : msg.pendingEdits.filter((e) => paths.includes(e.path));
    const left =
      paths === "all" || !paths
        ? []
        : msg.pendingEdits.filter((e) => !paths.includes(e.path));
    if (!take.length) return;
    try {
      const snapped = await snapshotEdits(take);
      await onApplyEdits(snapped);
      setMsgsByTab((all) => {
        const cur = [...(all[sid] || [])];
        const row = cur[msgIndex];
        if (!row) return all;
        cur[msgIndex] = {
          ...row,
          edits: [...(row.edits || []), ...snapped],
          pendingEdits: left.length ? left : undefined,
          buildPhase: left.length ? row.buildPhase || "plan" : "implement",
        };
        return { ...all, [sid]: cur };
      });
      onLog?.(`applied ${take.length} edit(s)`);
      void recordCodingHumanAcceptance(true, `accepted ${take.length} file(s)`, "ide-review");
      const webPaths = take.map((e) => e.path).filter(isWebPreviewPath);
      if (webPaths.length || prefs.always_preview || fullBuild) onAfterWebEdits?.(webPaths);
      const priorUser =
        [...rows.slice(0, msgIndex)].reverse().find((m) => m.role === "user")?.text || "";
      void rapidLearnFromIdeApply({
        projectId,
        userText: priorUser || "IDE apply",
        assistantText: msg.text || "",
        files: take.map((e) => e.path),
        intent: "implement",
      }).then(() => {
        setLearnFlash("تعلّم من Accept");
        window.setTimeout(() => setLearnFlash(""), 2500);
        void fetchLearningPulse().then((p) => p && setLearnPulse(p));
      });
      if (prefs.always_preview || fullBuild || webPaths.length) {
        window.setTimeout(() => {
          void verifyWorkspacePreview(projectId).then((v) => {
            setLearnFlash(v.ok ? "تحقق البناء ✓" : "تحقق البناء يحتاج مراجعة");
            window.setTimeout(() => setLearnFlash(""), 3000);
          });
        }, 1200);
      }
    } catch {
      setError("فشل تطبيق التعديلات على الملفات.");
      void recordCodingHumanAcceptance(false, "apply failed", "ide-review");
      void learnFromOperation({
        kind: "edits_failed",
        title: "IDE apply failed",
        detail: "Failed to write pending edits to workspace",
        projectId,
        files: take.map((e) => e.path),
        intent: "implement",
      });
    }
  }

  function rejectPending(sid: string, msgIndex: number, paths?: string[] | "all") {
    const rows = msgsByTab[sid] || [];
    const msg = rows[msgIndex];
    const rejected =
      paths === "all" || !paths
        ? msg?.pendingEdits || []
        : (msg?.pendingEdits || []).filter((e) => paths.includes(e.path));
    setMsgsByTab((all) => {
      const next = [...(all[sid] || [])];
      const row = next[msgIndex];
      if (!row?.pendingEdits?.length) return all;
      const left =
        paths === "all" || !paths
          ? []
          : row.pendingEdits.filter((e) => !paths.includes(e.path));
      next[msgIndex] = { ...row, pendingEdits: left.length ? left : undefined };
      return { ...all, [sid]: next };
    });
    void recordCodingHumanAcceptance(false, "rejected pending edits", "ide-review");
    const priorUser =
      [...rows.slice(0, msgIndex)].reverse().find((m) => m.role === "user")?.text || "";
    void learnFromOperation({
      kind: "edits_rejected",
      title: "Human rejected agent edits",
      detail: `Rejected ${rejected.length} file(s)`,
      projectId,
      userText: priorUser,
      assistantText: msg?.text || "",
      files: rejected.map((e) => e.path),
      intent: "implement",
      humanVerified: true,
    });
  }

  function reorderTabs(fromId: string, toId: string) {
    if (fromId === toId) return;
    setTabs((prev) => {
      const from = prev.findIndex((t) => t.id === fromId);
      const to = prev.findIndex((t) => t.id === toId);
      if (from < 0 || to < 0) return prev;
      const next = [...prev];
      const [item] = next.splice(from, 1);
      next.splice(to, 0, item);
      persistTabs(next, activeTabId);
      return next;
    });
  }

  async function purgeArchived(id: string) {
    try {
      await fetch(`${apiBaseForProject(projectId)}/api/projects/${projectId}/chat/sessions/${id}?hard=true`, {
        method: "DELETE",
      });
      forgetLocalArchive(projectId, id);
      setAllSessions((prev) => prev.filter((s) => s.id !== id));
    } catch {
      setError("تعذّر الحذف النهائي.");
    }
  }

  // Keep per-tab focus file in sync with the editor
  useEffect(() => {
    if (!activeTabId || !activePath) return;
    setTabFocusPath(activePath);
    setDraftsByTab((prev) => ({
      ...prev,
      [activeTabId]: {
        text: prev[activeTabId]?.text ?? textRef.current,
        attachments: prev[activeTabId]?.attachments ?? attachments,
        focusPath: activePath,
      },
    }));
  }, [activePath, activeTabId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function send(opts?: { resume?: boolean; prompt?: string }) {
    if (listening) stopListening();
    const sid = activeTabId;
    if (!projectId || !sid) return;
    if (busyByTab[sid]) return;

    const isResume = Boolean(opts?.resume);
    const cp = isResume ? resumeByTab[sid] || getCheckpoint(projectId, sid) : null;
    const message = (
      opts?.prompt ||
      textRef.current ||
      text ||
      interimSpeech ||
      speechBaseRef.current ||
      (isResume ? "أكمل من حيث توقفت." : "")
    ).trim();
    if (!message && !isResume) return;

    const profile = loadUser();
    if (!hasFeature(profile, "chat")) {
      setError("المحادثة غير مفعّلة في خطتك.");
      return;
    }
    if (!hasTokens(profile, 1)) {
      setError("نفدت التوكنز — راجع الحساب.");
      return;
    }

    const sendMode = mode;
    const sendAttachments = [...attachments];
    const sendFocus = tabFocusPath || activePath;
    const sendProvider = preferredProvider;
    const chiefLabel = selectedChief.label;
    const topic = topicTitleFromMessage(isResume && cp ? cp.userMessage : message);
    const budget = budgetByTab[sid] || getBudget(projectId, sid);
    setBudgetByTab((prev) => ({ ...prev, [sid]: budget }));

    const ac = new AbortController();
    abortByTabRef.current[sid] = ac;
    setTabBusy(sid, true);
    setError("");
    closeMenus();
    setAttachOpen(false);
    setHistoryOpen(false);
    setBudgetOpen(false);

    const wantsProject =
      /(من الصفر|scaffold|create (a )?(new )?project|new (app|application)|greenfield|أنشئ مشروع|ابني مشروع|ابني لي|ابن لي|تبني لي|أريد منك أن تبني|اريد منك ان تبني|تطبيق يخص|بني لي تطبيق|build (me )?(a |an )?(app|application)|neues projekt|projekt (neu )?anlegen|app von null)/i.test(
        message,
      );
    const treeHint = treePaths.length
      ? `Project tree (short):\n${treePaths.slice(0, 60).join("\n")}${treePaths.length > 60 ? "\n…" : ""}`
      : "Workspace tree is nearly empty.";
    const chiefHint = `Selected brain: ${chiefLabel} (${sendProvider}).`;
    const resumeHint =
      isResume && cp
        ? [
            "Resume after stop.",
            `Original ask: ${cp.userMessage}`,
            `Partial before stop:\n${cp.partialReply || "(none)"}`,
          ].join("\n")
        : "";
    const prefsHint = [
      prefs.language ? `Preferred language: ${prefs.language}` : "",
      prefs.stack ? `Preferred stack: ${prefs.stack}` : "",
      prefs.no_scaffold ? "Never dump canned scaffolds." : "",
      prefs.always_preview ? "Always remind/start Live Preview after UI edits." : "",
      prefs.notes ? `User notes: ${prefs.notes}` : "",
    ]
      .filter(Boolean)
      .join("\n");
    const context = [
      SCAFFOLD_RULES,
      MODE_HINT[sendMode],
      chiefHint,
      resumeHint,
      prefsHint ? `PROJECT PREFERENCES:\n${prefsHint}` : "",
      fullBuild
        ? "FULL APP BUILD MODE: short understand+plan, then THIS TURN emit complete runnable ```path fences (entry+styles+logic). User authorized implement now."
        : "",
      sendMode === "ask" ? "Do not emit file blocks unless the user explicitly asks." : "",
      sendMode === "edit" && (sendAttachments[0] || sendFocus)
        ? `Focus edits on: ${(sendAttachments[0] || sendFocus)!}`
        : sendFocus
          ? `Linked file for this chat: ${sendFocus}`
          : "No file open — you may still edit/create files if the task requires it.",
      sendAttachments.length ? `Attachments: ${sendAttachments.join(", ")}` : "",
      treeHint,
      livePreviewUrl
        ? `Live Preview is running at ${livePreviewUrl} — after UI edits tell the user to refresh معاينة.`
        : "Live Preview: user can open معاينة in the IDE top bar to test the site while building.",
      wantsProject && sendMode === "agent" && !fullBuild
        ? "User wants a new project — first understand + short plan; emit file fences only if they asked to write/implement now (or said اكتب/schreib/build files)."
        : "Prefer improving the existing workspace; change only what is needed. No repeated templates.",
      "",
      "=== USER MESSAGE (reply in this language) ===",
      message || "Continue from where you stopped.",
    ]
      .filter(Boolean)
      .join("\n");

    appendTabMsg(sid, {
      role: "user",
      text: isResume ? `متابعة: ${message}` : message,
      agent: chiefLabel,
    });
    appendTabMsg(sid, {
      role: "assistant",
      text: "",
      agent: chiefLabel,
      streaming: true,
      status: {
        phase: "understand",
        label: STATUS_PHASE_LABEL.understand[detectUserLang(message)],
        step: 1,
        total: 4,
      },
    });
    if (!isResume) renameTab(sid, topic);

    setText("");
    textRef.current = "";
    speechBaseRef.current = "";
    setDraftsByTab((prev) => ({
      ...prev,
      [sid]: { text: "", attachments: sendAttachments, focusPath: sendFocus },
    }));

    let streamed = "";
    try {
      void fetch(`${API_URL}/system/admin/abuse/scan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: profile.email, text: message }),
      });
      const chatBase = await resolveProjectApiBase(projectId);
      const res = await fetch(
        `${chatBase}/api/projects/${projectId}/chat/sessions/${sid}/messages/stream`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
          signal: ac.signal,
          body: JSON.stringify({
            message: context,
            preferred_provider: sendProvider === "auto" ? null : sendProvider,
            preferred_agent: null,
            mode: sendMode,
            attachments: sendAttachments,
            resume: isResume,
            max_tokens_budget: budget.maxTokens,
            max_seconds: budget.maxSeconds,
            allow_teacher: budget.allowTeacher,
          }),
        },
      );
      if (!res.ok || !res.body) {
        const data = await res.json().catch(() => ({}));
        patchLastAssistant(sid, {
          text: `تعذّر الرد: ${String((data as { detail?: string }).detail || res.status)}`,
          streaming: false,
        });
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let donePayload: Record<string, unknown> | null = null;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const part of parts) {
          const line = part
            .split("\n")
            .map((l) => l.trim())
            .find((l) => l.startsWith("data:"));
          if (!line) continue;
          let evt: Record<string, unknown> = {};
          try {
            evt = JSON.parse(line.slice(5).trim());
          } catch {
            continue;
          }
          const type = String(evt.type || "");
          if (type === "status") {
            const phase = String(evt.phase || "thinking");
            const lang = detectUserLang(message);
            const label = statusLabelFor(
              phase,
              String(evt.text || UI_LANG[lang].thinking),
              lang,
            );
            const step = typeof evt.step === "number" ? evt.step : undefined;
            const total = typeof evt.total === "number" ? evt.total : undefined;
            patchLastAssistant(sid, {
              // Keep bubble empty until deltas — status lives in the think row
              text: streamed || "",
              streaming: true,
              status: { phase, label, step, total },
            });
          } else if (type === "delta") {
            streamed += String(evt.text || "");
            patchLastAssistant(sid, {
              text: streamed,
              streaming: true,
              status: null,
            });
          } else if (type === "done") {
            donePayload = evt;
            streamed = String(evt.reply || streamed);
          } else if (type === "aborted") {
            patchLastAssistant(sid, {
              text: streamed || "—",
              streaming: false,
              status: null,
            });
            void learnFromOperation({
              kind: "chat_abort",
              title: "Agent turn aborted",
              detail: streamed.slice(0, 1500) || "aborted",
              projectId,
              userText: message,
              assistantText: streamed,
            });
            return;
          } else if (type === "error") {
            const detail = String(evt.detail || "خطأ");
            patchLastAssistant(sid, {
              text: `تعذّر الرد: ${detail}`,
              streaming: false,
              status: null,
            });
            void learnFromOperation({
              kind: "chat_error",
              title: "Agent stream error",
              detail,
              projectId,
              userText: message,
            });
            return;
          }
        }
      }

      const reply = String(donePayload?.reply || streamed || "تم.");
      const specialists = Array.isArray(donePayload?.specialists)
        ? (donePayload!.specialists as unknown[]).map(String)
        : [];
      const teacherFailed =
        /\[provider-error:/i.test(reply) ||
        /cursor_key_missing|refused_simulate/i.test(reply);
      // Success learning already happens server-side (LTM + absorb + journal).
      // Client only reports failures the server may miss.
      if (teacherFailed) {
        void learnFromOperation({
          kind: "chat_error",
          title: "Teacher/provider failed",
          detail: reply.slice(0, 1500),
          projectId,
          userText: message,
          assistantText: reply,
        });
      } else {
        setLearnFlash("تعلّم من هذه الجولة");
        window.setTimeout(() => setLearnFlash(""), 2500);
        void fetchLearningPulse().then((p) => p && setLearnPulse(p));
      }
      const wantsWrites = userWantsFileWrites(message) || fullBuild;
      let edits = teacherFailed
        ? []
        : sendMode === "ask" && !wantsWrites
          ? []
          : ensureBuildEdits(reply, message, parseAgentEdits(reply));
      const routeTier = donePayload?.route_tier ? String(donePayload.route_tier) : null;
      const modelId = donePayload?.model ? String(donePayload.model) : null;
      const simulated = Boolean(donePayload?.simulated);
      setLastRoute({ tier: routeTier, model: modelId, simulated });
      const display = displayAgentReply(reply, edits, message);
      // Plan-first: auto-write only when user clearly asked to implement this turn.
      const useReview =
        edits.length > 0 &&
        (!wantsWrites || (reviewBeforeApply && sendMode === "edit") || sendMode === "ask");
      const buildPhase = String(
        edits.length && wantsWrites && !useReview
          ? "implement"
          : edits.length
            ? "plan"
            : donePayload?.build_phase || "understand",
      );
      const decision = (donePayload?.decision || null) as DecisionLog | null;
      patchLastAssistant(sid, {
        text: display,
        edits: useReview ? undefined : edits,
        pendingEdits: useReview ? edits : undefined,
        specialists,
        buildPhase,
        agent: chiefLabel,
        routeTier,
        model: modelId,
        simulated,
        streaming: false,
        status: null,
        decision: decision
          ? {
              ...decision,
              simulated: Boolean(decision.simulated ?? simulated),
              model: decision.model || modelId,
            }
          : { route_tier: routeTier, model: modelId, simulated },
      });

      const serverTitle = donePayload?.session_title ? String(donePayload.session_title) : "";
      if (serverTitle && !isPlaceholderTitle(serverTitle)) renameTab(sid, serverTitle);
      else if (!isResume) renameTab(sid, topic);
      void refreshSessions();

      clearCheckpoint(projectId, sid);
      setResumeByTab((prev) => {
        const next = { ...prev };
        delete next[sid];
        return next;
      });

      const used = estimateTokensFromText(message) + estimateTokensFromText(reply);
      const nextBudget = setBudget(projectId, sid, {
        tokensUsed: (budget.tokensUsed || 0) + used,
        turns: (budget.turns || 0) + 1,
      });
      setBudgetByTab((prev) => ({ ...prev, [sid]: nextBudget }));

      await spendTokens(1, "ide_chat");
      const route = routeLabel(routeTier, simulated, modelId);
      const tabTitle = shortTitle(serverTitle || topic);
      let finalDisplay = display;
      let appliedEdits = edits;
      if (edits.length && !useReview && !teacherFailed) {
        patchLastAssistant(sid, {
          text: display,
          streaming: true,
          status: {
            phase: "writing",
            label: UI_LANG[detectUserLang(message)].writing,
          },
        });
        const snapped = await snapshotEdits(edits);
        appliedEdits = filterNoopEdits(snapped);
        if (appliedEdits.length) {
          await onApplyEdits(appliedEdits);
          onLog?.(`${tabTitle} · ${route.text} · ${appliedEdits.length} file(s)`);
          // Cursor-like: keep the prose clean — no "✓ N Dateien geschrieben" chrome
          patchLastAssistant(sid, {
            text: finalDisplay,
            edits: appliedEdits,
            streaming: false,
            status: null,
          });
          const webPaths = appliedEdits.map((e) => e.path).filter(isWebPreviewPath);
          if (webPaths.length || prefs.always_preview || fullBuild) onAfterWebEdits?.(webPaths);
          void rapidLearnFromIdeApply({
            projectId,
            userText: message,
            assistantText: finalDisplay,
            files: appliedEdits.map((e) => e.path),
            intent: "implement",
          }).then(() => {
            setLearnFlash("تعلّم من Accept");
            window.setTimeout(() => setLearnFlash(""), 2500);
            void fetchLearningPulse().then((p) => p && setLearnPulse(p));
          });
          if (prefs.always_preview || fullBuild || webPaths.length) {
            window.setTimeout(() => {
              void verifyWorkspacePreview(projectId).then((v) => {
                setLearnFlash(v.ok ? "تحقق البناء ✓" : "تحقق البناء يحتاج مراجعة");
                window.setTimeout(() => setLearnFlash(""), 3000);
              });
            }, 1200);
          }
        } else {
          // All identical to disk — talk only, no fake "Wrote 5"
          onLog?.(`${tabTitle} · ${route.text} · no file changes`);
          patchLastAssistant(sid, {
            text: finalDisplay,
            edits: undefined,
            streaming: false,
            status: null,
          });
        }
      } else if (edits.length) {
        onLog?.(`${tabTitle} · ${route.text} · review ${edits.length}`);
      }

      const langNotify = detectUserLang(message);
      const wroteSomething = Boolean(appliedEdits.length && !useReview && !teacherFailed);
      notifyTabDone({
        title: tabTitle,
        body: useReview
          ? langNotify === "de"
            ? "Dateien warten auf Review"
            : langNotify === "ar"
              ? "بانتظار مراجعة الملفات"
              : "Files awaiting review"
          : wroteSomething
            ? langNotify === "de"
              ? "Fertig"
              : langNotify === "ar"
                ? "تم"
                : "Done"
            : langNotify === "de"
              ? "Fertig"
              : langNotify === "ar"
                ? "تم"
                : "Done",
        tag: sid,
        onClick: () => selectTab(sid),
      });
    } catch (err) {
      const aborted = err instanceof DOMException && err.name === "AbortError";
      if (aborted) {
        patchLastAssistant(sid, { text: streamed || "—", streaming: false });
        void learnFromOperation({
          kind: "chat_abort",
          title: "Client aborted agent",
          detail: streamed.slice(0, 1500) || "abort",
          projectId,
          userText: message,
          assistantText: streamed,
        });
      } else {
        if (activeTabId === sid) setError("تعذّر الاتصال بالوكيل.");
        patchLastAssistant(sid, {
          text: "تعذّر الاتصال بالخادم. حاول مجدداً.",
          streaming: false,
        });
        void learnFromOperation({
          kind: "chat_error",
          title: "Agent connection failed",
          detail: String(err).slice(0, 500),
          projectId,
          userText: message,
        });
      }
    } finally {
      delete abortByTabRef.current[sid];
      setTabBusy(sid, false);
    }
  }

  return (
    <aside className="ide-agent">
      <header className="ide-agent__head">
        <div className="ide-agent__brand">
          <strong>Agents</strong>
          <span>Spixa</span>
          {learnPulse?.learn_from_everything ? (
            <em className="ide-agent__learn-pulse" title={learnPulse.doctrine_ar || "يتعلّم من كل عملية"}>
              {learnFlash ||
                `تعلّم نشط · ${learnPulse.experience?.total ?? "—"}`}
            </em>
          ) : null}
        </div>
        <div className="ide-agent__head-actions" role="toolbar" aria-label="أدوات الوكيل">
          <button
            type="button"
            className={`ide-agent__tab-action ${fullBuild ? "is-on" : ""}`}
            title="بناء تطبيق كامل — خطة قصيرة ثم تنفيذ runnable"
            onClick={() => setFullBuild((v) => !v)}
          >
            بناء
          </button>
          <button
            type="button"
            className={`ide-agent__tab-action ${prefsOpen ? "is-on" : ""}`}
            title="تفضيلات المشروع"
            onClick={() => setPrefsOpen((v) => !v)}
          >
            تفضيل
          </button>
          <button
            type="button"
            className={`ide-agent__tab-action ${pickCompare ? "is-on" : ""}`}
            title="مقارنة تبويبين"
            onClick={() => {
              setPickCompare((v) => (v ? null : "pick"));
              setCompareIds(null);
            }}
          >
            ⇄
          </button>
          <button
            type="button"
            className={`ide-agent__tab-action ${templatesOpen ? "is-on" : ""}`}
            title="قوالب الأوامر"
            onClick={() => {
              setTemplatesOpen((v) => !v);
              void fetchTemplates(projectId).then(setTemplates);
            }}
          >
            ⌘
          </button>
          <button
            type="button"
            className="ide-agent__tab-action"
            title="مشاركة التبويب"
            onClick={() => {
              if (!activeTabId) return;
              void (async () => {
                const share = await createShareLink(projectId, activeTabId);
                if (!share) {
                  setError("تعذّر إنشاء رابط المشاركة.");
                  return;
                }
                const url = `${window.location.origin}${share.path}`;
                try {
                  await navigator.clipboard.writeText(url);
                  onLog?.(`share link copied`);
                } catch {
                  window.prompt("انسخ الرابط:", url);
                }
              })();
            }}
          >
            ↗
          </button>
          {onStartVenture ? (
            <button
              type="button"
              className="ide-agent__tab-action"
              title="Als Venture starten"
              onClick={() => {
                const draft = (textRef.current || text || "").trim();
                const lastUser = [...msgs].reverse().find((m) => m.role === "user")?.text || "";
                const brief = draft || lastUser;
                if (!brief.trim()) {
                  setError("Schreib zuerst ein Ziel / eine Nachricht.");
                  return;
                }
                onStartVenture(brief.trim());
                onLog?.("handed brief to Venture");
              }}
            >
              ◆
            </button>
          ) : null}
          <button
            type="button"
            className="ide-agent__tab-action"
            title="تصدير Markdown"
            onClick={() => exportActive("md")}
          >
            MD
          </button>
          <button
            type="button"
            className="ide-agent__tab-action"
            title="تصدير للطباعة/PDF"
            onClick={() => exportActive("pdf")}
          >
            PDF
          </button>
          <button
            type="button"
            className={`ide-agent__tab-action ${historyOpen ? "is-on" : ""}`}
            title="الأرشيف"
            onClick={() => {
              const next = !historyOpen;
              setHistoryOpen(next);
              if (next) void refreshSessions();
            }}
          >
            ⏱
          </button>
        </div>
        <div className="ide-agent__meta">
          {lastRoute.tier || lastRoute.simulated ? (
            <span
              className={`ide-agent__route is-${routeLabel(lastRoute.tier, lastRoute.simulated, lastRoute.model).kind}`}
              title={lastRoute.model || undefined}
            >
              {routeLabel(lastRoute.tier, lastRoute.simulated, lastRoute.model).text}
            </span>
          ) : null}
          <em className="ide-agent__focus" title={activePath || undefined}>
            {selectedChief.label}
          </em>
        </div>
      </header>

      <div className="ide-agent__tabs-bar">
        <div className="ide-agent__tabs" ref={tabsRef} role="tablist" aria-label="Agent pages">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              draggable
              aria-selected={t.id === activeTabId}
              className={`ide-agent__tab ${t.id === activeTabId ? "is-active" : ""} ${busyByTab[t.id] ? "is-running" : ""} ${dragTabId === t.id ? "is-dragging" : ""}`}
              onClick={() => {
                if (pickCompare) {
                  if (!pickCompare || pickCompare === "pick") {
                    setPickCompare(t.id);
                  } else if (pickCompare !== t.id) {
                    setCompareIds([pickCompare, t.id]);
                    setPickCompare(null);
                  }
                  return;
                }
                selectTab(t.id);
              }}
              onDragStart={(e) => {
                setDragTabId(t.id);
                e.dataTransfer.effectAllowed = "move";
                e.dataTransfer.setData("text/plain", t.id);
              }}
              onDragEnd={() => setDragTabId(null)}
              onDragOver={(e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = "move";
              }}
              onDrop={(e) => {
                e.preventDefault();
                const from = e.dataTransfer.getData("text/plain") || dragTabId;
                if (from) reorderTabs(from, t.id);
                setDragTabId(null);
              }}
              title={busyByTab[t.id] ? `يعمل الآن: ${t.title}` : t.title}
            >
              <span className="ide-agent__tab-icon" aria-hidden>
                {busyByTab[t.id] ? (
                  <i className="ide-composer__spin ide-agent__tab-spin" />
                ) : (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                    <path
                      d="M5 6.5A2.5 2.5 0 0 1 7.5 4h9A2.5 2.5 0 0 1 19 6.5v7A2.5 2.5 0 0 1 16.5 16H10l-4 3.2V6.5Z"
                      stroke="currentColor"
                      strokeWidth="1.7"
                      strokeLinejoin="round"
                    />
                  </svg>
                )}
              </span>
              <span
                className={`ide-agent__tab-pin ${t.pinned ? "is-on" : ""}`}
                role="button"
                tabIndex={0}
                title={t.pinned ? "إلغاء التثبيت" : "تثبيت"}
                onClick={(e) => togglePin(t.id, e)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    togglePin(t.id);
                  }
                }}
              >
                {t.pinned ? "📌" : "○"}
              </span>
              <span className="ide-agent__tab-title" dir="auto">
                {shortTitle(t.title)}
              </span>
              <span
                className="ide-agent__tab-close"
                role="button"
                tabIndex={0}
                title={t.pinned ? "مثبت" : "إغلاق وأرشفة"}
                onClick={(e) => closeTab(t.id, e)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    closeTab(t.id);
                  }
                }}
              >
                ×
              </span>
            </button>
          ))}
        </div>
        <div className="ide-agent__tabs-actions">
          <button
            type="button"
            className={`ide-agent__tab-action ide-agent__tab-action--new ${creatingTab ? "is-on" : ""}`}
            title="محادثة جديدة"
            aria-label="محادثة جديدة"
            disabled={creatingTab}
            onClick={() => void createNewTab()}
          >
            {creatingTab ? "…" : "+"}
          </button>
        </div>
      </div>
      {pickCompare ? (
        <div className="ide-agent__compare-hint">
          اختر تبويبين للمقارنة
          <button type="button" onClick={() => setPickCompare(null)}>
            إلغاء
          </button>
        </div>
      ) : null}

      {prefsOpen ? (
        <div className="ide-agent__prefs">
          <header>
            <strong>تفضيلات المشروع</strong>
            <button type="button" onClick={() => setPrefsOpen(false)}>
              إغلاق
            </button>
          </header>
          <label>
            اللغة
            <input
              value={prefs.language || ""}
              onChange={(e) => setPrefs((p) => ({ ...p, language: e.target.value }))}
              placeholder="ar / de / en"
            />
          </label>
          <label>
            Stack
            <input
              value={prefs.stack || ""}
              onChange={(e) => setPrefs((p) => ({ ...p, stack: e.target.value }))}
              placeholder="HTML / Vite / Next…"
              dir="ltr"
            />
          </label>
          <label className="ide-agent__prefs-check">
            <input
              type="checkbox"
              checked={Boolean(prefs.no_scaffold)}
              onChange={(e) => setPrefs((p) => ({ ...p, no_scaffold: e.target.checked }))}
            />
            بدون قوالب جاهزة مكررة
          </label>
          <label className="ide-agent__prefs-check">
            <input
              type="checkbox"
              checked={Boolean(prefs.always_preview)}
              onChange={(e) => setPrefs((p) => ({ ...p, always_preview: e.target.checked }))}
            />
            معاينة دائماً بعد التعديل
          </label>
          <label>
            ملاحظات
            <textarea
              value={prefs.notes || ""}
              onChange={(e) => setPrefs((p) => ({ ...p, notes: e.target.value }))}
              rows={2}
              placeholder="أسلوبك، ألوان، قواعد…"
            />
          </label>
          <button
            type="button"
            className="ide-agent__prefs-save"
            onClick={() => {
              void saveProjectPreferences(projectId, prefs).then((r) => {
                if (!r.ok) setError(r.error || "تعذّر حفظ التفضيلات");
                else {
                  setLearnFlash("حُفظت التفضيلات");
                  window.setTimeout(() => setLearnFlash(""), 2000);
                  setPrefsOpen(false);
                }
              });
            }}
          >
            حفظ التفضيلات
          </button>
        </div>
      ) : null}

      {templatesOpen ? (
        <div className="ide-agent__templates">
          <header>
            <strong>قوالب</strong>
            <button
              type="button"
              onClick={() => {
                const prompt = (textRef.current || text || "").trim();
                if (!prompt) {
                  setError("اكتب أمراً أولاً لحفظه كقالب.");
                  return;
                }
                const title = topicTitleFromMessage(prompt).slice(0, 40) || "قالب";
                void createTemplate(projectId, title, prompt).then((row) => {
                  if (row) setTemplates((prev) => [row, ...prev]);
                });
              }}
            >
              حفظ الحالي
            </button>
            <button type="button" onClick={() => setTemplatesOpen(false)}>
              إغلاق
            </button>
          </header>
          <ul>
            {templates.map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  className="ide-agent__templates-use"
                  onClick={() => {
                    setText(t.prompt);
                    textRef.current = t.prompt;
                    setTemplatesOpen(false);
                    taRef.current?.focus();
                  }}
                >
                  <strong dir="auto">{t.title}</strong>
                </button>
                <button
                  type="button"
                  className="ide-agent__templates-del"
                  title="حذف"
                  onClick={() => {
                    void deleteTemplate(projectId, t.id).then((ok) => {
                      if (ok) setTemplates((prev) => prev.filter((x) => x.id !== t.id));
                    });
                  }}
                >
                  ⌫
                </button>
              </li>
            ))}
            {!templates.length ? <li className="ide-agent__history-empty">—</li> : null}
          </ul>
        </div>
      ) : null}

      {historyOpen ? (
        <div className="ide-agent__history">
          <header>
            <strong>الأرشيف</strong>
            <button
              type="button"
              onClick={() => {
                void refreshSessions();
              }}
              title="تحديث"
            >
              ↻
            </button>
            <button type="button" onClick={() => setHistoryOpen(false)}>
              Done
            </button>
          </header>
          <input
            className="ide-agent__history-search"
            value={archiveQuery}
            onChange={(e) => setArchiveQuery(e.target.value)}
            placeholder="بحث…"
            dir="auto"
          />
          {(() => {
            const openIds = new Set(tabs.map((t) => t.id));
            const q = archiveQuery.trim().toLowerCase();
            const openOnes = allSessions.filter((s) => openIds.has(s.id));
            const archived = allSessions
              .filter((s) => !openIds.has(s.id) && s.status !== "deleted")
              .filter((s) => {
                if (!q) return true;
                const title = resolveTabTitle(s.id) || s.title || "";
                return title.toLowerCase().includes(q);
              })
              .sort((a, b) => String(b.updated_at || "").localeCompare(String(a.updated_at || "")));
            return (
              <>
                {openOnes.length ? (
                  <section className="ide-agent__history-section">
                    <h4>مفتوحة</h4>
                    <ul>
                      {openOnes.map((s) => (
                        <li key={s.id}>
                          <button
                            type="button"
                            className={s.id === activeTabId ? "is-active" : ""}
                            onClick={() => {
                              selectTab(s.id);
                              setHistoryOpen(false);
                            }}
                          >
                            <strong dir="auto">{shortTitle(resolveTabTitle(s.id) || s.title)}</strong>
                            <span>Open</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </section>
                ) : null}
                <section className="ide-agent__history-section">
                  <h4>مؤرشفة ({archived.length})</h4>
                  <ul>
                    {archived.map((s) => {
                      const named = shortTitle(resolveTabTitle(s.id) || s.title);
                      return (
                        <li key={s.id} className="ide-agent__history-row">
                          <button
                            type="button"
                            className="ide-agent__history-open"
                            onClick={() => void openTab({ id: s.id, title: named })}
                          >
                            <strong dir="auto">{named}</strong>
                            <span>Reopen</span>
                          </button>
                          <button
                            type="button"
                            className="ide-agent__history-purge"
                            title="حذف نهائي"
                            onClick={(e) => {
                              e.stopPropagation();
                              if (window.confirm(`حذف نهائي: ${named}؟`)) {
                                void purgeArchived(s.id);
                              }
                            }}
                          >
                            ⌫
                          </button>
                        </li>
                      );
                    })}
                    {!archived.length ? <li className="ide-agent__history-empty">—</li> : null}
                  </ul>
                </section>
              </>
            );
          })()}
        </div>
      ) : null}

      {(tabFocusPath || attachments.length > 0) && activeTabId ? (
        <div className="ide-agent__ctx" dir="ltr">
          {tabFocusPath ? (
            <span className="ide-agent__ctx-file" title={tabFocusPath}>
              ⌕ {tabFocusPath.split(/[\\/]/).pop()}
            </span>
          ) : null}
          {attachments.map((p) => (
            <button
              key={p}
              type="button"
              className="ide-agent__ctx-chip"
              title={p}
              onClick={() => toggleAttach(p)}
            >
              @{p.split(/[\\/]/).pop()}
              <span aria-hidden>×</span>
            </button>
          ))}
        </div>
      ) : null}

      <div className="ide-agent__thread" ref={threadRef}>
        {msgs.map((m, i) => {
          const priorUser =
            m.role === "assistant"
              ? [...msgs.slice(0, i)].reverse().find((x) => x.role === "user")?.text || ""
              : m.text || "";
          const uiLang = detectUserLang(priorUser);
          const ui = UI_LANG[uiLang];
          const hasBody = !!(m.text || m.streaming || m.pendingEdits?.length || m.edits?.length);
          return (
          <div
            key={`${m.role}-${i}`}
            className={`ide-agent__msg is-${m.role}${m.streaming ? " is-streaming" : ""}`}
          >
            <span className="ide-agent__role">{m.role === "user" ? "You" : m.agent || "Spixa"}</span>
            {m.streaming && (m.status || !m.text) ? (
              <div className="ide-agent__think" aria-live="polite">
                <span className="ide-agent__think-pulse" aria-hidden />
                <span className="ide-agent__think-label">
                  {m.status?.label || ui.thinking}
                </span>
                {m.status?.step && m.status?.total ? (
                  <span className="ide-agent__think-step" dir="ltr">
                    {m.status.step}/{m.status.total}
                  </span>
                ) : null}
              </div>
            ) : null}
            {hasBody || m.role === "user" ? (
              <div className="ide-agent__bubble">
                {m.text || ""}
              </div>
            ) : null}
            {m.role === "assistant" && (m.buildPhase || m.specialists?.length) ? (
              <div className="ide-agent__team" dir="ltr">
                {m.buildPhase ? (
                  <span className={`ide-agent__phase is-${m.buildPhase}`}>
                    {(BUILD_PHASE_LABEL[m.buildPhase] || BUILD_PHASE_LABEL.idle)[uiLang]}
                  </span>
                ) : null}
                {(m.specialists || []).slice(0, 6).map((name) => (
                  <span key={name} className="ide-agent__chip">
                    {name}
                  </span>
                ))}
              </div>
            ) : null}
            {m.pendingEdits?.length && activeTabId ? (
              <AgentEditReview
                projectId={projectId}
                mode="review"
                edits={m.pendingEdits}
                onAcceptAll={() => void applyPending(activeTabId, i, "all")}
                onRejectAll={() => rejectPending(activeTabId, i, "all")}
                onAcceptOne={(path) => void applyPending(activeTabId, i, [path])}
                onSkipOne={(path) => rejectPending(activeTabId, i, [path])}
                onOpenPath={onOpenPath}
              />
            ) : null}
            {m.edits?.length && !m.pendingEdits?.length ? (
              <AgentEditReview
                projectId={projectId}
                mode="applied"
                edits={m.edits}
                onOpenPath={onOpenPath}
              />
            ) : null}
            {m.role === "assistant" && (m.routeTier || m.decision || m.simulated) ? (
              <div className="ide-agent__decide">
                <button
                  type="button"
                  className={`ide-agent__route-foot is-${routeLabel(m.routeTier || m.decision?.route_tier, m.simulated || m.decision?.simulated, m.model || m.decision?.model).kind}`}
                  onClick={() =>
                    setDecisionOpen((prev) => ({ ...prev, [`${i}`]: !prev[`${i}`] }))
                  }
                >
                  {routeLabel(m.routeTier || m.decision?.route_tier, m.simulated || m.decision?.simulated, m.model || m.decision?.model).text}
                  {m.simulated || m.decision?.simulated
                    ? ` · ${formatRouteModel(m.model || m.decision?.model, true)}`
                    : m.model || m.decision?.model
                      ? ` · ${formatRouteModel(m.model || m.decision?.model)}`
                      : ""}
                  {` · ${ui.why}`}
                </button>
                {decisionOpen[`${i}`] && m.decision ? (
                  <div className="ide-agent__decide-body">
                    <p>
                      {m.decision.intent || m.decision.intent_label
                        ? `${ui.understood}: ${intentLabelFor(m.decision.intent || m.decision.intent_label, uiLang)}`
                        : ui.executing}
                    </p>
                    {m.decision.files_hint?.length ? (
                      <p dir="ltr">files: {m.decision.files_hint.slice(0, 8).join(", ")}</p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
          );
        })}
        <div ref={threadEndRef} className="ide-agent__thread-end" aria-hidden />
      </div>

      {error ? <p className="ide-banner">{error}</p> : null}

      {activeTabId && (resumeByTab[activeTabId] || getCheckpoint(projectId, activeTabId)) ? (
        <div className="ide-agent__resume">
          <span>نقطة إيقاف محفوظة</span>
          <button type="button" onClick={() => void send({ resume: true })} disabled={activeBusy}>
            متابعة
          </button>
          <button
            type="button"
            className="is-muted"
            onClick={() => {
              clearCheckpoint(projectId, activeTabId);
              setResumeByTab((prev) => {
                const n = { ...prev };
                delete n[activeTabId];
                return n;
              });
            }}
          >
            تجاهل
          </button>
        </div>
      ) : null}

      {(() => {
        const lastUser =
          text.trim() ||
          [...msgs].reverse().find((m) => m.role === "user")?.text ||
          "";
        const chips = buildSuggestions({
          activePath: tabFocusPath || activePath,
          attachments,
          hasMessages: msgs.length > 0,
          lastAssistant: [...msgs].reverse().find((m) => m.role === "assistant")?.text,
          mode,
          lang: detectUserLang(lastUser),
        });
        if (!chips.length || activeBusy) return null;
        return (
          <div className="ide-agent__suggest">
            {chips.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => {
                  setText(s.prompt);
                  textRef.current = s.prompt;
                  void send({ prompt: s.prompt });
                }}
              >
                {s.label}
              </button>
            ))}
          </div>
        );
      })()}

      <div className={`ide-composer ${listening ? "is-listening" : ""}`}>
        {attachments.length > 0 && (
          <div className="ide-composer__chips">
            {attachments.map((p) => (
              <button
                key={p}
                type="button"
                className="ide-composer__chip"
                onClick={() => toggleAttach(p)}
                title={p}
              >
                @{p.split("/").pop()}
                <span aria-hidden>×</span>
              </button>
            ))}
          </div>
        )}

        {listening ? (
          <div className="ide-composer__hearing is-live" dir={speechDir}>
            <span className="ide-composer__hearing-dot" aria-hidden />
            <em>{speechDir === "rtl" ? "جارٍ الاستماع…" : "Listening…"}</em>
            <span className="ide-composer__hearing-lang">
              {detectedLang === "auto" ? "Auto" : detectedLang}
            </span>
          </div>
        ) : null}

        <textarea
          ref={taRef}
          rows={3}
          value={text}
          dir={speechDir}
          onChange={(e) => {
            setText(e.target.value);
            textRef.current = e.target.value;
            if (!listening) speechBaseRef.current = e.target.value;
          }}
          placeholder={
            listening
              ? speechDir === "rtl"
                ? "تحدث… اللغة تُكتشف تلقائياً"
                : "Speak… language detected automatically"
              : activeTab
                ? `Continue in “${shortTitle(activeTab.title)}”…`
                : "Plan, Build, / للأوامر، @ للملفات…"
          }
          onKeyDown={(e) => {
            // Plain Enter sends; Ctrl/Cmd+Enter is reserved for IDE “Run”.
            if (e.key === "Enter" && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
              e.preventDefault();
              void send();
            }
          }}
        />

        <div className="ide-composer__bar">
          <div className="ide-composer__left">
            <div className="ide-composer__mode-wrap">
              <button
                type="button"
                className={`ide-composer__mode ${reviewBeforeApply ? "is-open" : ""}`}
                title={
                  mode === "agent"
                    ? "وضع Agent يكتب الملفات دائماً فوراً (مثل Cursor)"
                    : reviewBeforeApply
                      ? "مراجعة قبل الكتابة (يعمل في وضع Edit فقط)"
                      : "كتابة تلقائية — يطبّق الملفات فوراً بلا قبول"
                }
                disabled={mode === "agent"}
                onClick={() => {
                  setReviewBeforeApply((v) => {
                    const next = !v;
                    try {
                      localStorage.setItem("spixa.ide.reviewBeforeApply", next ? "1" : "0");
                    } catch {
                      /* ignore */
                    }
                    return next;
                  });
                }}
              >
                {reviewBeforeApply ? "Review" : "Auto-write"}
              </button>
            </div>
            <div className="ide-composer__mode-wrap">
              <button
                type="button"
                className={`ide-composer__mode ${budgetOpen ? "is-open" : ""}`}
                title="سقف التكلفة لهذا التبويب"
                onClick={() => {
                  if (activeTabId) {
                    setBudgetByTab((prev) => ({
                      ...prev,
                      [activeTabId]: prev[activeTabId] || getBudget(projectId, activeTabId),
                    }));
                  }
                  setBudgetOpen((v) => !v);
                }}
              >
                Cap
              </button>
              {budgetOpen && activeTabId ? (
                <div className="ide-composer__budget" role="dialog">
                  {(() => {
                    const b = budgetByTab[activeTabId] || getBudget(projectId, activeTabId) || DEFAULT_BUDGET;
                    return (
                      <>
                        <label>
                          توكنز
                          <select
                            value={b.maxTokens}
                            onChange={(e) => {
                              const next = setBudget(projectId, activeTabId, {
                                maxTokens: Number(e.target.value),
                              });
                              setBudgetByTab((prev) => ({ ...prev, [activeTabId]: next }));
                            }}
                          >
                            {TOKEN_PRESETS.map((n) => (
                              <option key={n} value={n}>
                                {n}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          ثوانٍ
                          <select
                            value={b.maxSeconds}
                            onChange={(e) => {
                              const next = setBudget(projectId, activeTabId, {
                                maxSeconds: Number(e.target.value),
                              });
                              setBudgetByTab((prev) => ({ ...prev, [activeTabId]: next }));
                            }}
                          >
                            {TIME_PRESETS.map((n) => (
                              <option key={n} value={n}>
                                {n}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="ide-composer__budget-check">
                          <input
                            type="checkbox"
                            checked={b.allowTeacher}
                            onChange={(e) => {
                              const next = setBudget(projectId, activeTabId, {
                                allowTeacher: e.target.checked,
                              });
                              setBudgetByTab((prev) => ({ ...prev, [activeTabId]: next }));
                            }}
                          />
                          Teacher
                        </label>
                        <em>
                          {b.turns || 0}t · ~{b.tokensUsed || 0}/{b.maxTokens}
                        </em>
                      </>
                    );
                  })()}
                </div>
              ) : null}
            </div>
            <div className="ide-composer__mode-wrap">
              <button
                ref={modeBtnRef}
                type="button"
                className={`ide-composer__mode ${modeMenu ? "is-open" : ""}`}
                aria-haspopup="menu"
                aria-expanded={modeMenu}
                onClick={(e) => {
                  e.stopPropagation();
                  const next = !modeMenu;
                  setChiefMenu(false);
                  if (next) {
                    placeMenuAbove(modeBtnRef.current);
                    setModeMenu(true);
                  } else {
                    setModeMenu(false);
                  }
                }}
              >
                <span className="ide-composer__infty" aria-hidden>
                  ∞
                </span>
                {mode === "agent" ? "Agent" : mode === "ask" ? "Ask" : "Edit"}
                <span className="ide-composer__chev">▾</span>
              </button>
            </div>

            <div className="ide-composer__mode-wrap">
              <button
                ref={chiefBtnRef}
                type="button"
                className={`ide-composer__mode is-agent-pick ${chiefMenu ? "is-open" : ""}`}
                aria-haspopup="menu"
                aria-expanded={chiefMenu}
                title="النموذج الرئيس — Auto / Spixa / OpenRouter"
                onClick={(e) => {
                  e.stopPropagation();
                  const next = !chiefMenu;
                  setModeMenu(false);
                  setChiefSearch("");
                  if (next) {
                    placeMenuAbove(chiefBtnRef.current);
                    setChiefMenu(true);
                  } else {
                    setChiefMenu(false);
                  }
                }}
              >
                {selectedChief.label}
                <span className="ide-composer__chev">▾</span>
              </button>
            </div>
          </div>

          <div className="ide-composer__right">
            {micAvailable ? (
              <button
                type="button"
                className={`ide-composer__icon ide-composer__mic ${listening ? "is-listening" : ""}`}
                title={listening ? "إيقاف الميكروفون" : "تحدث — التعرف على اللغة تلقائياً"}
                aria-pressed={listening}
                onClick={toggleMic}
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden>
                  <path
                    d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3Z"
                    stroke="currentColor"
                    strokeWidth="1.8"
                  />
                  <path
                    d="M5 11a7 7 0 0 0 14 0M12 18v3"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
            ) : null}
            <button
              type="button"
              className={`ide-composer__icon ide-composer__icon--new ${creatingTab ? "is-on" : ""}`}
              title="محادثة جديدة"
              aria-label="محادثة جديدة"
              disabled={creatingTab}
              onClick={() => void createNewTab()}
            >
              {creatingTab ? <i className="ide-composer__spin" /> : "+"}
            </button>
            <button
              type="button"
              className={`ide-composer__icon ${attachOpen || attachments.length ? "is-on" : ""}`}
              title="إرفاق ملفات من المشروع"
              onClick={() => {
                setAttachOpen((v) => !v);
                if (!attachments.length && activePath) attachActive();
              }}
            >
              📎
            </button>
            {activeBusy && activeTabId ? (
              <button
                type="button"
                className="ide-composer__send is-stop"
                onClick={() => stopTab(activeTabId)}
                aria-label="إيقاف"
                title="إيقاف"
              >
                <span className="ide-composer__stop" aria-hidden />
              </button>
            ) : (
              <button
                type="button"
                className={`ide-composer__send ${canSend ? "is-ready" : "is-muted"}`}
                onClick={() => void send()}
                disabled={!canSend}
                aria-label="إرسال"
                title={listening ? "إيقاف الميكروفون والإرسال" : "إرسال (Enter)"}
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
                  <path
                    d="M3 8h10M9 4l4 4-4 4"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
            )}
          </div>
        </div>

        {attachOpen ? (
          <div className="ide-attach" dir="ltr">
            <header className="ide-attach__head">
              <strong>Attach files</strong>
              <button type="button" className="ide-term__btn" onClick={() => setAttachOpen(false)}>
                Done
              </button>
            </header>
            <input
              value={attachQ}
              onChange={(e) => setAttachQ(e.target.value)}
              placeholder="Filter paths…"
              className="ide-attach__search"
            />
            {activePath ? (
              <button type="button" className="ide-attach__active" onClick={attachActive}>
                + current file · {fileLabel}
              </button>
            ) : null}
            <ul className="ide-attach__list">
              {attachHits.map((p) => {
                const on = attachments.includes(p);
                return (
                  <li key={p}>
                    <button type="button" className={on ? "is-on" : ""} onClick={() => toggleAttach(p)}>
                      <span className="ide-attach__check">{on ? "✓" : ""}</span>
                      <span className="ide-attach__path">{p}</span>
                    </button>
                  </li>
                );
              })}
              {!attachHits.length ? <li className="ide-attach__empty">No files</li> : null}
            </ul>
            <footer className="ide-attach__foot">{attachments.length}/12 selected · contents sent to agent</footer>
          </div>
        ) : null}
      </div>

      {typeof document !== "undefined" && (modeMenu || chiefMenu)
        ? createPortal(
            <>
              <button
                type="button"
                className="ide-composer__menu-backdrop"
                aria-label="إغلاق القائمة"
                onClick={closeMenus}
              />
              {modeMenu ? (
                <div className="ide-composer__menu ide-composer__menu--portal" style={menuStyle} role="menu">
                  {(
                    [
                      ["agent", "Agent — بناء وتطبيق"],
                      ["ask", "Ask — شرح فقط"],
                      ["edit", "Edit — تعديل الملفات"],
                    ] as const
                  ).map(([id, label]) => (
                    <button
                      key={id}
                      type="button"
                      className={mode === id ? "is-active" : ""}
                      onClick={() => {
                        setMode(id);
                        closeMenus();
                      }}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              ) : null}
              {chiefMenu ? (
                <div
                  className="ide-composer__menu ide-composer__menu--models ide-composer__menu--portal"
                  style={menuStyle}
                  role="menu"
                >
                  <div className="ide-composer__model-search">
                    <input
                      type="search"
                      value={chiefSearch}
                      onChange={(e) => setChiefSearch(e.target.value)}
                      placeholder="Search models"
                      autoFocus
                    />
                  </div>
                  <button
                    type="button"
                    className={preferredProvider === "auto" ? "is-active" : ""}
                    onClick={() => {
                      setPreferredProvider("auto");
                      closeMenus();
                    }}
                  >
                    <strong>Auto</strong>
                    <span className="ide-composer__menu-sub">
                      {chiefs?.auto?.detail || "داخلي أولاً → تصعيد للمعلّم"}
                    </span>
                    {preferredProvider === "auto" ? <em className="ide-composer__check">✓</em> : null}
                  </button>
                  {filteredChiefGroups.map((g) => (
                    <div key={g.id} className="ide-composer__dept">
                      <header className="ide-composer__menu-label">{g.label}</header>
                      {g.models.map((m) => (
                        <button
                          key={m.id}
                          type="button"
                          className={preferredProvider === m.id ? "is-active" : ""}
                          onClick={() => {
                            setPreferredProvider(m.id);
                            closeMenus();
                          }}
                        >
                          <strong>{m.label}</strong>
                          {m.tier ? <span className="ide-composer__tier">{m.tier}</span> : null}
                          {preferredProvider === m.id ? <em className="ide-composer__check">✓</em> : null}
                        </button>
                      ))}
                    </div>
                  ))}
                  {!chiefs?.openrouter_configured ? (
                    <p className="ide-composer__menu-hint">
                      اربط OPENROUTER_API_KEY للمنبع الموحّد (معلّمون بدون مفاتيح لكل مزوّد).
                    </p>
                  ) : null}
                </div>
              ) : null}
            </>,
            document.body,
          )
        : null}

      {compareIds ? (
        <AgentCompareModal
          left={lastAssistantSnapshot(compareIds[0])}
          right={lastAssistantSnapshot(compareIds[1])}
          onClose={() => setCompareIds(null)}
        />
      ) : null}
    </aside>
  );
}
