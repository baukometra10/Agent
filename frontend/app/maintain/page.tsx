"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { GlassCard } from "@/components/ui/GlassCard";
import { PageHeader } from "@/components/ui/PageHeader";

export default function MaintainPage() {
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [out, setOut] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/system/maintain`, { cache: "no-store" });
      if (res.ok) setStatus(await res.json());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function onRun() {
    setBusy(true);
    try {
      const res = await fetch(`${API_URL}/system/maintain/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ climb_if_low: true }),
      });
      if (res.ok) setOut(await res.json());
    } catch {
      /* ignore */
    }
    setBusy(false);
    await reload();
  }

  const readiness = (status?.readiness || {}) as Record<string, unknown>;
  const coverage = (status?.coverage || {}) as Record<string, unknown>;
  const actions = (status?.actions_available || []) as string[];

  return (
    <div>
      <PageHeader
        eyebrow="صيانة ذاتية"
        title="المنظومة تُصلح نفسها"
        subtitle="Spixa يفحص المقاييس، يُنمي المناهج، يُوقف المعلّمين الجاهزين، ويرفع التغطية — دون لمس أصول مشاريعك."
        actions={
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void onRun()}>
            {busy ? "جارٍ الصيانة…" : "تشغيل دورة صيانة الآن"}
          </button>
        }
      />

      <div className="page-grid page-grid--2">
        <GlassCard title="الحالة">
          <div className="fleet-kpis">
            <div>
              <span>تغطية داخلية</span>
              <strong>{String(coverage.percent_internal ?? "—")}%</strong>
            </div>
            <div>
              <span>تخصصات جاهزة</span>
              <strong>
                {String(readiness.specialties_ready ?? 0)}/{String(readiness.specialties_total ?? 6)}
              </strong>
            </div>
            <div>
              <span>متقاعدة</span>
              <strong>{String(readiness.specialties_retired ?? 0)}</strong>
            </div>
          </div>
          <p className="settings-hint">{String(status?.doctrine || "")}</p>
        </GlassCard>

        <GlassCard title="إجراءات متاحة">
          <ul className="maintain-steps">
            {actions.map((a) => (
              <li key={a}>
                <code>{a}</code>
              </li>
            ))}
            {!actions.length && <li>لا إجراءات بعد.</li>}
          </ul>
        </GlassCard>
      </div>

      {out && (
        <div style={{ marginTop: 12 }}>
          <GlassCard title="آخر دورة">
            <pre
              style={{
                margin: 0,
                whiteSpace: "pre-wrap",
                direction: "ltr",
                textAlign: "left",
                fontFamily: "var(--mono)",
                fontSize: "0.75rem",
                maxHeight: 360,
                overflow: "auto",
              }}
            >
              {JSON.stringify(out, null, 2)}
            </pre>
          </GlassCard>
        </div>
      )}
    </div>
  );
}
