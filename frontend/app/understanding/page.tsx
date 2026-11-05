"use client";

import { useEffect, useState } from "react";
import { fetchProjects, runUnderstanding } from "@/lib/api";
import type { Project } from "@/lib/types";
import { GlassCard } from "@/components/ui/GlassCard";
import { PageHeader } from "@/components/ui/PageHeader";
import { NeuralNet } from "@/components/brain/NeuralNet";
import { ThinkingStream } from "@/components/brain/ThinkingStream";
import { useAgentLive } from "@/hooks/useAgentLive";

export default function UnderstandingPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [busy, setBusy] = useState(false);
  const { thinkEvents, events, focus, intensity } = useAgentLive(projectId || undefined);

  useEffect(() => {
    fetchProjects().then((rows) => {
      setProjects(rows);
      if (rows[0]) setProjectId(rows[0].id);
    });
  }, []);

  async function start() {
    if (!projectId || busy) return;
    setBusy(true);
    await runUnderstanding(projectId);
    setBusy(false);
  }

  return (
    <div>
      <PageHeader
        eyebrow="مساحة العمل"
        title="فهم المشروع"
        subtitle="تشغيل محرك الفهم متعدد الوكلاء مع بث تفكير حيّ — مساحة عمل معزولة لكل مشروع."
      />
      <GlassCard>
        <label htmlFor="p">المشروع</label>
        <select id="p" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <button type="button" className="btn btn-primary" style={{ marginTop: 12 }} onClick={start} disabled={busy}>
          {busy ? "جاري الفهم…" : "شغّل الفهم الذاتي"}
        </button>
      </GlassCard>
      <div className="brain-grid" style={{ marginTop: "1rem" }}>
        <div className={`brain-hero__viz ${focus.active ? "is-active" : ""}`} style={{ minHeight: 280 }}>
          <NeuralNet active={focus.active || busy} intensity={intensity} />
        </div>
        <ThinkingStream events={thinkEvents.length ? thinkEvents : events.slice(-16)} />
      </div>
    </div>
  );
}
