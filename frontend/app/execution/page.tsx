"use client";

import { useCallback, useEffect, useState } from "react";
import {
  confirmDeploy,
  executeProposal,
  fetchProjects,
  fetchProposals,
  mergeProposal,
  planDeploy,
  runEvolution,
} from "@/lib/api";
import type { ExecutionResult, Project, Proposal } from "@/lib/types";
import { GlassCard } from "@/components/ui/GlassCard";
import { PageHeader } from "@/components/ui/PageHeader";
import { SectionLinks } from "@/components/ui/SectionLinks";
import { proposalStatusLabel } from "@/lib/uiLabels";

export default function ExecutionPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [last, setLast] = useState<ExecutionResult | Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchProjects().then((rows) => {
      setProjects(rows);
      if (rows[0]) setProjectId(rows[0].id);
    });
  }, []);

  const reload = useCallback(async (id: string) => {
    if (!id) return;
    const rows = await fetchProposals(id);
    setProposals(
      rows.filter((p) =>
        ["approved", "awaiting_merge", "executing", "merged", "awaiting_approval"].includes(
          p.status,
        ),
      ),
    );
  }, []);

  useEffect(() => {
    reload(projectId);
  }, [projectId, reload]);

  async function onExecute(proposalId: string) {
    setBusy(true);
    setError(null);
    const result = await executeProposal(projectId, proposalId);
    setBusy(false);
    if (!result) {
      setError("فشل التنفيذ — تأكد أن المقترح معتمد.");
      return;
    }
    setLast(result);
    await reload(projectId);
  }

  async function onMerge(proposalId: string) {
    setBusy(true);
    setError(null);
    const result = await mergeProposal(projectId, proposalId);
    setBusy(false);
    if (!result) {
      setError("فشل الدمج — يجب أن يكون المقترح بانتظار الدمج مع موافقة بشرية.");
      return;
    }
    setLast(result);
    await reload(projectId);
  }

  async function onPlanDeploy() {
    if (!projectId || busy) return;
    setBusy(true);
    setError(null);
    const result = await planDeploy(projectId, "staging");
    setBusy(false);
    if (!result) {
      setError("تعذّر تخطيط النشر.");
      return;
    }
    setLast(result);
    await reload(projectId);
  }

  async function onConfirmDeploy() {
    if (!projectId || busy) return;
    setBusy(true);
    setError(null);
    const result = await confirmDeploy(projectId, "staging");
    setBusy(false);
    if (!result) {
      setError("تعذّر تأكيد النشر.");
      return;
    }
    setLast(result);
  }

  async function onEvolve() {
    if (!projectId || busy) return;
    setBusy(true);
    setError(null);
    const result = await runEvolution(projectId);
    setBusy(false);
    if (!result) {
      setError("تعذّرت دورة التطور.");
      return;
    }
    setLast(result);
    await reload(projectId);
  }

  return (
    <div>
      <PageHeader
        eyebrow="التسليم"
        title="مركز التنفيذ"
        subtitle="تنفيذ على فرع معزول ثم دمج يدوي صريح."
      />
      <SectionLinks sectionId="execution" />

      <GlassCard>
        <label htmlFor="project">المشروع</label>
        <select
          id="project"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
          disabled={!projects.length}
        >
          {!projects.length && <option value="">لا مشاريع بعد</option>}
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap", marginTop: 12 }}>
          <button type="button" className="btn btn-primary" disabled={busy || !projectId} onClick={onEvolve}>
            دورة تطور (بدون تنفيذ)
          </button>
          <button type="button" className="btn btn-ghost" disabled={busy || !projectId} onClick={onPlanDeploy}>
            خطة نشر تجريبي
          </button>
          <button type="button" className="btn btn-ghost" disabled={busy || !projectId} onClick={onConfirmDeploy}>
            تأكيد نشر (محاكاة)
          </button>
        </div>
      </GlassCard>

      {error && (
        <GlassCard>
          <p>{error}</p>
        </GlassCard>
      )}

      <div style={{ display: "grid", gap: "1rem", marginTop: "1rem" }}>
        {proposals.map((p) => (
          <GlassCard key={p.id}>
            <h3 style={{ marginTop: 0 }}>{p.title}</h3>
            <p style={{ opacity: 0.8 }}>{p.problem}</p>
            <p>
              الحالة: <strong>{proposalStatusLabel(p.status)}</strong>
              {" · "}
              الأولوية: {p.priority}
            </p>
            <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
              {p.status === "approved" && (
                <button type="button" disabled={busy} onClick={() => onExecute(p.id)}>
                  تنفيذ على فرع
                </button>
              )}
              {p.status === "awaiting_merge" && (
                <button type="button" disabled={busy} onClick={() => onMerge(p.id)}>
                  اعتماد الدمج
                </button>
              )}
            </div>
          </GlassCard>
        ))}
        {!proposals.length && projectId && (
          <GlassCard>
            <p>لا مقترحات جاهزة. شغّل دورة التطور أو اعتمد من مركز المقترحات.</p>
          </GlassCard>
        )}
      </div>

      {last && (
        <div style={{ marginTop: "1.25rem" }}>
          <GlassCard>
            <h3 style={{ marginTop: 0 }}>آخر نتيجة</h3>
            <pre style={{ whiteSpace: "pre-wrap", direction: "ltr", textAlign: "left" }}>
              {JSON.stringify(last, null, 2)}
            </pre>
          </GlassCard>
        </div>
      )}
    </div>
  );
}
