"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { GlassCard } from "@/components/ui/GlassCard";

type Engine = {
  id?: number;
  title_ar?: string;
  title_en?: string;
  role?: string;
};

type Release = {
  id: string;
  specialty?: string;
  status?: string;
  eval?: { student_score?: number; teacher_score?: number; beat_or_parity?: boolean };
  note_ar?: string;
};

export function ModelFactoryPanel() {
  const [bp, setBp] = useState<Record<string, unknown> | null>(null);
  const [releases, setReleases] = useState<Release[]>([]);
  const [out, setOut] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    try {
      const [b, r] = await Promise.all([
        fetch(`${API_URL}/system/factory/blueprint`, { cache: "no-store" }),
        fetch(`${API_URL}/system/factory/releases`, { cache: "no-store" }),
      ]);
      if (b.ok) setBp(await b.json());
      if (r.ok) {
        const data = await r.json();
        setReleases((data.releases || []) as Release[]);
      }
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

  const engines = (bp?.engines || []) as Engine[];
  const hard = (bp?.hard_rule || {}) as Record<string, unknown>;
  const pending = releases.filter((r) => r.status === "pending_approval");

  return (
    <div id="model-factory" className="page-grid" style={{ gap: "1rem" }}>
      <GlassCard title="مصنع تطوير النماذج — 5 محركات">
        <p style={{ marginTop: 0, color: "var(--muted)" }}>
          {(bp?.doctrine_ar as string) ||
            "مصنع تحت رقابة — الاقتراح ليس ترقية إنتاج."}
        </p>
        <p style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
          موافقة بشرية مطلوبة: {String(hard.require_human_approval ?? true)} · منع تعديل
          الأوزان تلقائيًا: {String(!(hard.auto_mutate_production_weights ?? false))}
        </p>
        <ol className="rapid-layers">
          {engines.map((e) => (
            <li key={String(e.id)}>
              <strong>
                {e.id}. {e.title_ar}
              </strong>
              <span>{e.role}</span>
            </li>
          ))}
        </ol>
        <div className="admin-user__actions" style={{ marginTop: 12 }}>
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy}
            onClick={() =>
              void run("/system/factory/cycle", {
                specialties: ["coding", "reasoning"],
                run_synthetic: true,
                seed: true,
                train: true,
              })
            }
          >
            تشغيل دورة المصنع
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={busy}
            onClick={() => void run("/system/factory/evaluate", { specialty: "coding" })}
          >
            مختبر التقييم
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={busy}
            onClick={() => void run("/system/factory/synthetic", { specialty: "coding", max_variants: 4 })}
          >
            بيانات تركيبية
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={busy}
            onClick={() => void run("/system/factory/self-improve")}
          >
            اقتراحات تحسين
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy}
            onClick={() =>
              void run("/system/factory/proof/coding", {
                real_train: true,
                approve_if_gates_pass: true,
                max_steps: 20,
                label: "coding_proof_ui",
                approver: "admin",
              })
            }
          >
            إثبات Coding (LoRA + اعتماد)
          </button>
        </div>
      </GlassCard>

      <GlassCard title={`إصدارات معلّقة (${pending.length})`}>
        <p className="settings-hint" style={{ marginTop: 0 }}>
          اجتياز التقييم + عدم التراجع عن آخر إصدار معتمد ينشئ اقتراحًا فقط. الموافقة البشرية
          هي التي تفعّل الإنتاج (`promote/all` لم يعد يشحن تلقائيًا).
        </p>
        <ul className="rapid-layers">
          {!pending.length && <li className="empty">لا اقتراحات معلّقة.</li>}
          {pending.map((r) => (
            <li key={r.id}>
              <strong dir="ltr">
                {r.specialty} · student {r.eval?.student_score ?? "—"} / teacher{" "}
                {r.eval?.teacher_score ?? "—"}
              </strong>
              <span>{r.note_ar || r.id}</span>
              <div className="admin-user__actions" style={{ marginTop: 8 }}>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={busy}
                  onClick={() =>
                    void run(`/system/factory/releases/${r.id}/approve`, {
                      approver: "admin",
                      force: false,
                    })
                  }
                >
                  موافقة إنتاج (بوابات النضج)
                </button>
                <button
                  type="button"
                  className="btn btn-ghost"
                  disabled={busy}
                  onClick={() =>
                    void run(`/system/factory/releases/${r.id}/approve`, {
                      approver: "admin",
                      force: true,
                    })
                  }
                >
                  اعتماد تجريبي (force)
                </button>
                <button
                  type="button"
                  className="btn btn-ghost"
                  disabled={busy}
                  onClick={() =>
                    void run(`/system/factory/releases/${r.id}/reject`, {
                      reason: "manual_reject",
                      rejector: "admin",
                    })
                  }
                >
                  رفض
                </button>
              </div>
            </li>
          ))}
        </ul>
      </GlassCard>

      {out ? (
        <GlassCard title="آخر نتيجة مصنع">
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
