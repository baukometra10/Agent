"use client";

import { useEffect, useState } from "react";
import { fetchProjects, fetchRoadmap } from "@/lib/api";
import type { Project, Roadmap } from "@/lib/types";
import { GlassCard } from "@/components/ui/GlassCard";
import { PageHeader } from "@/components/ui/PageHeader";

export default function RoadmapPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null);

  useEffect(() => {
    fetchProjects().then((rows) => {
      setProjects(rows);
      if (rows[0]) setProjectId(rows[0].id);
    });
  }, []);

  useEffect(() => {
    if (!projectId) return;
    fetchRoadmap(projectId).then(setRoadmap);
  }, [projectId]);

  return (
    <div>
      <PageHeader
        eyebrow="مساحة العمل"
        title="خارطة الطريق"
        subtitle="خطة استراتيجية يولّدها الوكيل — التنفيذ يبقى ببوابة بشرية."
      />
      <GlassCard>
        <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </GlassCard>
      {roadmap ? (
        <div style={{ marginTop: "1rem" }}>
        <GlassCard title={`${roadmap.title} (v${roadmap.version})`}>
          <p style={{ color: "var(--muted)" }}>{roadmap.vision}</p>
          <ol className="plan-steps">
            {(roadmap.items || []).map((item) => (
              <li key={item.id} className={item.status === "done" ? "is-done" : ""}>
                <span className="plan-steps__marker" />
                <div className="plan-steps__body">
                  <span>
                    {item.title} · أولوية {item.priority}
                  </span>
                  <em className="plan-pill">{item.status}</em>
                </div>
              </li>
            ))}
          </ol>
        </GlassCard>
        </div>
      ) : (
        <div className="empty">لا خارطة بعد — شغّل الفهم لتوليدها.</div>
      )}
    </div>
  );
}
