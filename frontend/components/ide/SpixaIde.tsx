"use client";

import Link from "next/link";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { createPortal } from "react-dom";
import { fetchProjects } from "@/lib/api";
import { PRODUCT } from "@/lib/brand";
import type { Project } from "@/lib/types";
import type { FileEdit } from "@/lib/agentEdits";
import {
  createWorkspaceEntry,
  fetchPreviewStatus,
  fetchWorkspaceFile,
  fetchWorkspaceTree,
  saveWorkspaceFile,
  startWorkspacePreview,
  stopWorkspacePreview,
  type TreeEntry,
} from "@/lib/workspace";
import {
  isSpixaDesktop,
  openFolderErrorMessage,
  openLocalProjectFolder,
  pickLocalFolder,
} from "@/lib/openLocalProject";
import { LocalFolderBrowser } from "@/components/projects/LocalFolderBrowser";
import { useIdeTopbarActive, useIdeTopbarHost } from "@/components/shell/IdeTopbarSlot";
import { loadIdeLayout, saveIdeLayout, type IdeRightPanel } from "@/lib/ideLayout";
import { learnFromOperation, recordCodingTaskOutcome } from "@/lib/maturity";
import { CodeEditor, type EditorCursorState } from "./CodeEditor";
import { resolveShare } from "@/lib/agentPanel/agentUiApi";
import { IdeAgentPanel } from "./IdeAgentPanel";
import { IdeVenturePanel } from "./IdeVenturePanel";
import { IdeFileTree, type TreeNodeData } from "./IdeFileTree";
import {
  IdeBottomPanel,
  type IdeBottomPanelHandle,
  type IdeProblem,
} from "./IdeBottomPanel";
import { IdeStatusBar } from "./IdeStatusBar";
import { MediaPreview } from "./MediaPreview";
import type { FileViewKind } from "./fileKinds";
import { fileBadge } from "./ideLanguage";
import { runCommandForPath } from "./runFile";

type OpenTab = {
  path: string;
  content: string;
  dirty: boolean;
  truncated?: boolean;
  kind: FileViewKind;
  size?: number;
  mime?: string;
};

function nestTree(entries: TreeEntry[]): TreeNodeData[] {
  const root: TreeNodeData[] = [];
  const dirs = new Map<string, TreeNodeData>();

  for (const e of entries) {
    if (e.type === "dir") {
      dirs.set(e.path, { name: e.name, path: e.path, type: "dir", children: [] });
    }
  }
  for (const e of entries) {
    const parentPath = e.path.includes("/") ? e.path.slice(0, e.path.lastIndexOf("/")) : "";
    const node: TreeNodeData =
      e.type === "dir"
        ? dirs.get(e.path) || { name: e.name, path: e.path, type: "dir", children: [] }
        : { name: e.name, path: e.path, type: "file" };
    if (!parentPath) {
      if (!root.find((r) => r.path === node.path)) root.push(node);
    } else {
      const parent = dirs.get(parentPath);
      if (parent) {
        parent.children = parent.children || [];
        if (!parent.children.find((c) => c.path === node.path)) parent.children.push(node);
      } else if (!root.find((r) => r.path === node.path)) {
        root.push(node);
      }
    }
  }
  return root;
}

export function SpixaIde({ initialProjectId }: { initialProjectId?: string }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState(initialProjectId || "");
  const [agentSessionId, setAgentSessionId] = useState<string | null>(null);
  const [pendingOpenFile, setPendingOpenFile] = useState<string | null>(null);
  const [entries, setEntries] = useState<TreeEntry[]>([]);
  const [tabs, setTabs] = useState<OpenTab[]>([]);
  const [activePath, setActivePath] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [newName, setNewName] = useState("");
  const [folderPath, setFolderPath] = useState("");
  const [showOpenFolder, setShowOpenFolder] = useState(false);
  const [showDiskBrowser, setShowDiskBrowser] = useState(false);
  /** Exclusive side panel — Agent | Venture | closed (closed by default for workspace) */
  const [rightPanel, setRightPanel] = useState<IdeRightPanel>(null);
  const [ventureSeed, setVentureSeed] = useState<string | null>(null);
  const showAgent = rightPanel === "agent";
  const showVenture = rightPanel === "venture";
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [paletteQ, setPaletteQ] = useState("");
  const [wordWrap, setWordWrap] = useState(true);
  const [explorerOpen, setExplorerOpen] = useState(true);
  const [terminalOpen, setTerminalOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [previewKey, setPreviewKey] = useState(0);
  const [explorerW, setExplorerW] = useState(240);
  const [dockW, setDockW] = useState(420);
  const [layoutReady, setLayoutReady] = useState(false);
  const explorerWRef = useRef(explorerW);
  const dockWRef = useRef(dockW);
  explorerWRef.current = explorerW;
  dockWRef.current = dockW;
  const dragRef = useRef<{ kind: "explorer" | "dock"; startX: number; startW: number } | null>(null);
  const [cursor, setCursor] = useState<EditorCursorState>({ line: 1, column: 1, selected: 0 });
  const [problems, setProblems] = useState<IdeProblem[]>([]);
  const editorApi = useRef<{
    format: () => void;
    focus: () => void;
    reveal: (line: number, column?: number) => void;
  } | null>(null);
  const bottomRef = useRef<IdeBottomPanelHandle | null>(null);

  useIdeTopbarActive(true);
  const topbarHost = useIdeTopbarHost();

  const active = tabs.find((t) => t.path === activePath) || null;
  const tree = useMemo(() => nestTree(entries), [entries]);
  const files = useMemo(() => entries.filter((e) => e.type === "file"), [entries]);
  const paletteHits = useMemo(() => {
    const q = paletteQ.trim().toLowerCase();
    if (!q) return files.slice(0, 40);
    return files.filter((f) => f.path.toLowerCase().includes(q)).slice(0, 40);
  }, [files, paletteQ]);
  const crumbs = activePath ? activePath.split("/") : [];
  const activeProject = projects.find((p) => p.id === projectId) || null;
  const diskPath = activeProject?.workspace_path || activeProject?.source_uri || "";

  const reloadTree = useCallback(async (pid: string) => {
    if (!pid) return;
    try {
      const { resolveProjectApiBase } = await import("@/lib/projectApi");
      await resolveProjectApiBase(pid);
    } catch {
      /* still attempt tree */
    }
    const data = await fetchWorkspaceTree(pid);
    const rows = Array.isArray(data.entries) ? data.entries : [];
    setEntries(rows);
    if (!rows.length) {
      setStatus("المستكشف فارغ — تأكد أن الـ API المحلي يعمل على المنفذ 7000 ثم حدّث المستكشف.");
    }
  }, []);

  const refreshProjects = useCallback(async (preferId?: string, upsert?: Project) => {
    const list = await fetchProjects();
    setProjects(() => {
      if (upsert && !list.some((p) => p.id === upsert.id)) {
        return [upsert, ...list];
      }
      return list.map((p) => (upsert && p.id === upsert.id ? { ...p, ...upsert } : p));
    });
    if (preferId) {
      setProjectId(preferId);
      return;
    }
    setProjectId((cur) => cur || upsert?.id || list[0]?.id || "");
  }, []);

  useEffect(() => {
    void refreshProjects(initialProjectId);
  }, [initialProjectId, refreshProjects]);

  useEffect(() => {
    const L = loadIdeLayout();
    setExplorerOpen(L.explorerOpen);
    setTerminalOpen(L.terminalOpen);
    setRightPanel(L.rightPanel);
    setExplorerW(L.explorerW);
    setDockW(L.dockW);
    setLayoutReady(true);
  }, []);

  useEffect(() => {
    if (!layoutReady) return;
    saveIdeLayout({
      explorerOpen,
      terminalOpen,
      rightPanel,
      explorerW,
      dockW,
    });
  }, [layoutReady, explorerOpen, terminalOpen, rightPanel, explorerW, dockW]);

  useEffect(() => {
    function onMove(ev: PointerEvent) {
      const drag = dragRef.current;
      if (!drag) return;
      const rtl = document.documentElement.dir === "rtl";
      const dx = ev.clientX - drag.startX;
      // In RTL explorer is on the visual right; dock on the visual left.
      if (drag.kind === "explorer") {
        const next = Math.min(520, Math.max(180, drag.startW + (rtl ? -dx : dx)));
        setExplorerW(next);
      } else {
        const next = Math.min(720, Math.max(300, drag.startW + (rtl ? dx : -dx)));
        setDockW(next);
      }
    }
    function onUp() {
      const drag = dragRef.current;
      if (!drag) return;
      dragRef.current = null;
      document.body.classList.remove("ide-resizing");
      saveIdeLayout({
        explorerW: explorerWRef.current,
        dockW: dockWRef.current,
      });
    }
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, []);

  function beginResize(kind: "explorer" | "dock", e: ReactPointerEvent) {
    e.preventDefault();
    dragRef.current = {
      kind,
      startX: e.clientX,
      startW: kind === "explorer" ? explorerWRef.current : dockWRef.current,
    };
    document.body.classList.add("ide-resizing");
  }

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const openPath = params.get("open");
    const pid = params.get("project");
    const session = params.get("session");
    const share = params.get("share");
    const filePath = params.get("file");
    const venture = params.get("venture");
    if (pid) setProjectId(pid);
    if (session) {
      setAgentSessionId(session);
      setRightPanel("agent");
    }
    if (venture) {
      setVentureSeed(venture);
      setRightPanel("venture");
    }
    if (filePath) {
      setRightPanel((cur) => cur || "agent");
      setPendingOpenFile(filePath);
    }
    if (share) {
      void (async () => {
        const hit = await resolveShare(share);
        if (!hit) {
          setStatus("رابط المشاركة غير صالح أو منتهٍ.");
          return;
        }
        setProjectId(hit.project_id);
        setAgentSessionId(hit.session_id);
        setRightPanel("agent");
        setStatus(`فُتح تبويب مشارك · ${hit.title}`);
        const url = new URL(window.location.href);
        url.searchParams.delete("share");
        url.searchParams.set("project", hit.project_id);
        url.searchParams.set("session", hit.session_id);
        window.history.replaceState({}, "", `${url.pathname}?${url.searchParams.toString()}`);
      })();
    }
    if (openPath) {
      setFolderPath(openPath);
      void (async () => {
        setBusy(true);
        const result = await openLocalProjectFolder(openPath);
        setBusy(false);
        if (!result.ok) {
          setShowOpenFolder(true);
          setStatus("تعذّر فتح المجلد من الرابط — عدّل المسار وحاول مجددًا.");
          return;
        }
        await refreshProjects(result.project.id, result.project);
        setShowOpenFolder(false);
        setStatus(`فُتح المجلد · ${result.project.name}`);
        window.history.replaceState({}, "", "/ide");
      })();
    }
  }, [refreshProjects]);

  useEffect(() => {
    if (!projectId) return;
    void reloadTree(projectId);
    setTabs([]);
    setActivePath(null);
    setProblems([]);
  }, [projectId, reloadTree]);

  useEffect(() => {
    if (!projectId || !pendingOpenFile) return;
    const path = pendingOpenFile;
    const timer = window.setTimeout(() => {
      setPendingOpenFile(null);
      void openFile(path);
    }, 120);
    return () => window.clearTimeout(timer);
    // Intentionally open once when project + pending path are ready
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, pendingOpenFile]);

  useEffect(() => {
    if (!active || active.kind !== "code") setProblems([]);
  }, [active?.path, active?.kind]);

  async function openFile(path: string) {
    if (!projectId) return;
    const existing = tabs.find((t) => t.path === path);
    if (existing) {
      setActivePath(path);
      setPaletteOpen(false);
      return;
    }
    setBusy(true);
    const data = await fetchWorkspaceFile(projectId, path);
    setBusy(false);
    if (!data.ok) {
      setStatus(String(data.error || "تعذّر فتح الملف"));
      return;
    }
    const kind: FileViewKind =
      !data.kind || data.kind === "text" ? "code" : (data.kind as FileViewKind);
    setTabs((t) => [
      ...t,
      {
        path,
        content: kind === "code" ? data.content || "" : "",
        dirty: false,
        truncated: data.truncated,
        kind,
        size: data.size,
        mime: data.mime,
      },
    ]);
    setActivePath(path);
    setStatus(path);
    setPaletteOpen(false);
  }

  function updateContent(value: string) {
    if (!activePath) return;
    setTabs((all) =>
      all.map((t) => (t.path === activePath ? { ...t, content: value, dirty: true } : t)),
    );
  }

  const refreshPreviewFrame = useCallback(() => {
    setPreviewKey((k) => k + 1);
  }, []);

  async function saveActive() {
    if (!projectId || !active || active.kind !== "code") return;
    setBusy(true);
    const res = await saveWorkspaceFile(projectId, active.path, active.content);
    setBusy(false);
    if (!res.ok) {
      setStatus(`فشل الحفظ: ${res.error}`);
      return;
    }
    setTabs((all) => all.map((t) => (t.path === active.path ? { ...t, dirty: false } : t)));
    setStatus(`حُفظ · ${active.path}`);
    if (previewUrl) refreshPreviewFrame();
  }

  async function createFile() {
    if (!projectId || !newName.trim()) return;
    let path = newName.trim().replace(/\\/g, "/").replace(/^\/+/, "");
    const asDir = path.endsWith("/");
    if (asDir) path = path.replace(/\/+$/, "");
    if (!path) return;
    const kind = asDir ? "dir" : "file";
    const res = await createWorkspaceEntry(projectId, path, kind);
    if (!res.ok) {
      setStatus(`تعذّر الإنشاء: ${res.error}`);
      return;
    }
    setNewName("");
    await reloadTree(projectId);
    if (kind === "file") await openFile(path);
    else setStatus(`مجلد جديد على جهازك · ${path}/`);
  }

  async function openFolder() {
    const local = folderPath.trim();
    if (!local) return;
    setBusy(true);
    const result = await openLocalProjectFolder(local, `Opened from Spixa IDE · ${local}`);
    setBusy(false);
    if (!result.ok) {
      setStatus("تعذّر فتح المجلد — تحقق من المسار والصلاحيات.");
      return;
    }
    setShowOpenFolder(false);
    setFolderPath("");
    await refreshProjects(result.project.id, result.project);
    setStatus(`فُتح المجلد · ${result.project.name}`);
  }

  async function pickDesktopFolder() {
    if (isSpixaDesktop()) {
      const chosen = await pickLocalFolder();
      if (chosen) {
        setFolderPath(chosen);
        setBusy(true);
        const result = await openLocalProjectFolder(chosen, `Opened from desktop picker · ${chosen}`);
        setBusy(false);
        if (!result.ok) {
          setShowDiskBrowser(true);
          setStatus("تعذّر فتح المجلد المختار.");
          return;
        }
        setShowOpenFolder(false);
        setShowDiskBrowser(false);
        await refreshProjects(result.project.id, result.project);
        setStatus(`فُتح المجلد · ${result.project.name}`);
        return;
      }
    }
    setShowDiskBrowser(true);
  }

  async function bindChosenFolder(chosen: string): Promise<{ ok: boolean; error?: string }> {
    setBusy(true);
    const result = await openLocalProjectFolder(chosen, `Opened from disk browser · ${chosen}`);
    setBusy(false);
    if (!result.ok) {
      const text = openFolderErrorMessage(result.error);
      setStatus(text);
      return { ok: false, error: text };
    }
    setShowDiskBrowser(false);
    setShowOpenFolder(false);
    await refreshProjects(result.project.id, result.project);
    setStatus(`فُتح المجلد · ${result.project.name}`);
    return { ok: true };
  }

  function closeTab(path: string) {
    setTabs((all) => {
      const next = all.filter((t) => t.path !== path);
      if (activePath === path) setActivePath(next[next.length - 1]?.path || null);
      return next;
    });
  }

  function cycleTab(dir: 1 | -1) {
    if (!tabs.length) return;
    const idx = Math.max(0, tabs.findIndex((t) => t.path === activePath));
    const next = tabs[(idx + dir + tabs.length) % tabs.length];
    if (next) setActivePath(next.path);
  }

  async function saveAllDirty() {
    if (!projectId) return;
    const dirty = tabs.filter((t) => t.dirty && t.kind === "code");
    if (!dirty.length) return;
    setBusy(true);
    for (const tab of dirty) {
      const res = await saveWorkspaceFile(projectId, tab.path, tab.content);
      if (!res.ok) {
        setBusy(false);
        setStatus(`فشل الحفظ: ${tab.path} · ${res.error}`);
        return;
      }
    }
    setTabs((all) => all.map((t) => ({ ...t, dirty: false })));
    setBusy(false);
    setStatus(`حُفظ ${dirty.length} ملف`);
    if (previewUrl) refreshPreviewFrame();
  }

  async function applyEdits(edits: FileEdit[]) {
    if (!projectId || !edits.length) return;
    const applied: string[] = [];
    const failed: string[] = [];
    let lastFile: string | null = null;
    setBusy(true);
    for (const edit of edits) {
      if (edit.kind === "dir") {
        const res = await createWorkspaceEntry(projectId, edit.path.replace(/\/+$/, ""), "dir");
        if (res.ok) applied.push(edit.path);
        else failed.push(edit.path);
        continue;
      }
      const res = await saveWorkspaceFile(projectId, edit.path, edit.content);
      if (!res.ok) {
        failed.push(edit.path);
        continue;
      }
      applied.push(edit.path);
      lastFile = edit.path;
      setTabs((all) => {
        const hit = all.find((t) => t.path === edit.path);
        if (hit) {
          return all.map((t) =>
            t.path === edit.path ? { ...t, content: edit.content, dirty: false, kind: "code" } : t,
          );
        }
        return [
          ...all,
          {
            path: edit.path,
            content: edit.content,
            dirty: false,
            kind: "code" as const,
          },
        ];
      });
    }
    if (lastFile) setActivePath(lastFile);
    await reloadTree(projectId);
    setBusy(false);
    if (failed.length && !applied.length) {
      setStatus(`فشل تطبيق التعديلات · ${failed.join(", ")}`);
      void recordCodingTaskOutcome(false, "ide_apply_ui");
      throw new Error("apply_edits_failed");
    }
    void recordCodingTaskOutcome(failed.length === 0, "ide_apply_ui");
    if (failed.length) {
      setStatus(`طُبّق ${applied.length} · فشل: ${failed.join(", ")}`);
    } else {
      setStatus(`طُبّقت تعديلات الوكيل · ${applied.join(", ")}`);
    }
    if (previewUrl && applied.length) {
      refreshPreviewFrame();
    }
  }

  const ensureLivePreview = useCallback(
    async (opts?: { open?: boolean; silent?: boolean }) => {
      if (!projectId) return;
      setPreviewBusy(true);
      try {
        const started = await startWorkspacePreview(projectId);
        if (!started.running || !started.url) {
          setPreviewUrl(null);
          if (!opts?.silent) {
            setStatus(`معاينة: ${started.error || "تعذّر التشغيل"}`);
          }
          void learnFromOperation({
            kind: "preview_fail",
            title: "Live preview failed",
            detail: String(started.error || "preview_start_failed"),
            projectId,
            intent: "implement",
          });
          return;
        }
        setPreviewUrl(started.url);
        if (opts?.open !== false) setPreviewOpen(true);
        refreshPreviewFrame();
        if (!opts?.silent) {
          setStatus(`Live Preview · ${started.url}`);
        }
        bottomRef.current?.appendOutput(`Live Preview · ${started.url}`, "meta");
        void learnFromOperation({
          kind: "preview_ok",
          title: "Live preview running",
          detail: started.url,
          projectId,
          intent: "implement",
          humanVerified: true,
        });
      } finally {
        setPreviewBusy(false);
      }
    },
    [projectId, refreshPreviewFrame],
  );

  const stopLivePreview = useCallback(async () => {
    if (!projectId) return;
    setPreviewBusy(true);
    try {
      await stopWorkspacePreview(projectId);
      setPreviewUrl(null);
      setPreviewOpen(false);
      setStatus("توقفت المعاينة");
    } finally {
      setPreviewBusy(false);
    }
  }, [projectId]);

  const toggleLivePreview = useCallback(async () => {
    if (!projectId) return;
    if (previewOpen && previewUrl) {
      setPreviewOpen(false);
      return;
    }
    const status = await fetchPreviewStatus(projectId);
    if (status.running && status.url) {
      setPreviewUrl(status.url);
      setPreviewOpen(true);
      refreshPreviewFrame();
      return;
    }
    await ensureLivePreview({ open: true });
  }, [projectId, previewOpen, previewUrl, ensureLivePreview, refreshPreviewFrame]);

  const previewProjectRef = useRef<string | null>(null);
  useEffect(() => {
    const prev = previewProjectRef.current;
    if (prev && prev !== projectId) {
      void stopWorkspacePreview(prev);
      setPreviewOpen(false);
      setPreviewUrl(null);
    }
    previewProjectRef.current = projectId || null;
    if (!projectId) {
      setPreviewOpen(false);
      setPreviewUrl(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      const status = await fetchPreviewStatus(projectId);
      if (cancelled) return;
      if (status.running && status.url) {
        setPreviewUrl(status.url);
      } else {
        setPreviewUrl(null);
        setPreviewOpen(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const mod = e.ctrlKey || e.metaKey;
      const key = e.key.toLowerCase();
      if (mod && key === "s") {
        e.preventDefault();
        if (e.shiftKey) void saveAllDirty();
        else void saveActive();
        return;
      }
      if (mod && key === "p") {
        e.preventDefault();
        setPaletteOpen(true);
        setPaletteQ("");
        return;
      }
      if (mod && key === "o") {
        e.preventDefault();
        void pickDesktopFolder();
        return;
      }
      if (mod && key === "w") {
        e.preventDefault();
        if (activePath) closeTab(activePath);
        return;
      }
      if (mod && key === "tab") {
        e.preventDefault();
        cycleTab(e.shiftKey ? -1 : 1);
        return;
      }
      if (mod && key === "b") {
        e.preventDefault();
        setExplorerOpen((v) => !v);
        return;
      }
      if (mod && key === "l") {
        e.preventDefault();
        setRightPanel((cur) => (cur === "agent" ? null : "agent"));
        return;
      }
      if (mod && e.shiftKey && key === "v") {
        e.preventDefault();
        setRightPanel((cur) => (cur === "venture" ? null : "venture"));
        return;
      }
      if (mod && e.key === "`") {
        e.preventDefault();
        setTerminalOpen((v) => !v);
        return;
      }
      if (mod && e.key === "Enter") {
        e.preventDefault();
        void runActiveFile();
        return;
      }
      if (e.key === "Escape") {
        setPaletteOpen(false);
        setPaletteQ("");
        setShowOpenFolder(false);
        setShowDiskBrowser(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const projectLabel = activeProject?.name || "بدون مشروع";
  const fileCount = files.length;
  const runCmd = active?.kind === "code" ? runCommandForPath(active.path) : null;

  async function runActiveFile() {
    if (!runCmd || !projectId) {
      setStatus("لا أمر تشغيل لهذا النوع من الملفات.");
      return;
    }
    if (active?.dirty) await saveActive();
    setTerminalOpen(true);
    bottomRef.current?.showTab("terminal");
    setStatus(`تشغيل · ${runCmd}`);
    await bottomRef.current?.run(runCmd);
  }

  const shellStyle = {
    ["--ide-explorer-w" as string]: explorerOpen ? `${explorerW}px` : "44px",
    ["--ide-dock-w" as string]: rightPanel ? `${dockW}px` : "0px",
  } as CSSProperties;

  const ideTopbar = (
    <div className="ide-topbar-chrome">
      <label className="ide-top__project ide-top__project--bar">
        <span className="sr-only">المشروع</span>
        <select value={projectId} onChange={(e) => setProjectId(e.target.value)} title="المشروع">
          {!projects.length && <option value="">لا مشاريع</option>}
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </label>
      <div className="ide-top__toolbar" role="toolbar" aria-label="أدوات IDE">
        <div className="ide-top__group">
          <button
            type="button"
            className={`ide-tb ${explorerOpen ? "is-on" : ""}`}
            onClick={() => setExplorerOpen((v) => !v)}
            title="المستكشف (Ctrl+B)"
          >
            مستكشف
          </button>
          <button type="button" className="ide-tb" onClick={() => void pickDesktopFolder()} title="فتح مجلد">
            مجلد
          </button>
          <button type="button" className="ide-tb" onClick={() => setPaletteOpen(true)} title="بحث ملف (Ctrl+P)">
            بحث
          </button>
        </div>
        <i className="ide-top__sep" aria-hidden />
        <div className="ide-top__group">
          <button
            type="button"
            className="ide-tb ide-tb--accent"
            disabled={!active || active.kind !== "code" || !active.dirty || busy}
            onClick={() => void saveActive()}
            title="حفظ (Ctrl+S)"
          >
            حفظ
          </button>
          <button
            type="button"
            className="ide-tb"
            disabled={!runCmd || busy}
            onClick={() => void runActiveFile()}
            title="تشغيل (Ctrl+Enter)"
          >
            تشغيل
          </button>
        </div>
        <i className="ide-top__sep" aria-hidden />
        <div className="ide-top__group">
          <button
            type="button"
            className={`ide-tb ${terminalOpen ? "is-on" : ""}`}
            onClick={() => setTerminalOpen((v) => !v)}
            title="اللوحة السفلية (Ctrl+`)"
          >
            لوحة
          </button>
          <button
            type="button"
            className={`ide-tb ${previewOpen ? "is-on" : ""}`}
            disabled={!projectId || previewBusy}
            onClick={() => void toggleLivePreview()}
            title="Live Preview — اختبر الموقع أثناء البناء"
          >
            {previewBusy ? "…" : previewOpen ? "إخفاء المعاينة" : "معاينة"}
          </button>
              <button
                type="button"
                className={`ide-tb ${showAgent ? "is-on" : ""}`}
                onClick={() => setRightPanel((cur) => (cur === "agent" ? null : "agent"))}
                title={showAgent ? "إخفاء الوكيل (Ctrl+L)" : "إظهار الوكيل (Ctrl+L)"}
              >
                {showAgent ? "إخفاء الوكيل" : "الوكيل"}
              </button>
              <button
                type="button"
                className={`ide-tb ${showVenture ? "is-on" : ""}`}
                onClick={() => setRightPanel((cur) => (cur === "venture" ? null : "venture"))}
                title={showVenture ? "إخفاء Venture (Ctrl+Shift+V)" : "إظهار Venture (Ctrl+Shift+V)"}
              >
                {showVenture ? "إخفاء Venture" : "Venture"}
              </button>
          <Link href="/download" className="ide-tb" title="تطبيق سطح المكتب">
            سطح المكتب
          </Link>
        </div>
      </div>
      {busy ? (
        <span className="ide-pill ide-pill--bar is-busy" title={status || "يعمل…"}>
          يعمل…
        </span>
      ) : null}
    </div>
  );

  return (
    <div
      className={`ide-shell ${rightPanel ? "has-agent" : ""} ${rightPanel === "venture" ? "has-venture" : ""} ${previewOpen ? "has-preview" : ""} ${explorerOpen ? "" : "explorer-collapsed"}`.trim()}
      style={shellStyle}
    >
      {topbarHost ? createPortal(ideTopbar, topbarHost) : null}
      {status ? (
        <div className="ide-live-status" role="status">
          {status}
        </div>
      ) : null}

      <div className="ide-body">
        <aside className={`ide-sidebar ${explorerOpen ? "" : "is-collapsed"}`.trim()}>
          {explorerOpen ? (
          <>
          <div className="ide-sidebar__head">
            <div className="ide-sidebar__title">
              <strong>المستكشف</strong>
              <em>{projectLabel}</em>
            </div>
            <div className="ide-sidebar__head-actions">
              <button
                type="button"
                className="ide-icon-btn"
                onClick={() => void reloadTree(projectId)}
                title="تحديث"
                aria-label="تحديث الشجرة"
              >
                ↻
              </button>
              <button
                type="button"
                className="ide-icon-btn"
                onClick={() => setExplorerOpen(false)}
                title="طي المستكشف"
                aria-label="طي المستكشف"
              >
                «
              </button>
            </div>
          </div>
          <div className="ide-sidebar__stats">
            <span>{fileCount} ملف</span>
            <span dir="ltr">{diskPath ? diskPath.split(/[\\/]/).pop() : "—"}</span>
          </div>
          <div className="ide-new">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="ملف جديد… مثل src/app.ts"
              dir="ltr"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  void createFile();
                }
              }}
            />
            <button type="button" className="ide-icon-btn" onClick={() => void createFile()} title="إنشاء">
              +
            </button>
          </div>
          <IdeFileTree
            tree={tree}
            active={activePath}
            onOpen={(p) => void openFile(p)}
            emptyHint="افتح مجلدًا من جهازك أو أنشئ ملفًا للبدء."
          />
          </>
          ) : (
            <button
              type="button"
              className="ide-sidebar__rail"
              onClick={() => setExplorerOpen(true)}
              title="فتح المستكشف"
              aria-label="فتح المستكشف"
            >
              <span>المستكشف</span>
            </button>
          )}
          {explorerOpen ? (
            <div
              className="ide-sash ide-sash--explorer"
              role="separator"
              aria-orientation="vertical"
              aria-label="تغيير عرض المستكشف"
              onPointerDown={(e) => beginResize("explorer", e)}
            />
          ) : null}
        </aside>

        <main className="ide-main">
          <div className="ide-editor-chrome">
            <div className="ide-tabs" dir="ltr">
              {tabs.length ? (
                tabs.map((t) => {
                  const badge = fileBadge(t.path);
                  return (
                    <div
                      key={t.path}
                      className={`ide-tab ${t.path === activePath ? "is-active" : ""} ${t.dirty ? "is-dirty" : ""}`}
                      onMouseDown={(e) => {
                        if (e.button === 1) {
                          e.preventDefault();
                          closeTab(t.path);
                        }
                      }}
                    >
                      <button type="button" onClick={() => setActivePath(t.path)} title={t.path}>
                        <span className={`ide-tab__badge is-${badge.kind}`} aria-hidden>
                          {badge.label}
                        </span>
                        <span className="ide-tab__name">{t.path.split("/").pop()}</span>
                        {t.dirty ? <i className="ide-tab__dirty" title="غير محفوظ" /> : null}
                      </button>
                      <button
                        type="button"
                        className="ide-tab__close"
                        onClick={() => closeTab(t.path)}
                        aria-label="إغلاق"
                      >
                        ×
                      </button>
                    </div>
                  );
                })
              ) : (
                <div className="ide-tabs__empty">لا ملفات مفتوحة</div>
              )}
            </div>
            {activePath ? (
              <div className="ide-crumbs" dir="ltr">
                {crumbs.map((c, i) => (
                  <span key={`${c}-${i}`} className="ide-crumbs__seg">
                    {i > 0 ? <i>/</i> : null}
                    {c}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
          {active ? (
            active.kind === "code" ? (
              <>
                <CodeEditor
                  path={active.path}
                  value={active.content}
                  onChange={updateContent}
                  projectId={projectId}
                  wordWrap={wordWrap}
                  onCursorChange={setCursor}
                  onProblems={setProblems}
                  onReady={(api) => {
                    editorApi.current = api;
                  }}
                />
                <IdeStatusBar
                  path={active.path}
                  dirty={active.dirty}
                  cursor={cursor}
                  wordWrap={wordWrap}
                  onToggleWrap={() => setWordWrap((v) => !v)}
                  onFormat={() => editorApi.current?.format()}
                  onRun={() => void runActiveFile()}
                  canRun={Boolean(runCmd)}
                  problemCount={problems.length}
                  onOpenProblems={() => {
                    setTerminalOpen(true);
                    bottomRef.current?.showTab("problems");
                  }}
                />
              </>
            ) : projectId ? (
              <MediaPreview
                projectId={projectId}
                path={active.path}
                kind={active.kind}
                size={active.size}
                mime={active.mime}
              />
            ) : null
          ) : projectId ? (
            <div className="ide-welcome ide-welcome--ready">
              <div className="ide-welcome__badge">مساحة مرتبطة</div>
              <h1>{projectLabel}</h1>
              <p>
                اختر ملفًا من المستكشف، أو أنشئ ملفًا جديدًا. الحفظ يكتب مباشرة على جهازك
                {diskPath ? (
                  <>
                    {" "}
                    في <code dir="ltr">{diskPath}</code>
                  </>
                ) : null}
                .
              </p>
              <div className="ide-welcome__actions">
                <button type="button" className="btn btn-primary" onClick={() => setPaletteOpen(true)}>
                  بحث عن ملف
                </button>
                <button type="button" className="btn btn-ghost" onClick={() => void pickDesktopFolder()}>
                  تغيير المجلد
                </button>
              </div>
              <div className="ide-welcome__hints">
                <span>
                  <kbd>Ctrl</kbd>
                  <kbd>P</kbd>
                  بحث سريع في الملفات
                </span>
                <span>
                  <kbd>Ctrl</kbd>
                  <kbd>S</kbd>
                  حفظ · <kbd>Ctrl</kbd>
                  <kbd>Shift</kbd>
                  <kbd>S</kbd>
                  حفظ الكل
                </span>
                <span>
                  <kbd>Ctrl</kbd>
                  <kbd>W</kbd>
                  إغلاق تبويب · <kbd>Ctrl</kbd>
                  <kbd>Shift</kbd>
                  <kbd>F</kbd>
                  تنسيق
                </span>
              </div>
            </div>
          ) : (
            <div className="ide-welcome">
              <div className="ide-welcome__badge">IDE</div>
              <h1>مساحة عمل {PRODUCT}</h1>
              <p>افتح مجلدًا على جهازك لبدء التحرير — الملفات تبقى عندك والمستكشف يعرضها بتنظيم احترافي.</p>
              <div className="ide-welcome__actions">
                <button type="button" className="btn btn-primary" onClick={() => void pickDesktopFolder()}>
                  فتح مجلد
                </button>
                <Link href="/download" className="btn btn-ghost">
                  تنزيل سطح المكتب
                </Link>
              </div>
            </div>
          )}
          {active?.truncated ? <p className="ide-banner">الملف كبير — عُرض جزء منه فقط.</p> : null}
          {projectId ? (
            <IdeBottomPanel
              ref={bottomRef}
              projectId={projectId}
              open={terminalOpen}
              onToggle={() => setTerminalOpen((v) => !v)}
              problems={problems}
              activePath={activePath}
              onOpenProblem={(p) => {
                void openFile(p.path).then(() => {
                  window.setTimeout(() => editorApi.current?.reveal(p.line, p.column), 80);
                });
              }}
            />
          ) : null}
        </main>

        {previewOpen && projectId ? (
          <aside className="ide-preview" aria-label="Live Preview">
            <div className="ide-preview__head">
              <div className="ide-preview__title">
                <strong>معاينة مباشرة</strong>
                {previewUrl ? (
                  <a href={previewUrl} target="_blank" rel="noreferrer" dir="ltr">
                    {previewUrl}
                  </a>
                ) : (
                  <span>جاري التشغيل…</span>
                )}
              </div>
              <div className="ide-preview__actions">
                <button
                  type="button"
                  className="ide-tb"
                  disabled={previewBusy}
                  onClick={() => refreshPreviewFrame()}
                  title="تحديث"
                >
                  تحديث
                </button>
                <button
                  type="button"
                  className="ide-tb"
                  disabled={previewBusy}
                  onClick={() => void ensureLivePreview({ open: true })}
                  title="إعادة تشغيل السيرفر"
                >
                  تشغيل
                </button>
                <button
                  type="button"
                  className="ide-tb"
                  disabled={previewBusy}
                  onClick={() => void stopLivePreview()}
                  title="إيقاف السيرفر"
                >
                  إيقاف
                </button>
                <button
                  type="button"
                  className="ide-tb"
                  onClick={() => setPreviewOpen(false)}
                  title="إخفاء اللوحة"
                >
                  إغلاق
                </button>
              </div>
            </div>
            {previewUrl ? (
              <iframe
                key={previewKey}
                className="ide-preview__frame"
                title="Live Preview"
                src={previewUrl}
              />
            ) : (
              <div className="ide-preview__empty">اضغط تشغيل لبدء السيرفر المحلي.</div>
            )}
          </aside>
        ) : null}

        {rightPanel && projectId ? (
          <div className="ide-right-dock" data-panel={rightPanel}>
            <div
              className="ide-sash ide-sash--dock"
              role="separator"
              aria-orientation="vertical"
              aria-label="تغيير عرض لوحة الوكيل"
              onPointerDown={(e) => beginResize("dock", e)}
            />
            {rightPanel === "venture" ? (
              <IdeVenturePanel
                projectId={projectId}
                onLog={(text) => bottomRef.current?.appendOutput(text, "meta")}
                seedBrief={ventureSeed}
                onSeedConsumed={() => setVentureSeed(null)}
              />
            ) : (
              <IdeAgentPanel
                projectId={projectId}
                activePath={activePath}
                treePaths={entries.map((e) => e.path)}
                onApplyEdits={applyEdits}
                onOpenPath={(p) => void openFile(p)}
                onLog={(text) => bottomRef.current?.appendOutput(text, "meta")}
                initialSessionId={agentSessionId}
                onAfterWebEdits={() => {
                  void ensureLivePreview({ open: true, silent: false });
                }}
                livePreviewUrl={previewUrl}
                onStartVenture={(brief) => {
                  setVentureSeed(brief);
                  setRightPanel("venture");
                }}
              />
            )}
          </div>
        ) : null}
      </div>

      {paletteOpen && (
        <div
          className="ide-modal"
          role="dialog"
          aria-label="بحث الملفات"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) {
              setPaletteOpen(false);
              setPaletteQ("");
            }
          }}
        >
          <div
            className="ide-modal__card"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <input
              autoFocus
              dir="ltr"
              value={paletteQ}
              onChange={(e) => setPaletteQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Escape") {
                  e.preventDefault();
                  setPaletteOpen(false);
                  setPaletteQ("");
                }
              }}
              placeholder="ابحث عن ملف… (Esc أو نقرة فارغة للإلغاء)"
            />
            <ul
              onMouseDown={(e) => {
                if (e.target === e.currentTarget) {
                  setPaletteOpen(false);
                  setPaletteQ("");
                }
              }}
            >
              {paletteHits.map((f) => (
                <li key={f.path}>
                  <button
                    type="button"
                    onClick={() => {
                      void openFile(f.path);
                      setPaletteOpen(false);
                      setPaletteQ("");
                    }}
                  >
                    {f.path}
                  </button>
                </li>
              ))}
              {!paletteHits.length && <li className="ide-empty">لا نتائج — انقر خارج القائمة للإغلاق</li>}
            </ul>
          </div>
        </div>
      )}

      <LocalFolderBrowser
        open={showDiskBrowser}
        onClose={() => setShowDiskBrowser(false)}
        onSelect={(folder) => bindChosenFolder(folder)}
      />

      {showOpenFolder && (
        <div className="ide-modal" role="dialog" aria-label="فتح مجلد">
          <div className="ide-modal__card">
            <h2>فتح مجلد محلي</h2>
            <p className="settings-hint">
              تصفّح الأقراص والمجلدات على جهازك، ثم اربط المجلد — الحفظ مباشرة على القرص.
            </p>
            <div className="ide-welcome__actions">
              <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void pickDesktopFolder()}>
                {busy ? "جاري الربط…" : "عرض ملفات الجهاز…"}
              </button>
              <button type="button" className="btn btn-ghost" onClick={() => setShowOpenFolder(false)}>
                إلغاء
              </button>
            </div>
            <details style={{ marginTop: 12 }}>
              <summary className="settings-hint">مسار يدوي (متقدم)</summary>
              <input
                dir="ltr"
                value={folderPath}
                onChange={(e) => setFolderPath(e.target.value)}
                placeholder="C:\Users\...\Desktop\my-project"
                style={{ marginTop: 8, width: "100%" }}
              />
              <button
                type="button"
                className="btn btn-ghost"
                style={{ marginTop: 8 }}
                disabled={busy || !folderPath.trim()}
                onClick={() => void openFolder()}
              >
                استيراد المسار
              </button>
            </details>
          </div>
        </div>
      )}
    </div>
  );
}
