"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { GlassCard } from "@/components/ui/GlassCard";

type Metric = { value?: number | null; proves?: string; gate?: number; gate_max?: number; n?: number };
type Card = {
  specialty?: string;
  product?: string;
  production_ready?: boolean;
  blockers?: string[];
  metrics?: Record<string, Metric>;
};

export function IntelligenceOpsPanel() {
  const [maturity, setMaturity] = useState<Record<string, unknown> | null>(null);
  const [evolution, setEvolution] = useState<Record<string, unknown> | null>(null);
  const [registry, setRegistry] = useState<Record<string, unknown> | null>(null);
  const [probe, setProbe] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    try {
      const [m, e, r] = await Promise.all([
        fetch(`${API_URL}/system/intelligence/maturity`, { cache: "no-store" }),
        fetch(`${API_URL}/system/intelligence/evolution`, { cache: "no-store" }),
        fetch(`${API_URL}/system/intelligence/ownership-registry`, { cache: "no-store" }),
      ]);
      if (m.ok) setMaturity(await m.json());
      if (e.ok) setEvolution(await e.json());
      if (r.ok) setRegistry(await r.json());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function runIndependence() {
    setBusy(true);
    try {
      const res = await fetch(`${API_URL}/system/intelligence/independence/probe`, { method: "POST" });
      setProbe(await res.json());
    } catch {
      setProbe({ error: "network" });
    }
    setBusy(false);
  }

  const cards = (maturity?.specialties || []) as Card[];
  const evo = (evolution?.specialties || []) as Record<string, unknown>[];

  return (
    <div id="intelligence-ops" className="page-grid" style={{ gap: "1rem" }}>
      <GlassCard title="نضج التخصصات — بوابات جودة">
        <p style={{ marginTop: 0, color: "var(--muted)" }}>
          {(maturity?.doctrine_ar as string) ||
            "لا نعتمد عدد الأمثلة أو الـAdapters — الإنتاج بعد بوابات الجودة فقط."}
        </p>
        <ul className="rapid-layers">
          {cards.map((c) => (
            <li key={String(c.specialty)}>
              <strong>
                {c.product} · {c.production_ready ? "جاهز للإنتاج" : "محظور للإنتاج"}
              </strong>
              <span>
                {Object.entries(c.metrics || {})
                  .map(([k, v]) => `${k}=${v?.value ?? "—"}`)
                  .join(" · ")}
              </span>
              {!!c.blockers?.length && (
                <em style={{ display: "block", color: "var(--muted)", fontSize: "0.78rem" }}>
                  موانع: {c.blockers.join(", ")}
                </em>
              )}
            </li>
          ))}
        </ul>
      </GlassCard>

      <GlassCard title="سجل ملكية النماذج">
        <p style={{ marginTop: 0, color: "var(--muted)" }}>
          {(registry?.name_ar as string) || "Model Ownership Registry"}
        </p>
        <ul className="rapid-layers">
          {((registry?.fields as string[]) || []).map((f) => (
            <li key={f}>
              <strong dir="ltr">{f}</strong>
            </li>
          ))}
        </ul>
      </GlassCard>

      <GlassCard title="وضع استقلال النماذج">
        <p style={{ marginTop: 0, color: "var(--muted)" }}>
          يعطّل المعلّمين الخارجيين في جلسة الفحص ويختبر المسارات الأساسية فعليًا.
        </p>
        <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void runIndependence()}>
          تشغيل فحص الاستقلال
        </button>
        {probe ? (
          <pre
            style={{
              marginTop: 12,
              maxHeight: 220,
              overflow: "auto",
              fontSize: "0.75rem",
              direction: "ltr",
            }}
          >
            {JSON.stringify(
              {
                ok: probe.ok,
                passed: probe.passed,
                total: probe.total,
                failed: probe.failed,
              },
              null,
              2
            )}
          </pre>
        ) : null}
      </GlassCard>

      <GlassCard title="لوحة تطور الذكاء">
        <p style={{ marginTop: 0, color: "var(--muted)" }}>
          {(evolution?.doctrine_ar as string) || "تحسن / تراجع / مقارنة عبر الإصدارات"}
        </p>
        <ul className="rapid-layers">
          {evo.map((row) => (
            <li key={String(row.specialty)}>
              <strong>
                {String(row.product)} · versions {String(row.ownership_versions ?? 0)}
              </strong>
              <span dir="ltr">
                vs_prev Δ {String((row.vs_previous as { delta_student?: number })?.delta_student ?? "—")} ·
                student{" "}
                {String((row.vs_teacher as { student?: number })?.student ?? "—")} / teacher{" "}
                {String((row.vs_teacher as { teacher?: number })?.teacher ?? "—")}
              </span>
            </li>
          ))}
        </ul>
      </GlassCard>
    </div>
  );
}
