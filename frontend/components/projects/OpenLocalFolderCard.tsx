"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { GlassCard } from "@/components/ui/GlassCard";
import { LocalFolderBrowser } from "@/components/projects/LocalFolderBrowser";
import {
  isSpixaDesktop,
  openFolderErrorMessage,
  openLocalProjectFolder,
  pickLocalFolder,
} from "@/lib/openLocalProject";

/**
 * Open Folder: system dialog (desktop) or in-app browser of Desktop/Documents (local API).
 */
export function OpenLocalFolderCard() {
  const router = useRouter();
  const [desktop, setDesktop] = useState(false);
  const [showBrowser, setShowBrowser] = useState(false);
  const [showManual, setShowManual] = useState(false);
  const [path, setPath] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    setDesktop(isSpixaDesktop());
  }, []);

  async function openPath(local: string): Promise<{ ok: boolean; error?: string }> {
    setBusy(true);
    setMsg(null);
    const result = await openLocalProjectFolder(local);
    setBusy(false);
    if (!result.ok) {
      const text = openFolderErrorMessage(result.error);
      setMsg(text);
      return { ok: false, error: text };
    }
    const disk = result.project.workspace_path || result.project.source_uri || local;
    setMsg(`مرتبط بمجلدك على الجهاز: ${disk}`);
    setShowBrowser(false);
    router.push(`/ide?project=${result.project.id}`);
    return { ok: true };
  }

  async function onPick() {
    if (desktop) {
      const chosen = await pickLocalFolder();
      if (chosen) {
        await openPath(chosen);
        return;
      }
    }
    setShowBrowser(true);
  }

  return (
    <>
      <GlassCard title="فتح مشروع من الجهاز">
        <p className="settings-hint" style={{ marginTop: 0 }}>
          اختر مجلدًا ثم اضغط <strong>استخدام هذا المجلد</strong> — بعدها يُفتح في مساحة العمل.
        </p>

        <div className="admin-user__actions">
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void onPick()}>
            {busy ? "جاري الربط…" : "اختيار مجلد من الجهاز…"}
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={busy}
            onClick={() => setShowManual((v) => !v)}
          >
            {showManual ? "إخفاء المسار اليدوي" : "مسار يدوي (متقدم)"}
          </button>
        </div>

        {showManual && (
          <div className="settings-form" style={{ marginTop: 12 }}>
            <label>
              مسار مجلد موجود على جهازك
              <input
                dir="ltr"
                value={path}
                onChange={(e) => setPath(e.target.value)}
                placeholder="C:\Users\...\Desktop\MyProject"
              />
            </label>
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy || !path.trim()}
              onClick={() => void openPath(path)}
            >
              ربط هذا المجلد
            </button>
          </div>
        )}

        {msg && (
          <p className="settings-hint" dir="auto">
            {msg}
          </p>
        )}
      </GlassCard>

      <LocalFolderBrowser
        open={showBrowser}
        onClose={() => setShowBrowser(false)}
        onSelect={(folder) => openPath(folder)}
      />
    </>
  );
}
