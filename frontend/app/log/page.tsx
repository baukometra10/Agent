"use client";

import { useEffect, useState } from "react";
import { fetchProjects, fetchTasks } from "@/lib/api";
import type { AgentTask, Project } from "@/lib/types";
import { GlassCard } from "@/components/ui/GlassCard";
import { PageHeader } from "@/components/ui/PageHeader";
import { ThinkingStream } from "@/components/brain/ThinkingStream";
import { useAgentLive } from "@/hooks/useAgentLive";

export default function LogPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [tasks, setTasks] = useState<AgentTask[]>([]);
  const { events } = useAgentLive(projectId || undefined);

  useEffect(() => {
    fetchProjects().then((rows) => {
      setProjects(rows);
      if (rows[0]) setProjectId(rows[0].id);
    });
  }, []);

  useEffect(() => {
    if (!projectId) return;
    fetchTasks(projectId).then(setTasks);
  }, [projectId]);

  return (
    <div>
      <PageHeader
        eyebrow="مساحة العمل"
        title="سجل التطوير"
        subtitle="مهام الوكلاء وبث الأحداث: أين توقف العمل وما أُنجز."
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
      <div className="brain-grid" style={{ marginTop: "1rem" }}>
        <ThinkingStream events={events} title="أحداث حية" />
        <GlassCard title="مهام الوكلاء">
          <ul className="checklist">
            {tasks.map((t) => (
              <li key={t.id} className={t.status === "succeeded" ? "is-done" : t.status === "running" ? "is-active" : ""}>
                <span className="check" aria-hidden>
                  {t.status === "succeeded" ? "✓" : t.status === "running" ? "●" : ""}
                </span>
                <span>
                  <strong>{t.agent_name}</strong> — {t.objective}
                  <br />
                  <small>
                    {t.department} · {t.status}
                  </small>
                </span>
              </li>
            ))}
            {!tasks.length && <li>لا مهام مسجّلة بعد.</li>}
          </ul>
        </GlassCard>
      </div>
    </div>
  );
}
