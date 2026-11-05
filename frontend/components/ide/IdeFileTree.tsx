"use client";

import { useEffect, useMemo, useState } from "react";

export type TreeNodeData = {
  name: string;
  path: string;
  type: "file" | "dir";
  children?: TreeNodeData[];
};

const MUTED_DIRS = new Set([
  ".git",
  ".pytest_cache",
  "__pycache__",
  "node_modules",
  ".venv",
  "venv",
  ".next",
  "dist",
  "build",
  ".tox",
  ".mypy_cache",
  ".ruff_cache",
  ".idea",
  ".vscode",
  "coverage",
  ".turbo",
]);

function sortNodes(nodes: TreeNodeData[]): TreeNodeData[] {
  return [...nodes].sort((a, b) => {
    if (a.type !== b.type) return a.type === "dir" ? -1 : 1;
    return a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
  });
}

type FileKind =
  | "folder"
  | "folder-open"
  | "ts"
  | "js"
  | "py"
  | "rs"
  | "go"
  | "json"
  | "md"
  | "css"
  | "html"
  | "yml"
  | "toml"
  | "sql"
  | "sh"
  | "img"
  | "lock"
  | "env"
  | "git"
  | "docker"
  | "cfg"
  | "file";

function fileKind(name: string): FileKind {
  const lower = name.toLowerCase();
  if (lower === "dockerfile" || lower.startsWith("dockerfile.")) return "docker";
  if (lower === "readme.md" || lower === "readme") return "md";
  if (lower === ".gitignore" || lower === ".gitattributes" || lower === ".gitmodules") return "git";
  if (lower.startsWith(".env")) return "env";
  if (lower.endsWith(".lock") || lower === "package-lock.json" || lower === "pnpm-lock.yaml") return "lock";
  if (lower === "tsconfig.json" || lower === "jsconfig.json" || lower === "pyproject.toml") return "cfg";
  const ext = lower.includes(".") ? lower.split(".").pop() || "" : "";
  const map: Record<string, FileKind> = {
    ts: "ts",
    tsx: "ts",
    mts: "ts",
    cts: "ts",
    js: "js",
    jsx: "js",
    mjs: "js",
    cjs: "js",
    py: "py",
    pyi: "py",
    rs: "rs",
    go: "go",
    json: "json",
    md: "md",
    mdx: "md",
    css: "css",
    scss: "css",
    sass: "css",
    less: "css",
    html: "html",
    htm: "html",
    yml: "yml",
    yaml: "yml",
    toml: "toml",
    ini: "cfg",
    cfg: "cfg",
    conf: "cfg",
    sql: "sql",
    sh: "sh",
    bash: "sh",
    zsh: "sh",
    ps1: "sh",
    bat: "sh",
    cmd: "sh",
    svg: "img",
    png: "img",
    jpg: "img",
    jpeg: "img",
    gif: "img",
    webp: "img",
    ico: "img",
  };
  return map[ext] || "file";
}

function KindIcon({ kind }: { kind: FileKind }) {
  if (kind === "folder" || kind === "folder-open") {
    return (
      <svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
        {kind === "folder-open" ? (
          <path d="M1.75 3.5A1.25 1.25 0 0 1 3 2.25h3.2l1.1 1.25H13a1.25 1.25 0 0 1 1.25 1.25v.75H2.9l-.9 5.85A1.25 1.25 0 0 1 3.25 12.5H13.6a1 1 0 0 0 .98-.8l1.1-5.2A1.25 1.25 0 0 0 14.45 5H14.25V4.75A1.25 1.25 0 0 0 13 3.5H7.55L6.45 2.25H3A1.25 1.25 0 0 0 1.75 3.5z" />
        ) : (
          <path d="M1.75 3.5A1.25 1.25 0 0 1 3 2.25h3.15L7.25 3.5H13A1.25 1.25 0 0 1 14.25 4.75v7A1.25 1.25 0 0 1 13 13H3A1.25 1.25 0 0 1 1.75 11.75z" />
        )}
      </svg>
    );
  }

  const badge: Partial<Record<FileKind, string>> = {
    ts: "TS",
    js: "JS",
    py: "PY",
    rs: "RS",
    go: "GO",
    json: "{}",
    md: "MD",
    css: "#",
    html: "<>",
    yml: "Y",
    toml: "T",
    sql: "Q",
    sh: ">_",
    docker: "D",
    env: "*",
    git: "G",
    lock: "L",
    cfg: "C",
    img: "▣",
  };

  const label = badge[kind];
  if (label) {
    return <span className="ide-tree__badge">{label}</span>;
  }

  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
      <path d="M3.25 1.5h5.6L13 5.65v8.1A1.25 1.25 0 0 1 11.75 15h-8.5A1.25 1.25 0 0 1 2 13.75v-11A1.25 1.25 0 0 1 3.25 1.5z" opacity="0.55" />
      <path d="M8.85 1.65v3.7H12.5" fill="none" stroke="currentColor" strokeWidth="1.15" />
    </svg>
  );
}

function filterTree(nodes: TreeNodeData[], q: string): TreeNodeData[] {
  if (!q) return nodes;
  const out: TreeNodeData[] = [];
  for (const n of nodes) {
    if (n.type === "dir") {
      const kids = filterTree(n.children || [], q);
      if (kids.length || n.name.toLowerCase().includes(q)) {
        out.push({ ...n, children: kids.length ? kids : n.children });
      }
    } else if (n.name.toLowerCase().includes(q) || n.path.toLowerCase().includes(q)) {
      out.push(n);
    }
  }
  return out;
}

function TreeNode({
  node,
  depth,
  active,
  onOpen,
  forceOpen,
}: {
  node: TreeNodeData;
  depth: number;
  active: string | null;
  onOpen: (path: string) => void;
  forceOpen: boolean;
}) {
  const muted = node.type === "dir" && MUTED_DIRS.has(node.name);
  const [open, setOpen] = useState(depth < 1 && !muted);
  const isDir = node.type === "dir";
  const expanded = isDir && (forceOpen || open);
  const kind: FileKind = isDir ? (expanded ? "folder-open" : "folder") : fileKind(node.name);
  const kids = useMemo(() => sortNodes(node.children || []), [node.children]);

  useEffect(() => {
    if (forceOpen && isDir) setOpen(true);
  }, [forceOpen, isDir]);

  return (
    <div className={`ide-tree__node ${muted ? "is-muted" : ""}`} role="treeitem" aria-expanded={isDir ? expanded : undefined}>
      <button
        type="button"
        className={`ide-tree__row ${!isDir && active === node.path ? "is-active" : ""} ${isDir ? "is-dir" : "is-file"}`}
        style={{ ["--depth" as string]: String(depth) }}
        title={node.path}
        onClick={() => {
          if (isDir) setOpen((v) => !v);
          else onOpen(node.path);
        }}
      >
        <span className={`ide-tree__chev ${isDir ? (expanded ? "is-open" : "") : "is-leaf"}`} aria-hidden>
          {isDir ? (
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <path d="M3.2 1.8L7 5L3.2 8.2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          ) : null}
        </span>
        <span className={`ide-tree__icon is-${kind}`} aria-hidden>
          <KindIcon kind={kind} />
        </span>
        <span className="ide-tree__label">{node.name}</span>
      </button>
      {isDir && expanded ? (
        <div className="ide-tree__children" role="group">
          {kids.map((child) => (
            <TreeNode
              key={child.path}
              node={child}
              depth={depth + 1}
              active={active}
              onOpen={onOpen}
              forceOpen={forceOpen}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function IdeFileTree({
  tree,
  active,
  onOpen,
  emptyHint,
}: {
  tree: TreeNodeData[];
  active: string | null;
  onOpen: (path: string) => void;
  emptyHint?: string;
}) {
  const [query, setQuery] = useState("");
  const roots = useMemo(() => sortNodes(tree), [tree]);
  const q = query.trim().toLowerCase();
  const visible = useMemo(() => filterTree(roots, q), [roots, q]);
  const forceOpen = q.length > 0;

  const matchCount = useMemo(() => {
    if (!q) return 0;
    let n = 0;
    const walk = (nodes: TreeNodeData[]) => {
      for (const node of nodes) {
        if (node.type === "file") n += 1;
        else walk(node.children || []);
      }
    };
    walk(visible);
    return n;
  }, [visible, q]);

  if (!roots.length) {
    return (
      <div className="ide-tree-empty">
        <div className="ide-tree-empty__icon" aria-hidden>
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
            <path
              d="M3 7.5A2.5 2.5 0 0 1 5.5 5h4l1.5 2H18.5A2.5 2.5 0 0 1 21 9.5v7A2.5 2.5 0 0 1 18.5 19h-13A2.5 2.5 0 0 1 3 16.5v-9z"
              stroke="currentColor"
              strokeWidth="1.4"
            />
          </svg>
        </div>
        <p>{emptyHint || "لا ملفات بعد."}</p>
      </div>
    );
  }

  return (
    <div className="ide-tree-shell">
      <div className="ide-tree-filter">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
          <circle cx="5.2" cy="5.2" r="3.4" stroke="currentColor" strokeWidth="1.3" />
          <path d="M7.7 7.7L10.2 10.2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
        </svg>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="تصفية الملفات…"
          dir="auto"
          aria-label="تصفية شجرة الملفات"
        />
        {q ? <span className="ide-tree-filter__count">{matchCount}</span> : null}
      </div>
      <div className="ide-tree" dir="ltr" role="tree">
        {visible.length ? (
          visible.map((node) => (
            <TreeNode key={node.path} node={node} depth={0} active={active} onOpen={onOpen} forceOpen={forceOpen} />
          ))
        ) : (
          <p className="ide-tree__no-match">لا نتائج لـ «{query}»</p>
        )}
      </div>
    </div>
  );
}
