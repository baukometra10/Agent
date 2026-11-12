"use client";

import { useEffect, useMemo, useState } from "react";
import type { FileEdit } from "@/lib/agentEdits";
import { diffStats, hunksFromDiff, lineDiff, type DiffHunk } from "@/lib/agentPanel/tabDiff";
import { fetchWorkspaceFile } from "@/lib/workspace";

type Props = {
  projectId: string;
  edits: FileEdit[];
  /** review = Accept/Skip; applied = Cursor-style inline diffs after auto-write */
  mode?: "review" | "applied";
  onAcceptAll?: () => void;
  onRejectAll?: () => void;
  onAcceptOne?: (path: string) => void;
  onSkipOne?: (path: string) => void;
  onOpenPath?: (path: string) => void;
};

type FilePreview = {
  path: string;
  kind?: "file" | "dir";
  before: string;
  after: string;
  isNew: boolean;
  adds: number;
  dels: number;
  hunks: DiffHunk[];
};

function buildPreview(edit: FileEdit, beforeRaw: string): FilePreview {
  const before = beforeRaw;
  const after = edit.content || "";
  const isNew = !before;
  const diff = lineDiff(before, after);
  const stats = diffStats(diff);
  const hunks =
    isNew && !before
      ? [
          {
            startOld: 0,
            startNew: 1,
            lines: after.split(/\r?\n/).slice(0, 120).map((text, idx) => ({
              type: "add" as const,
              text,
              oldNo: null,
              newNo: idx + 1,
            })),
          },
        ]
      : hunksFromDiff(diff, 2);
  return {
    path: edit.path,
    kind: edit.kind || "file",
    before,
    after,
    isNew,
    adds: isNew ? after.split(/\r?\n/).length : stats.adds,
    dels: stats.dels,
    hunks,
  };
}

export function AgentEditReview({
  projectId,
  edits,
  mode = "review",
  onAcceptAll,
  onRejectAll,
  onAcceptOne,
  onSkipOne,
  onOpenPath,
}: Props) {
  const [previews, setPreviews] = useState<FilePreview[]>([]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const applied = mode === "applied";

  const editKey = useMemo(
    () =>
      edits
        .map(
          (e) =>
            `${e.path}:${e.content.length}:${e.kind || "file"}:${(e.previousContent || "").length}`,
        )
        .join("|"),
    [edits],
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      const rows: FilePreview[] = [];
      for (const edit of edits) {
        if (edit.kind === "dir") {
          rows.push({
            path: edit.path,
            kind: "dir",
            before: "",
            after: "",
            isNew: true,
            adds: 0,
            dels: 0,
            hunks: [],
          });
          continue;
        }
        let before = "";
        if (typeof edit.previousContent === "string") {
          before = edit.previousContent;
        } else if (!applied) {
          const res = await fetchWorkspaceFile(projectId, edit.path);
          before =
            res.ok && typeof (res as { content?: string }).content === "string"
              ? String((res as { content?: string }).content)
              : "";
        } else {
          // Applied without snapshot — show new file as full add from content.
          before = "";
        }
        rows.push(buildPreview(edit, before));
      }
      if (!cancelled) {
        setPreviews(rows);
        setExpanded(Object.fromEntries(rows.map((r) => [r.path, true])));
        setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, editKey, edits, applied]);

  // Hide no-op cards (+0 −0 identical) — they feel robotic vs Cursor
  const visible = previews.filter(
    (p) => p.kind === "dir" || p.isNew || p.adds > 0 || p.dels > 0,
  );

  if (!edits.length) return null;
  if (!loading && visible.length === 0) return null;

  return (
    <div className={`ide-agent__review${applied ? " is-applied" : ""}`}>
      <header>
        <strong dir="ltr">
          {applied
            ? `Changed ${visible.length || edits.length}`
            : `Review ${visible.length || edits.length}`}
        </strong>
        {!applied ? (
          <>
            <button type="button" onClick={onAcceptAll}>
              قبول الكل
            </button>
            <button type="button" className="is-muted" onClick={onRejectAll}>
              رفض
            </button>
          </>
        ) : null}
      </header>
      {loading ? <p className="ide-agent__diff-loading">جارٍ تجهيز الفروقات…</p> : null}
      <div className="ide-agent__diff-list">
        {(loading ? previews : visible).map((p) => (
          <section key={p.path} className="ide-agent__diff-card">
            <div className="ide-agent__diff-head">
              <button
                type="button"
                className="ide-agent__diff-toggle"
                onClick={() => setExpanded((prev) => ({ ...prev, [p.path]: !prev[p.path] }))}
                aria-expanded={!!expanded[p.path]}
              >
                <span aria-hidden>{expanded[p.path] ? "▾" : "▸"}</span>
              </button>
              {onOpenPath ? (
                <button
                  type="button"
                  className="ide-agent__file-link"
                  dir="ltr"
                  title={`فتح ${p.path}`}
                  onClick={() => onOpenPath(p.path)}
                >
                  {p.path}
                </button>
              ) : (
                <span dir="ltr" title={p.path}>
                  {p.path}
                </span>
              )}
              <em className="ide-agent__diff-stats" dir="ltr">
                {p.kind === "dir"
                  ? "dir"
                  : p.isNew
                    ? `new · +${p.adds}`
                    : `+${p.adds} −${p.dels}`}
              </em>
              {!applied ? (
                <>
                  <button type="button" onClick={() => onAcceptOne?.(p.path)}>
                    قبول
                  </button>
                  <button type="button" className="is-muted" onClick={() => onSkipOne?.(p.path)}>
                    تخطي
                  </button>
                </>
              ) : (
                <span className="ide-agent__diff-applied" aria-hidden>
                  ✓
                </span>
              )}
            </div>
            {expanded[p.path] && p.kind !== "dir" ? (
              <div className="ide-agent__diff-body" dir="ltr">
                {p.hunks.length ? (
                  p.hunks.map((h, hi) => (
                    <div key={`${p.path}-h${hi}`} className="ide-agent__diff-hunk">
                      <div className="ide-agent__diff-hunk-meta">
                        @@ -{h.startOld},{h.lines.filter((l) => l.type !== "add").length} +
                        {h.startNew},{h.lines.filter((l) => l.type !== "del").length} @@
                      </div>
                      {h.lines.map((line, li) => (
                        <div
                          key={`${p.path}-h${hi}-l${li}`}
                          className={`ide-agent__diff-line is-${line.type}`}
                        >
                          <span className="ide-agent__diff-gutter">{line.oldNo ?? ""}</span>
                          <span className="ide-agent__diff-gutter">{line.newNo ?? ""}</span>
                          <span className="ide-agent__diff-mark">
                            {line.type === "add" ? "+" : line.type === "del" ? "−" : " "}
                          </span>
                          <code>{line.text || " "}</code>
                        </div>
                      ))}
                    </div>
                  ))
                ) : (
                  <p className="ide-agent__diff-empty">
                    لا تغييرات مرئية — الملف مطابق لما هو مكتوب بالفعل
                  </p>
                )}
              </div>
            ) : null}
          </section>
        ))}
      </div>
    </div>
  );
}
