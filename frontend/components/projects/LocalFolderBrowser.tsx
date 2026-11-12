"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchLocalList,
  fetchLocalRoots,
  type LocalEntry,
  type LocalRoot,
} from "@/lib/localDisk";

type Props = {
  open: boolean;
  onClose: () => void;
  onSelect: (folderPath: string) => void;
};

function formatSize(size?: number): string {
  if (typeof size !== "number" || Number.isNaN(size)) return "";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export function LocalFolderBrowser({ open, onClose, onSelect }: Props) {
  const [roots, setRoots] = useState<LocalRoot[]>([]);
  const [current, setCurrent] = useState("");
  const [parent, setParent] = useState<string | null>(null);
  const [folders, setFolders] = useState<LocalEntry[]>([]);
  const [files, setFiles] = useState<LocalEntry[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [pathInput, setPathInput] = useState("");
  const [filterQ, setFilterQ] = useState("");
  const [showHidden, setShowHidden] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const filterTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadPath = useCallback(async (path: string, opts?: { q?: string; showHidden?: boolean }) => {
    const q = opts?.q ?? filterQ;
    const hidden = opts?.showHidden ?? showHidden;
    setBusy(true);
    setError("");
    const data = await fetchLocalList(path, { showHidden: hidden, q });
    setBusy(false);
    if (!data) {
      setError("تعذّر قراءة المجلد — تأكد أن الـ API يعمل على نفس الجهاز.");
      return;
    }
    setCurrent(data.path);
    setPathInput(data.path);
    setParent(data.parent);
    setFolders(data.folders || []);
    setFiles(data.files || []);
    setSelected(null);
  }, [filterQ, showHidden]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setFilterQ("");
    setSelected(null);
    setError("");
    (async () => {
      const { roots: r } = await fetchLocalRoots();
      if (cancelled) return;
      setRoots(r);
      const start =
        r.find((x) => x.id === "desktop") ||
        r.find((x) => x.id === "desktop_onedrive") ||
        r.find((x) => x.id === "home") ||
        r[0];
      if (start) await loadPath(start.path, { q: "", showHidden: false });
      else setError("لم يُعثر على مجلدات قابلة للتصفح على هذا الجهاز.");
    })();
    return () => {
      cancelled = true;
    };
    // Only re-init when dialog opens
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    return () => {
      if (filterTimer.current) clearTimeout(filterTimer.current);
    };
  }, []);

  function scheduleFilter(nextQ: string) {
    setFilterQ(nextQ);
    if (!current) return;
    if (filterTimer.current) clearTimeout(filterTimer.current);
    filterTimer.current = setTimeout(() => {
      void loadPath(current, { q: nextQ });
    }, 220);
  }

  function goToTypedPath() {
    const target = pathInput.trim();
    if (!target) return;
    void loadPath(target, { q: filterQ });
  }

  if (!open) return null;

  return (
    <div
      className="folder-browser-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="تصفح الجهاز"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="folder-browser"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <header className="folder-browser__head">
          <div>
            <strong>اختر مجلدًا من جهازك</strong>
            <span>تصفّح الأقراص والمجلدات — اضغط مساحة فارغة لإلغاء التحديد</span>
          </div>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            إغلاق
          </button>
        </header>

        <div className="folder-browser__roots">
          {roots.map((r) => (
            <button
              key={r.id}
              type="button"
              className={`folder-browser__root ${current === r.path ? "is-active" : ""}`}
              onClick={() => void loadPath(r.path, { q: filterQ })}
            >
              {r.label_ar || r.label}
            </button>
          ))}
        </div>

        <div className="folder-browser__pathbar">
          <input
            dir="ltr"
            className="folder-browser__path-input"
            value={pathInput}
            onChange={(e) => setPathInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                goToTypedPath();
              }
            }}
            placeholder="C:\\Users\\… أو مسار المجلد"
            aria-label="مسار المجلد"
          />
          <button type="button" className="btn btn-ghost" disabled={busy} onClick={goToTypedPath}>
            انتقال
          </button>
        </div>

        <div className="folder-browser__toolbar">
          <button
            type="button"
            className="btn btn-ghost"
            disabled={!parent || busy}
            onClick={() => parent && void loadPath(parent, { q: filterQ })}
          >
            ↑ أعلى
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={busy || !current}
            onClick={() => void loadPath(current, { q: filterQ })}
          >
            تحديث
          </button>
          <label className="folder-browser__check">
            <input
              type="checkbox"
              checked={showHidden}
              onChange={(e) => {
                const next = e.target.checked;
                setShowHidden(next);
                if (current) void loadPath(current, { showHidden: next, q: filterQ });
              }}
            />
            إظهار المخفي
          </label>
          <input
            dir="ltr"
            className="folder-browser__filter"
            value={filterQ}
            onChange={(e) => scheduleFilter(e.target.value)}
            placeholder="تصفية الاسم…"
            aria-label="تصفية الملفات"
          />
        </div>

        <div
          className="folder-browser__list"
          dir="ltr"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setSelected(null);
          }}
        >
          {busy && <p className="folder-browser__empty">جاري التحميل…</p>}
          {!busy &&
            folders.map((f) => (
              <button
                key={f.path}
                type="button"
                className={`folder-browser__row is-dir ${selected === f.path ? "is-selected" : ""}`}
                onClick={() => setSelected(f.path)}
                onDoubleClick={() => void loadPath(f.path, { q: "" })}
              >
                <span className="folder-browser__icon" aria-hidden>
                  📁
                </span>
                <span className="folder-browser__name">{f.name}</span>
                <span className="folder-browser__meta">
                  {[f.has_git && "git", f.has_package_json && "node", f.has_pyproject && "py"]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
                <span
                  className="folder-browser__open"
                  role="button"
                  tabIndex={0}
                  onClick={(e) => {
                    e.stopPropagation();
                    void loadPath(f.path, { q: "" });
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      e.stopPropagation();
                      void loadPath(f.path, { q: "" });
                    }
                  }}
                >
                  فتح
                </span>
              </button>
            ))}
          {!busy &&
            files.map((f) => (
              <div key={f.path} className="folder-browser__row is-file">
                <span className="folder-browser__icon" aria-hidden>
                  📄
                </span>
                <span className="folder-browser__name">{f.name}</span>
                <span className="folder-browser__meta">{formatSize(f.size)}</span>
              </div>
            ))}
          {!busy && !folders.length && !files.length && (
            <p className="folder-browser__empty">
              {filterQ.trim() ? "لا نتائج للتصفية." : "المجلد فارغ."}
            </p>
          )}
        </div>

        {error ? <p className="folder-browser__error">{error}</p> : null}

        <footer className="folder-browser__foot">
          <p>
            {selected
              ? `المحدد: ${selected}`
              : "اضغط مجلدًا لتحديده، أو مساحة فارغة لإلغاء التحديد. الربط للمجلد فقط."}
          </p>
          <div className="folder-browser__actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>
              إلغاء
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={!selected}
              onClick={() => selected && onSelect(selected)}
            >
              استخدام هذا المجلد
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
