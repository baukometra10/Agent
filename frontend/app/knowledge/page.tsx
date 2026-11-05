"use client";

import { useEffect, useState } from "react";
import { fetchKnowledge, fetchProjectMemory, fetchProjects } from "@/lib/api";
import type { KnowledgeNode, Project } from "@/lib/types";
import { GlassCard } from "@/components/ui/GlassCard";
import { PageHeader } from "@/components/ui/PageHeader";

type MemoryRecall = {
  binding?: {
    project_name?: string;
    workspace_path?: string;
    isolation_namespace?: string;
    rule?: string;
  };
  standing_instructions?: { id: string; content: string }[];
  transcript?: { role?: string; content?: string; at?: string }[];
  counts?: Record<string, number>;
};

export default function KnowledgePage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [nodes, setNodes] = useState<KnowledgeNode[]>([]);
  const [ltm, setLtm] = useState<MemoryRecall | null>(null);

  useEffect(() => {
    fetchProjects().then((rows) => {
      setProjects(rows);
      if (rows[0]) setProjectId(rows[0].id);
    });
  }, []);

  useEffect(() => {
    if (!projectId) return;
    fetchKnowledge(projectId).then(setNodes);
    fetchProjectMemory(projectId).then((row) => setLtm(row as MemoryRecall | null));
  }, [projectId]);

  return (
    <div>
      <PageHeader
        eyebrow="مساحة العمل"
        title="المعرفة والذاكرة"
        subtitle="طبقات المعرفة + ذاكرة المشروع المعزولة + استرجاع دلالي محلي."
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

      {ltm?.binding && (
        <div style={{ marginTop: "1rem" }}>
        <GlassCard>
          <h2 style={{ marginTop: 0 }}>أين يعمل الوكيل</h2>
          <p>
            <strong>{ltm.binding.project_name}</strong>
          </p>
          <small style={{ display: "block", direction: "ltr", textAlign: "left" }}>
            {ltm.binding.workspace_path}
          </small>
          <small style={{ display: "block", direction: "ltr", textAlign: "left" }}>
            ns: {ltm.binding.isolation_namespace}
          </small>
          <p>{ltm.binding.rule}</p>
          <small>
            transcript={ltm.counts?.transcript ?? 0} · standing=
            {ltm.counts?.standing_instructions ?? 0}
          </small>
        </GlassCard>
        </div>
      )}

      {!!ltm?.standing_instructions?.length && (
        <div style={{ marginTop: "1rem" }}>
          <h2>تعليمات دائمة لهذا المشروع</h2>
          {ltm.standing_instructions.map((row) => (
            <article key={row.id} className="node fact">
              <p>{row.content}</p>
            </article>
          ))}
        </div>
      )}

      {!!ltm?.transcript?.length && (
        <div style={{ marginTop: "1rem" }}>
          <h2>سجل الكلمات المحفوظة</h2>
          <div className="knowledge-list">
            {ltm.transcript
              .slice()
              .reverse()
              .slice(0, 40)
              .map((row, i) => (
                <article key={`${row.at}-${i}`} className="node">
                  <strong>{row.role}</strong>
                  <small>{row.at}</small>
                  <p>{row.content}</p>
                </article>
              ))}
          </div>
        </div>
      )}

      <div className="knowledge-list" style={{ marginTop: "1rem" }}>
        <h2>عقد المعرفة</h2>
        {nodes.map((node) => (
          <article key={node.id} className={`node ${node.kind}`}>
            <strong>{node.title}</strong>
            <small>
              {node.kind} · {node.memory_layer}/{node.category} · ثقة{" "}
              {Math.round(node.confidence * 100)}%
            </small>
            <p>{node.content}</p>
          </article>
        ))}
        {!nodes.length && <div className="empty">الذاكرة فارغة لهذا المشروع.</div>}
      </div>
    </div>
  );
}
