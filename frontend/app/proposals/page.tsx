"use client";

import { useCallback, useEffect, useState } from "react";
import { approveProposal, fetchProjects, fetchProposals } from "@/lib/api";
import type { Project, Proposal } from "@/lib/types";
import { GlassCard } from "@/components/ui/GlassCard";
import { PageHeader } from "@/components/ui/PageHeader";
import { SectionLinks } from "@/components/ui/SectionLinks";
import { proposalOriginLabel, proposalStatusLabel } from "@/lib/uiLabels";

export default function ProposalsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    fetchProjects().then((rows) => {
      setProjects(rows);
      if (rows[0]) setProjectId(rows[0].id);
    });
  }, []);

  const reload = useCallback(async (id: string) => {
    if (!id) return;
    setProposals(await fetchProposals(id));
  }, []);

  useEffect(() => {
    reload(projectId);
  }, [projectId, reload]);

  async function onApprove(proposalId: string) {
    setBusy(true);
    setMsg(null);
    const updated = await approveProposal(projectId, proposalId);
    setBusy(false);
    if (!updated) {
      setMsg("تعذّر الاعتماد.");
      return;
    }
    setMsg("تم الاعتماد — انتقل لمركز التنفيذ لتطبيق التغيير على فرع.");
    await reload(projectId);
  }

  return (
    <div>
      <PageHeader
        eyebrow="التسليم"
        title="مركز المقترحات"
        subtitle="اعتماد أو رفض أو طلب مراجعة — لا تنفيذ قبل موافقتك."
      />
      <SectionLinks sectionId="proposals" />

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
      </GlassCard>

      {msg && (
        <GlassCard>
          <p>{msg}</p>
        </GlassCard>
      )}

      <div style={{ display: "grid", gap: "1rem", marginTop: "1rem" }}>
        {proposals.map((p) => (
          <GlassCard key={p.id}>
            <h3 style={{ marginTop: 0 }}>{p.title}</h3>
            <p style={{ opacity: 0.85 }}>{p.proposal}</p>
            <p>
              الحالة: <strong>{proposalStatusLabel(p.status)}</strong>
              {" · "}
              المصدر: {proposalOriginLabel(p.origin)}
            </p>
            {["awaiting_approval", "draft", "revision_requested"].includes(p.status) && (
              <button type="button" disabled={busy} onClick={() => onApprove(p.id)}>
                اعتماد
              </button>
            )}
          </GlassCard>
        ))}
        {!proposals.length && projectId && (
          <GlassCard>
            <p>لا مقترحات بعد. شغّل الفهم أو دردشة الوكيل لإنشاء مسودات.</p>
          </GlassCard>
        )}
      </div>
    </div>
  );
}
