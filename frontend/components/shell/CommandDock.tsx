"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { IdeAgentPanel } from "@/components/ide/IdeAgentPanel";
import { createBlankProject, fetchProjects } from "@/lib/api";
import { applyAgentEdits } from "@/lib/applyAgentEdits";
import type { Project } from "@/lib/types";
import { fetchWorkspaceTree } from "@/lib/workspace";

/**
 * Global floating agent — identical IdeAgentPanel as the IDE.
 * Accepts commands on every page (except /ide where the docked panel exists).
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
  const [booting, setBooting] = useState(false);

  const project = projects.find((p) => p.id === projectId) || null;

  const ensureAgentProject = useCallback(async () => {
    setBooting(true);
    setStatus("");
    try {
      let rows = await fetchProjects();
      if (!rows.length) {
        const created = await createBlankProject({
          name: "مساحة الأوامر",
          description: "جلسة أوامر سريعة من زر الوكيل — نفس وكيل المحرر",
        });
        if (created) {
          rows = [created];
          setStatus("تم تجهيز مساحة أوامر تلقائياً — اكتب أمرك مباشرة.");
        }
      }
      setProjects(rows);
      setProjectId((cur) => {
        if (cur && rows.some((p) => p.id === cur)) return cur;
        return rows[0]?.id || "";
      });
      return rows[0]?.id || "";
    } finally {
      setBooting(false);
    }
  }, []);

  useEffect(() => {
    if (hideOnIde) setOpen(false);
  }, [hideOnIde]);

  useEffect(() => {
    void fetchProjects().then((rows) => {
      setProjects(rows);
      setProjectId((cur) => cur || rows[0]?.id || "");
    });
  }, []);

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
    if (!open || hideOnIde) return;
    void ensureAgentProject();
  }, [open, hideOnIde, ensureAgentProject]);

  if (hideOnIde) return null;

  return (
    <>
      <button
        type="button"
        className={`cmd-fab ${open ? "is-open" : ""}`}
        onClick={() => setOpen((v) => !v)}
        title="وكيل Spixa — اكتب أوامر (Ctrl+J)"
        aria-label="فتح وكيل الأوامر"
        aria-expanded={open}
      >
        <span className="cmd-fab__glyph">⌘</span>
        <span className="cmd-fab__label">الوكيل</span>
      </button>

      {open && (
        <div className="cmd-dock cmd-dock--agent" role="dialog" aria-label="وكيل الأوامر">
          <header className="cmd-dock__head">
            <div>
              <strong>وكيل Spixa</strong>
              <span>نفس ذكاء المحرر — اكتب أوامر، مقترحات، وتعديلات ملفات</span>
            </div>
            <div className="cmd-dock__head-actions">
              {projectId ? (
                <Link
                  href={`/ide?project=${encodeURIComponent(projectId)}`}
                  className="btn btn-ghost"
                  title="فتح نفس الجلسة في المحرر"
                  onClick={() => setOpen(false)}
                >
                  المحرر
                </Link>
              ) : null}
              <button type="button" className="btn btn-ghost" onClick={() => setOpen(false)}>
                إغلاق
              </button>
            </div>
          </header>

          <div className="cmd-dock__project">
            <label htmlFor="cmd-dock-project">السياق</label>
            <select
              id="cmd-dock-project"
              value={projectId}
              disabled={booting || !projects.length}
              onChange={(e) => setProjectId(e.target.value)}
            >
              {booting && !projectId ? <option value="">جاري تجهيز مساحة الأوامر…</option> : null}
              {!booting && !projects.length ? (
                <option value="">تعذّر تجهيز مساحة — أعد المحاولة</option>
              ) : null}
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            {!projectId && !booting ? (
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void ensureAgentProject()}
              >
                تجهيز
              </button>
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
                key={projectId}
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
                      ? `طُبّقت ${edits.length} تعديلات على ${project?.name || "المساحة"}`
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
              <p>
                {booting
                  ? "جاري فتح وكيل الأوامر…"
                  : "اضغط «تجهيز» لبدء جلسة أوامر فورية — نفس وكيل المحرر."}
              </p>
              {!booting ? (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => void ensureAgentProject()}
                >
                  بدء الأوامر الآن
                </button>
              ) : null}
            </div>
          )}
        </div>
      )}
    </>
  );
}
