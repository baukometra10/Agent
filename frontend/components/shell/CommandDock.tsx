"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { IdeAgentPanel } from "@/components/ide/IdeAgentPanel";
import { fetchProjects } from "@/lib/api";
import { applyAgentEdits } from "@/lib/applyAgentEdits";
import type { Project } from "@/lib/types";
import { fetchWorkspaceTree } from "@/lib/workspace";

/**
 * Global Spixa agent — same IdeAgentPanel as the IDE.
 * Hidden on /ide (panel already docked there). Ctrl/Cmd+J elsewhere.
 */
export function CommandDock() {
  const pathname = usePathname() || "";
  const router = useRouter();
  const hideOnIde = pathname === "/ide" || pathname.startsWith("/ide/");
  const [open, setOpen] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [treePaths, setTreePaths] = useState<string[]>([]);
  const [status, setStatus] = useState("");

  const project = projects.find((p) => p.id === projectId) || null;

  const loadProjects = useCallback(async () => {
    const rows = await fetchProjects();
    setProjects(rows);
    setProjectId((cur) => cur || rows[0]?.id || "");
  }, []);

  useEffect(() => {
    if (hideOnIde) setOpen(false);
  }, [hideOnIde]);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  useEffect(() => {
    if (!projectId) {
      setTreePaths([]);
      return;
    }
    let cancelled = false;
    (async () => {
      const tree = await fetchWorkspaceTree(projectId);
      if (cancelled) return;
      setTreePaths((tree.entries || []).filter((e) => e.type === "file").map((e) => e.path));
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (hideOnIde) return;
      const meta = e.ctrlKey || e.metaKey;
      if (meta && e.key.toLowerCase() === "j") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [hideOnIde]);

  useEffect(() => {
    if (!open) return;
    void loadProjects();
  }, [open, loadProjects]);

  if (hideOnIde) return null;

  return (
    <>
      <button
        type="button"
        className={`cmd-fab ${open ? "is-open" : ""}`}
        onClick={() => setOpen((v) => !v)}
        title="وكيل Spixa (Ctrl+J) — نفس وكيل مساحة العمل"
        aria-label="فتح وكيل Spixa"
      >
        <span className="cmd-fab__glyph">⌘</span>
        <span className="cmd-fab__label">الوكيل</span>
      </button>

      {open && (
        <div className="cmd-dock cmd-dock--agent" role="dialog" aria-label="وكيل Spixa">
          <header className="cmd-dock__head">
            <div>
              <strong>وكيل Spixa</strong>
              <span>نفس الوكيل داخل مساحة العمل — الجلسات مشتركة لكل مشروع</span>
            </div>
            <div className="cmd-dock__head-actions">
              {projectId ? (
                <Link
                  href={`/ide?project=${encodeURIComponent(projectId)}`}
                  className="btn btn-ghost"
                  onClick={() => setOpen(false)}
                >
                  في المحرر
                </Link>
              ) : null}
              <button type="button" className="btn btn-ghost" onClick={() => setOpen(false)}>
                إغلاق
              </button>
            </div>
          </header>

          <div className="cmd-dock__project">
            <label htmlFor="cmd-dock-project">المشروع</label>
            <select
              id="cmd-dock-project"
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
            >
              {!projects.length && <option value="">لا مشاريع — افتح مشروعاً أولاً</option>}
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            {!projects.length ? (
              <Link href="/projects" className="btn btn-primary" onClick={() => setOpen(false)}>
                المشاريع
              </Link>
            ) : null}
          </div>

          {status ? (
            <p className="cmd-dock__status" role="status">
              {status}
            </p>
          ) : null}

          {projectId ? (
            <div className="cmd-dock__agent">
              <IdeAgentPanel
                projectId={projectId}
                activePath={null}
                treePaths={treePaths}
                onApplyEdits={async (edits) => {
                  const res = await applyAgentEdits(projectId, edits);
                  if (!res.ok) {
                    setStatus(String(res.error || "تعذّر تطبيق التعديلات"));
                    return;
                  }
                  setStatus(
                    edits.length
                      ? `طُبّقت ${edits.length} تعديلات على ${project?.name || "المشروع"}`
                      : "",
                  );
                  const tree = await fetchWorkspaceTree(projectId);
                  setTreePaths(
                    (tree.entries || []).filter((e) => e.type === "file").map((e) => e.path),
                  );
                }}
                onOpenPath={(path) => {
                  setOpen(false);
                  router.push(
                    `/ide?project=${encodeURIComponent(projectId)}&file=${encodeURIComponent(path)}`,
                  );
                }}
                onLog={(text) => setStatus(text)}
                onStartVenture={(brief) => {
                  setOpen(false);
                  router.push(
                    `/ide?project=${encodeURIComponent(projectId)}&venture=${encodeURIComponent(brief.slice(0, 200))}`,
                  );
                }}
              />
            </div>
          ) : (
            <div className="cmd-dock__empty">
              <p>اربط مشروعاً من «المشاريع» ليبدأ الوكيل بنفس تجربة المحرر.</p>
              <Link href="/projects" className="btn btn-primary" onClick={() => setOpen(false)}>
                فتح المشاريع
              </Link>
            </div>
          )}
        </div>
      )}
    </>
  );
}
