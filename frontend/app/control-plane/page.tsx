"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { evolveFleet, fetchAutopilot, fetchFleet, runAutopilot } from "@/lib/api";
import { AutopilotToggle } from "@/components/shell/AutopilotToggle";
import { GlassCard } from "@/components/ui/GlassCard";
import { useAutopilot } from "@/hooks/useAutopilot";

type FleetCard = {
  id: string;
  name: string;
  slug: string;
  status: string;
  isolation_namespace: string;
  understanding_progress: number;
  awaiting_approval: number;
  open_findings: number;
  last_evolution_at: string | null;
  href: string;
};

export default function ControlPlanePage() {
  const [fleet, setFleet] = useState<Record<string, unknown> | null>(null);
  const [autopilot, setAutopilot] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [batch, setBatch] = useState<Record<string, unknown> | null>(null);
  const [autoOut, setAutoOut] = useState<Record<string, unknown> | null>(null);
  const [notifyEmail, setNotifyEmail] = useState("");
  const auto = useAutopilot();
  const { refresh: refreshAuto, setEnabled, enabled, busy: autoBusy, lastRun, doctrine } = auto;

  const reload = useCallback(async () => {
    setFleet(await fetchFleet());
    setAutopilot(await fetchAutopilot());
    await refreshAuto();
  }, [refreshAuto]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function onEvolveAll() {
    setBusy(true);
    const result = await evolveFleet(10);
    setBatch(result);
    setBusy(false);
    await reload();
  }

  async function onRunAuto() {
    setBusy(true);
    setAutoOut(await runAutopilot(notifyEmail || undefined));
    setBusy(false);
    await reload();
  }

  const totals = (fleet?.totals || {}) as Record<string, unknown>;
  const projects = (fleet?.projects || []) as FleetCard[];
  const autoStatus = (autopilot?.autopilot || {}) as Record<string, unknown>;
  const experience = (autopilot?.experience || {}) as Record<string, unknown>;

  return (
    <div>
      <header className="page-head">
        <h1>لوحة الأسطول</h1>
        <p>
          تحكم متعدد المشاريع مع عزل صارم — لا ذاكرة مشتركة، ودورات التطور تُنفَّذ مشروعًا تلو الآخر.
        </p>
      </header>

      <GlassCard title="مساعد الطيار">
        <p style={{ marginTop: 0 }}>
          المسمّى الرسمي: <strong>مساعد الطيار</strong>. الزر في الشريط العلوي يبدّل فوراً:{" "}
          <strong>مساعد الطيار · يعمل</strong> = الوكيل يدير المشاريع ويقترح تحسينات ومخاطر على نسخ
          تجريبية؛ <strong>مساعد الطيار · متوقف</strong> = أنت تعطي الأوامر بنفسك. لا يُلمس الأصل قبل
          موافقتك.
        </p>
        <div style={{ margin: "12px 0" }}>
          <AutopilotToggle />
        </div>
        <div className="fleet-kpis">
          <div>
            <span>الوضع</span>
            <strong>
              {enabled
                ? "مساعد الطيار · يعمل وحده"
                : "مساعد الطيار · متوقف (أوامرك)"}
            </strong>
          </div>
          <div>
            <span>تجارب مسجّلة</span>
            <strong>{String(experience.total ?? 0)}</strong>
          </div>
          <div>
            <span>آخر دورة</span>
            <strong style={{ fontSize: "0.75rem" }}>
              {String(autoStatus.last_run || lastRun || "—")}
            </strong>
          </div>
        </div>
        <label style={{ display: "block", marginTop: 12 }}>
          بريد التنبيه (اختياري)
          <input
            value={notifyEmail}
            onChange={(e) => setNotifyEmail(e.target.value)}
            placeholder="you@example.com"
            dir="ltr"
            style={{ width: "100%", marginTop: 4 }}
          />
        </label>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy || autoBusy}
            onClick={() => void setEnabled(true, notifyEmail || undefined)}
          >
            تشغيل مساعد الطيار
          </button>
          <button type="button" className="btn btn-ghost" disabled={busy} onClick={onRunAuto}>
            دورة مساعد الطيار الآن
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={busy || autoBusy}
            onClick={() => void setEnabled(false)}
          >
            إيقاف مساعد الطيار
          </button>
        </div>
        <p className="settings-hint" style={{ marginBottom: 0 }}>
          {String(autoStatus.doctrine || doctrine || "")}
        </p>
        {autoOut && (
          <pre
            style={{
              marginTop: 12,
              whiteSpace: "pre-wrap",
              direction: "ltr",
              textAlign: "left",
              fontSize: "0.72rem",
              maxHeight: 220,
              overflow: "auto",
            }}
          >
            {JSON.stringify(autoOut, null, 2)}
          </pre>
        )}
      </GlassCard>

      <GlassCard>
        <div className="fleet-kpis">
          <div>
            <span>المشاريع</span>
            <strong>{String(totals.projects ?? 0)}</strong>
          </div>
          <div>
            <span>بانتظار قرار</span>
            <strong>{String(totals.awaiting_approval ?? 0)}</strong>
          </div>
          <div>
            <span>العزل</span>
            <strong style={{ fontSize: "0.85rem" }}>namespace / workspace</strong>
          </div>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          style={{ marginTop: 12 }}
          disabled={busy}
          onClick={onEvolveAll}
        >
          {busy ? "جاري دورات الأسطول…" : "تشغيل تطور للأسطول (متسلسل)"}
        </button>
        <p style={{ color: "var(--muted)", fontSize: "0.8rem", marginBottom: 0 }}>
          {String(fleet?.isolation_guarantee || "")}
        </p>
      </GlassCard>

      <div className="fleet-grid">
        {projects.map((p) => (
          <GlassCard key={p.id} title={p.name}>
            <p style={{ margin: "0 0 0.5rem", color: "var(--muted)", fontSize: "0.82rem" }}>
              {p.slug} · {p.status}
            </p>
            <p style={{ margin: 0, fontSize: "0.78rem", direction: "ltr", textAlign: "left" }}>
              {p.isolation_namespace}
            </p>
            <ul className="checklist" style={{ marginTop: "0.75rem" }}>
              <li>
                فهم {Math.round((p.understanding_progress || 0) * 100)}%
              </li>
              <li>مقترحات معلّقة: {p.awaiting_approval}</li>
              <li>ملاحظات مفتوحة: {p.open_findings}</li>
              <li>آخر تطور: {p.last_evolution_at || "—"}</li>
            </ul>
            <Link href={p.href} className="btn btn-ghost" style={{ marginTop: 8 }}>
              فتح المشروع
            </Link>
          </GlassCard>
        ))}
        {!projects.length && <div className="empty">لا مشاريع في الأسطول بعد.</div>}
      </div>

      {batch && (
        <GlassCard title="آخر دفعة أسطول">
          <pre style={{ whiteSpace: "pre-wrap", direction: "ltr", textAlign: "left", margin: 0 }}>
            {JSON.stringify(batch, null, 2)}
          </pre>
        </GlassCard>
      )}
    </div>
  );
}
