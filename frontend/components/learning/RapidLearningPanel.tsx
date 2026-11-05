"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { GlassCard } from "@/components/ui/GlassCard";

type Layer = {
  id?: number;
  title_ar?: string;
  title_en?: string;
  role?: string;
};

export function RapidLearningPanel() {
  const [bp, setBp] = useState<Record<string, unknown> | null>(null);
  const [out, setOut] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/system/learning/rapid`, { cache: "no-store" });
      if (res.ok) setBp(await res.json());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function run(path: string, body?: Record<string, unknown>) {
    setBusy(true);
    try {
      const res = await fetch(`${API_URL}${path}`, {
        method: "POST",
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      setOut(await res.json());
      await reload();
    } catch {
      setOut({ error: "network" });
    }
    setBusy(false);
  }

  const layers = (bp?.layers || []) as Layer[];
  const teachers = ((bp?.multi_teacher as { roster?: Record<string, unknown>[] }) || {}).roster || [];
  const domains =
    ((bp?.competitive_lab as { domains?: { ar?: string; measure?: string }[] }) || {}).domains || [];

  return (
    <div id="rapid-learning" className="page-grid" style={{ gap: "1rem" }}>
      <GlassCard title="منظومة التعلم السريع — 7 طبقات">
        <p style={{ marginTop: 0, color: "var(--muted)" }}>
          {(bp?.doctrine as string) || "Internal Intelligence First"} — المعلّمون الخارجيون يولّدون
          الاستقلال الداخلي عبر Distillation.
        </p>
        <ol className="rapid-layers">
          {layers.map((l) => (
            <li key={String(l.id)}>
              <strong>
                {l.id}. {l.title_ar}
              </strong>
              <span>{l.role}</span>
            </li>
          ))}
        </ol>
        <div className="admin-user__actions" style={{ marginTop: 12 }}>
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy}
            onClick={() => void run("/system/learning/rapid/cycle")}
          >
            تشغيل الدورة المستمرة
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={busy}
            onClick={() => void run("/system/learning/rapid/competitive")}
          >
            مختبر المنافسة
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={busy}
            onClick={() =>
              void run("/system/learning/lab/multi-agent", {
                task: "lab_review_pass",
                artifacts: {
                  coder: "Applied isolated patch for edge-case handling in add().",
                  reviewer:
                    "Found off-by-one in loop bound; verified fix returns correct sum for empty inputs.",
                  security: "No injection or secret-leak risk in the candidate patch.",
                  tester: "Unit tests for add() empty and negative cases passed in sandbox.",
                  architect: "Change stays local; no new coupling across modules.",
                  tests_ok: true,
                  force_promote: false,
                  reviewer_severity: "verified_fix",
                },
              })
            }
          >
            Multi-Agent Lab
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={busy}
            onClick={() =>
              void run("/system/learning/lab/execution-verified", {
                patch_summary: "execution_lab_demo: isolated patch + tests",
                tests_ok: true,
                sandbox_ok: true,
                repair_notes: "def add(a, b):\n    return a + b\n",
                promote: true,
              })
            }
          >
            تعلّم من التنفيذ
          </button>
        </div>
      </GlassCard>

      <GlassCard title="معلّمون خارجيون متعددون">
        <ul className="rapid-layers">
          {teachers.map((t) => (
            <li key={String(t.id)}>
              <strong>{String(t.label)}</strong>
              <span dir="ltr">
                {String(t.model || "—")} {t.configured ? "✓" : "(غير مضبوط)"}
              </span>
              <em style={{ display: "block", color: "var(--muted)", fontSize: "0.78rem" }}>
                {String(t.license_note || "")}
              </em>
            </li>
          ))}
        </ul>
      </GlassCard>

      <GlassCard title="مختبر تنافسي — مجالات القياس">
        <ul className="rapid-layers">
          {domains.map((d, i) => (
            <li key={i}>
              <strong>{d.ar}</strong>
              <span>{d.measure}</span>
            </li>
          ))}
        </ul>
      </GlassCard>

      {out ? (
        <GlassCard title="آخر نتيجة">
          <pre
            style={{
              margin: 0,
              maxHeight: 280,
              overflow: "auto",
              fontSize: "0.75rem",
              direction: "ltr",
            }}
          >
            {JSON.stringify(out, null, 2)}
          </pre>
        </GlassCard>
      ) : null}
    </div>
  );
}
