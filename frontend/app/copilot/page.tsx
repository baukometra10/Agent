"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  approveProposal,
  climbOwnershipCoverage,
  executeProposal,
  fetchAutopilot,
  fetchAutopilotReports,
  fetchOwnershipCoverage,
  runAutopilot,
} from "@/lib/api";
import { AutopilotToggle } from "@/components/shell/AutopilotToggle";
import { GlassCard } from "@/components/ui/GlassCard";
import { PageHeader } from "@/components/ui/PageHeader";
import { SectionLinks } from "@/components/ui/SectionLinks";
import { useAutopilot } from "@/hooks/useAutopilot";

export default function CopilotPage() {
  const auto = useAutopilot();
  const [reports, setReports] = useState<Record<string, unknown>[]>([]);
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [coverage, setCoverage] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [runOut, setRunOut] = useState<Record<string, unknown> | null>(null);
  const [actionMsg, setActionMsg] = useState<string>("");

  const { refresh: refreshAuto } = auto;

  const reload = useCallback(async () => {
    setStatus(await fetchAutopilot());
    setReports(await fetchAutopilotReports());
    const cov = await fetchOwnershipCoverage();
    setCoverage((cov?.coverage as Record<string, unknown>) || null);
    await refreshAuto();
  }, [refreshAuto]);

  useEffect(() => {
    void reload();
    const id = window.setInterval(() => void reload(), 15000);
    return () => window.clearInterval(id);
  }, [reload]);

  async function onRun() {
    setBusy(true);
    setRunOut(await runAutopilot());
    setBusy(false);
    await reload();
  }

  async function onApproveAndExecute(projectId: string, proposalId: string) {
    setBusy(true);
    setActionMsg("جارٍ الموافقة…");
    const approved = await approveProposal(projectId, proposalId);
    if (!approved) {
      setActionMsg("فشلت الموافقة — راجع مركز المقترحات.");
      setBusy(false);
      return;
    }
    setActionMsg("موافق · جارٍ التنفيذ على فرع معزول…");
    const exec = await executeProposal(projectId, proposalId);
    setRunOut(exec);
    setActionMsg(
      exec
        ? "تم التنفيذ على فرع معزول — الدمج ما زال بوابتك البشرية."
        : "الموافقة تمت؛ التنفيذ يحتاج مراجعة في مركز التنفيذ.",
    );
    setBusy(false);
    await reload();
  }

  const ap = (status?.autopilot || {}) as Record<string, unknown>;
  const latest = reports[0];
  const projects =
    ((latest?.report as Record<string, unknown> | undefined)?.projects as
      | Record<string, unknown>[]
      | undefined) || [];

  return (
    <div>
      <PageHeader
        eyebrow="تشغيل غير مراقب"
        title="مساعد الطيار"
        subtitle="يعمل وحده على نسخ تجريبية، يبني فروقات واقتراحات، ولا يلمس الأصول قبل موافقتك."
      />
      <SectionLinks sectionId="copilot" />

      <GlassCard title="التشغيل">
        <div style={{ marginBottom: 12 }}>
          <AutopilotToggle />
        </div>
        <div className="fleet-kpis">
          <div>
            <span>الوضع</span>
            <strong>
              {auto.enabled
                ? auto.paused
                  ? "معلّق (عمل يدوي)"
                  : "يعمل · حلقة خلفية"
                : "متوقف"}
            </strong>
          </div>
          <div>
            <span>تغطية داخلية</span>
            <strong>
              {coverage ? `${String(coverage.percent_internal ?? 0)}%` : "—"}
              <small style={{ display: "block", fontWeight: 400, color: "var(--muted)" }}>
                هدف {String(coverage?.percent_target ?? 85)}%
              </small>
            </strong>
          </div>
          <div>
            <span>تكلفة / مهمة ناجحة</span>
            <strong>
              {coverage
                ? `$${Number(coverage.cost_per_successful_task_usd ?? 0).toFixed(5)}`
                : "—"}
            </strong>
          </div>
          <div>
            <span>تخصصات جاهزة</span>
            <strong>
              {coverage
                ? `${String(coverage.specialties_ready ?? 0)}/${String(coverage.specialties_total ?? 6)}`
                : "—"}
            </strong>
          </div>
          <div>
            <span>آخر دورة</span>
            <strong style={{ fontSize: "0.75rem" }}>
              {String(ap.last_run || auto.lastRun || "—")}
            </strong>
          </div>
        </div>
        {coverage?.label_ar ? (
          <p className="settings-hint">{String(coverage.label_ar)}</p>
        ) : null}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy || auto.busy}
            onClick={() => void onRun()}
          >
            {busy ? "جارٍ الدورة…" : "تشغيل دورة تجريبية الآن"}
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={busy}
            onClick={() => {
              setBusy(true);
              void climbOwnershipCoverage({ n: 8 }).then(async (out) => {
                setRunOut(out);
                setBusy(false);
                await reload();
              });
            }}
          >
            رفع تغطية مملوكة
          </button>
        </div>
        <p className="settings-hint">{String(ap.doctrine || auto.doctrine || "")}</p>
      </GlassCard>

      {latest && (
        <GlassCard title={latest.urgent ? "آخر تقرير · عاجل" : "آخر تقرير"}>
          {!!latest.urgent && (
            <p style={{ color: "#f0a0a0", marginTop: 0 }}>تنبيه أمني/مخاطرة عالية — راجع فوراً.</p>
          )}
          <p style={{ marginTop: latest.urgent ? undefined : 0 }}>{String(latest.summary || "")}</p>
          <small style={{ display: "block" }}>
            {latest.generated_at
              ? new Date(String(latest.generated_at)).toLocaleString("ar", {
                  dateStyle: "medium",
                  timeStyle: "short",
                  hour12: false,
                })
              : ""}
          </small>
          {projects.map((p) => (
            <article key={String(p.project_id || p.project_name)} className="node" style={{ marginTop: 12 }}>
              <strong>{String(p.project_name)}</strong>
              <p>{String(p.why || "")}</p>
              {!!(p.experiment as Record<string, unknown> | undefined)?.patch_count && (
                <p>
                  تعديلات تجريبية:{" "}
                  {String((p.experiment as Record<string, unknown>).patch_count)} · أصول ملموسة؟{" "}
                  {String(p.originals_touched)}
                </p>
              )}
              {!!(p.experiment as Record<string, unknown> | undefined)?.combined_diff_preview && (
                <pre
                  style={{
                    whiteSpace: "pre-wrap",
                    direction: "ltr",
                    textAlign: "left",
                    fontSize: "0.72rem",
                    maxHeight: 220,
                    overflow: "auto",
                  }}
                >
                  {String(
                    (p.experiment as Record<string, unknown>).combined_diff_preview,
                  )}
                </pre>
              )}
              {!!(p.proposal as Record<string, unknown> | undefined)?.proposal_id && (
                <p style={{ marginBottom: 8 }}>
                  الموافقة + التنفيذ من هنا ينقل ملفات التجربة إلى فرع معزول فقط — الدمج يبقى يدوياً.
                </p>
              )}
              {!!(p.proposal as Record<string, unknown> | undefined)?.proposal_id && (
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={busy}
                  onClick={() =>
                    void onApproveAndExecute(
                      String(p.project_id),
                      String((p.proposal as Record<string, unknown>).proposal_id),
                    )
                  }
                >
                  موافقة وتنفيذ (فرع معزول)
                </button>
              )}
              {!!(p.proposal as Record<string, unknown> | undefined)?.proposal_id && (
                <Link className="btn btn-ghost" href="/proposals" style={{ marginInlineStart: 8 }}>
                  مركز المقترحات
                </Link>
              )}
              <Link className="btn btn-ghost" href="/execution" style={{ marginInlineStart: 8 }}>
                مركز التنفيذ
              </Link>
            </article>
          ))}
          {actionMsg ? <p className="settings-hint">{actionMsg}</p> : null}
        </GlassCard>
      )}

      <GlassCard title="سجل التقارير">
        <ul className="checklist">
          {reports.map((r) => (
            <li key={String(r.id)}>
              <span className="check">{r.urgent ? "!" : "●"}</span>
              <span>
                {r.urgent ? "عاجل · " : ""}
                {String(r.summary || r.id)}
                <br />
                <small>{String(r.generated_at || "")}</small>
              </span>
            </li>
          ))}
          {!reports.length && <li className="empty">لا تقارير بعد — شغّل دورة الآن.</li>}
        </ul>
        <Link href="/control-plane" className="btn btn-ghost" style={{ marginTop: 8 }}>
          لوحة الأسطول
        </Link>
      </GlassCard>

      {runOut && (
        <GlassCard title="ناتج آخر تشغيل يدوي">
          <pre
            style={{
              whiteSpace: "pre-wrap",
              direction: "ltr",
              textAlign: "left",
              fontSize: "0.72rem",
              maxHeight: 280,
              overflow: "auto",
              margin: 0,
            }}
          >
            {JSON.stringify(runOut, null, 2)}
          </pre>
        </GlassCard>
      )}
    </div>
  );
}
