"use client";

import { useCallback, useEffect, useState } from "react";
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

export function LocalFolderBrowser({ open, onClose, onSelect }: Props) {
  const [roots, setRoots] = useState<LocalRoot[]>([]);
  const [current, setCurrent] = useState("");
  const [parent, setParent] = useState<string | null>(null);
  const [folders, setFolders] = useState<LocalEntry[]>([]);
  const [files, setFiles] = useState<LocalEntry[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const loadPath = useCallback(async (path: string) => {
    setBusy(true);
    setError("");
    const data = await fetchLocalList(path);
    setBusy(false);
    if (!data) {
      setError("تعذّر قراءة المجلد — تأكد أن الـ API يعمل على نفس الجهاز.");
      return;
    }
    setCurrent(data.path);
    setParent(data.parent);
    setFolders(data.folders || []);
    setFiles(data.files || []);
    setSelected(data.path);
  }, []);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    (async () => {
      const { roots: r } = await fetchLocalRoots();
      if (cancelled) return;
      setRoots(r);
      const desktop =
        r.find((x) => x.id === "desktop") ||
        r.find((x) => x.id === "desktop_onedrive") ||
        r[0];
      if (desktop) await loadPath(desktop.path);
      else setError("لم يُعثر على سطح المكتب أو المجلد الشخصي على هذا الجهاز.");
    })();
    return () => {
      cancelled = true;
    };
  }, [open, loadPath]);

  if (!open) return null;

  return (
    <div className="folder-browser-backdrop" role="dialog" aria-modal="true" aria-label="تصفح الجهاز">
      <div className="folder-browser">
        <header className="folder-browser__head">
          <div>
            <strong>اختر مجلدًا من جهازك</strong>
            <span dir="ltr">{current || "…"}</span>
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
              onClick={() => void loadPath(r.path)}
            >
              {r.label_ar || r.label}
            </button>
          ))}
        </div>

        <div className="folder-browser__toolbar">
          <button
            type="button"
            className="btn btn-ghost"
            disabled={!parent || busy}
            onClick={() => parent && void loadPath(parent)}
          >
            ↑ أعلى
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={busy || !current}
            onClick={() => void loadPath(current)}
          >
            تحديث
          </button>
        </div>

        <div className="folder-browser__list" dir="ltr">
          {busy && <p className="folder-browser__empty">جاري التحميل…</p>}
          {!busy &&
            folders.map((f) => (
              <button
                key={f.path}
                type="button"
                className={`folder-browser__row is-dir ${selected === f.path ? "is-selected" : ""}`}
                onClick={() => setSelected(f.path)}
                onDoubleClick={() => void loadPath(f.path)}
              >
                <span className="folder-browser__icon">📁</span>
                <span className="folder-browser__name">{f.name}</span>
                <span className="folder-browser__meta">
                  {[f.has_git && "git", f.has_package_json && "node", f.has_pyproject && "py"]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={(e) => {
                    e.stopPropagation();
                    void loadPath(f.path);
                  }}
                >
                  فتح
                </button>
              </button>
            ))}
          {!busy &&
            files.map((f) => (
              <div key={f.path} className="folder-browser__row is-file">
                <span className="folder-browser__icon">📄</span>
                <span className="folder-browser__name">{f.name}</span>
                <span className="folder-browser__meta">
                  {typeof f.size === "number" ? `${Math.round(f.size / 1024)} KB` : ""}
                </span>
              </div>
            ))}
          {!busy && !folders.length && !files.length && (
            <p className="folder-browser__empty">المجلد فارغ.</p>
          )}
        </div>

        {error ? <p className="folder-browser__error">{error}</p> : null}

        <footer className="folder-browser__foot">
          <p>
            اختر مجلد المشروع ثم «استخدام هذا المجلد». الملفات المعروضة للتوضيح — الربط يكون للمجلد.
          </p>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!selected}
            onClick={() => selected && onSelect(selected)}
          >
            استخدام هذا المجلد
          </button>
        </footer>
      </div>
    </div>
  );
}
