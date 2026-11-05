"use client";

import { useEffect, useState } from "react";
import { fetchFindings, fetchProjects, runDesign, runQuality } from "@/lib/api";
import type { Finding, Project } from "@/lib/types";
import { GlassCard } from "@/components/ui/GlassCard";
import { PageHeader } from "@/components/ui/PageHeader";
import { ThinkingStream } from "@/components/brain/ThinkingStream";
import { useAgentLive } from "@/hooks/useAgentLive";

export default function AnalysisPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [findings, setFindings] = useState<Finding[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [last, setLast] = useState<Record<string, unknown> | null>(null);
  const { thinkEvents, events } = useAgentLive(projectId || undefined);

  useEffect(() => {
    fetchProjects().then((rows) => {
      setProjects(rows);
      if (rows[0]) setProjectId(rows[0].id);
    });
  }, []);

  useEffect(() => {
    if (!projectId) return;
    fetchFindings(projectId).then(setFindings);
  }, [projectId, last]);

  async function onQuality() {
    if (!projectId || busy) return;
    setBusy("quality");
    const result = await runQuality(projectId, "full");
    setLast(result);
    setBusy(null);
  }

  async function onDesign() {
    if (!projectId || busy) return;
    setBusy("design");
    const result = await runDesign(projectId, "حسّن الاتساق وإمكانية الوصول");
    setLast(result);
    setBusy(null);
  }

  return (
    <div>
      <PageHeader
        eyebrow="مساحة العمل"
        title="التحليل الذكي"
        subtitle="جودة، أمن، وتصميم — نتائج منظمة داخل مساحة العمل دون لمس الأصول."
      />
      <GlassCard>
        <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap", marginTop: 12 }}>
          <button type="button" className="btn btn-primary" disabled={!!busy} onClick={onQuality}>
            {busy === "quality" ? "جاري الفحص…" : "تشغيل محرك الجودة/الأمن"}
          </button>
          <button type="button" className="btn btn-ghost" disabled={!!busy} onClick={onDesign}>
            {busy === "design" ? "جاري التصميم…" : "تشغيل محرك التصميم"}
          </button>
        </div>
      </GlassCard>

      <div className="brain-grid" style={{ marginTop: "1rem" }}>
        <ThinkingStream events={thinkEvents.length ? thinkEvents : events.slice(-12)} />
        <GlassCard title="آخر تشغيل محرك">
          {last ? (
            <pre style={{ whiteSpace: "pre-wrap", direction: "ltr", textAlign: "left", margin: 0 }}>
              {JSON.stringify(last, null, 2)}
            </pre>
          ) : (
            <p className="empty">شغّل محركًا لعرض الناتج هنا.</p>
          )}
        </GlassCard>
      </div>

      <div className="knowledge-list" style={{ marginTop: "1rem" }}>
        {findings.map((f) => (
          <article key={f.id} className="node inference">
            <strong>
              [{f.severity}] {f.title}
            </strong>
            <small>
              {f.kind} · {f.category} · {f.status}
            </small>
            <p>{f.description}</p>
            {f.recommendation && <p style={{ color: "var(--cyan)" }}>{f.recommendation}</p>}
          </article>
        ))}
        {!findings.length && <div className="empty">لا نتائج بعد — شغّل الفهم أو محرك الجودة.</div>}
      </div>
    </div>
  );
}