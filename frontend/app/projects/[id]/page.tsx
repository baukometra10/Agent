import Link from "next/link";
import { GlassCard } from "@/components/ui/GlassCard";
import { PageHeader } from "@/components/ui/PageHeader";
import { ProgressRing } from "@/components/dashboard/ProgressRing";
import { AgentWorkspace } from "@/components/brain/AgentWorkspace";
import { fetchKnowledge, fetchProject } from "@/lib/api";
import { SectionLinks } from "@/components/ui/SectionLinks";
import {
  memoryLayerLabel,
  projectStatusLabel,
  sourceTypeLabel,
} from "@/lib/uiLabels";
import { UnderstandButton } from "./understand-button";

export default async function ProjectPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const project = await fetchProject(id);
  const knowledge = project ? await fetchKnowledge(id) : [];

  if (!project) {
    return (
      <div>
        <p className="empty">المشروع غير موجود.</p>
        <Link href="/projects" className="back-link">
          ← العودة للمشاريع
        </Link>
      </div>
    );
  }

  const progress = Math.round((project.understanding_progress || 0) * 100);

  return (
    <div className="detail-grid">
      <div>
        <Link href="/projects" className="back-link">
          ← كل المشاريع
        </Link>
        <PageHeader
          eyebrow="مشروع معزول"
          title={project.name}
          subtitle={`الحالة: ${projectStatusLabel(project.status)} · تقدم الفهم: ${progress}%`}
        />
        <SectionLinks sectionId="projects" />

        <UnderstandButton projectId={project.id} />

        <div className="meta" style={{ marginBottom: "1.25rem" }}>
          {(project.frameworks || []).map((fw) => (
            <span className="chip" key={fw}>
              {fw}
            </span>
          ))}
          {(project.languages || []).map((lang) => (
            <span className="chip" key={lang.name}>
              {lang.name} ({lang.files})
            </span>
          ))}
          {project.file_stats?.total_files != null && (
            <span className="chip">{project.file_stats.total_files} ملفًا</span>
          )}
        </div>
      </div>

      <div className="widget-row" style={{ gridTemplateColumns: "minmax(0, 0.7fr) minmax(0, 1.3fr)" }}>
        <GlassCard title="تقدم الفهم">
          <div style={{ display: "grid", placeItems: "center", padding: "0.5rem 0 1rem" }}>
            <ProgressRing value={progress} size={140} sublabel="اكتمال الفهم" />
          </div>
          {project.description && (
            <p style={{ color: "var(--muted)", margin: 0, lineHeight: 1.6 }}>{project.description}</p>
          )}
        </GlassCard>

        <GlassCard title="خريطة المعرفة">
          <p style={{ color: "var(--muted)", marginTop: 0, fontSize: "0.88rem" }}>
            حقائق واستنتاجات وعناصر غير مؤكدة — مفصولة دائمًا، مع المصدر لكل عقدة.
          </p>
          {knowledge.length === 0 ? (
            <div className="empty">لا معرفة بعد. شغّل الفهم لملء الخريطة.</div>
          ) : (
            <div className="knowledge-list">
              {knowledge.map((node) => (
                <article key={node.id} className={`node ${node.kind}`}>
                  <strong>{node.title}</strong>
                  <div>
                    <small>
                      {node.kind === "fact"
                        ? "حقيقة"
                        : node.kind === "inference"
                          ? "استنتاج"
                          : "غير مؤكد"}
                      {" · "}
                      {memoryLayerLabel(node.memory_layer)}
                      {node.category ? ` / ${memoryLayerLabel(node.category)}` : ""}
                      {" · "}
                      ثقة {Math.round(node.confidence * 100)}%
                      {" · "}
                      مصدر {sourceTypeLabel(node.source_type)}
                      {node.source_path ? (
                        <>
                          {" · "}
                          <span dir="ltr">{node.source_path}</span>
                        </>
                      ) : null}
                    </small>
                  </div>
                  <p style={{ margin: "0.55rem 0 0", lineHeight: 1.55 }}>{node.content}</p>
                </article>
              ))}
            </div>
          )}
        </GlassCard>
      </div>

      <div style={{ marginTop: "1.5rem" }}>
        <AgentWorkspace projects={[project]} initialProjectId={project.id} />
      </div>
    </div>
  );
}
