"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { Project } from "@/lib/types";
import { createBlankProject } from "@/lib/api";
import { CodeStream } from "@/components/brain/CodeStream";
import { NeuralNet } from "@/components/brain/NeuralNet";
import { OpenLocalFolderCard } from "@/components/projects/OpenLocalFolderCard";
import { useAgentLive } from "@/hooks/useAgentLive";
import { GlassCard } from "@/components/ui/GlassCard";
import { PageHeader } from "@/components/ui/PageHeader";
import { SectionLinks } from "@/components/ui/SectionLinks";

type Props = { projects: Project[] };

export function ProjectPickerLive({ projects: initial }: Props) {
  const [projects, setProjects] = useState(initial);
  const [selected, setSelected] = useState(initial[0]?.id || "");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const { focus, codeEvents, intensity, connected } = useAgentLive(selected || undefined);
  const active = focus.active;

  useEffect(() => {
    setProjects(initial);
    setSelected((cur) => cur || initial[0]?.id || "");
  }, [initial]);

  const selectedProject = useMemo(
    () => projects.find((p) => p.id === selected),
    [projects, selected],
  );

  async function onCreate() {
    if (!name.trim() || busy) return;
    setBusy(true);
    setMsg(null);
    const created = await createBlankProject({
      name: name.trim(),
      description: description.trim() || undefined,
    });
    setBusy(false);
    if (!created) {
      setMsg("تعذّر إنشاء المشروع.");
      return;
    }
    setProjects((prev) => [created, ...prev]);
    setSelected(created.id);
    setName("");
    setDescription("");
    const disk = created.workspace_path || created.source_uri || "سطح المكتب";
    setMsg(`تم إنشاء «${created.name}» على جهازك: ${disk}`);
  }

  return (
    <div>
      <PageHeader
        eyebrow="العمل"
        title="المشاريع والملفات"
        subtitle="اربط مجلدًا حقيقيًا على جهازك، أو أنشئ مشروعًا جديدًا على سطح المكتب — الكود يبقى عندك دائمًا."
      />
      <SectionLinks sectionId="projects" />

      <OpenLocalFolderCard />

      <GlassCard title="أو إنشاء مشروع جديد على سطح المكتب">
        <p className="settings-hint" style={{ marginTop: 0 }}>
          يُنشأ مجلد باسم المشروع على سطح المكتب (أو Documents/SpixaProjects)، وتُحفظ فيه الملفات
          مباشرة. لاحقًا يمكن تجربة النشر على Railway بعد استقرار التدريب.
        </p>
        <div className="settings-form">
          <label>
            اسم المشروع
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="مثلاً: متجر سريع" />
          </label>
          <label>
            وصف مختصر
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="اختياري"
            />
          </label>
          <button type="button" className="btn btn-primary" disabled={busy || !name.trim()} onClick={onCreate}>
            {busy ? "جاري الإنشاء…" : "إنشاء على سطح المكتب"}
          </button>
          {msg && <p className="settings-hint">{msg}</p>}
        </div>
      </GlassCard>

      <section className="projects-live-panel glass-card" style={{ marginTop: "1rem" }}>
        <div className="projects-live-panel__viz">
          <NeuralNet active={active} intensity={intensity} />
          <div className="projects-live-panel__status">
            <span className={`live-pill ${active ? "is-hot" : ""}`}>
              <i className="live-pill__dot" />
              {active ? "يكتب / يفكر الآن" : connected ? "خامل" : "…"}
            </span>
            <strong>{focus.project_name || selectedProject?.name || "اختر مشروعًا"}</strong>
            <span>{focus.resume_hint || focus.phase}</span>
          </div>
        </div>
        <CodeStream events={codeEvents} title="الكود الذي يُكتب على المشروع المحدد" />
      </section>

      {projects.length === 0 ? (
        <div className="empty">لا توجد مشاريع بعد — اختر مجلدًا من الجهاز أو أنشئ مشروعًا فارغًا.</div>
      ) : (
        <section className="projects-grid">
          {projects.map((project) => {
            const progress = Math.round((project.understanding_progress || 0) * 100);
            const isSel = project.id === selected;
            const isFocus = focus.project_id === project.id && active;
            return (
              <article
                key={project.id}
                className={`project-tile ${isSel ? "is-selected" : ""} ${isFocus ? "is-working" : ""}`}
              >
                <button
                  type="button"
                  className="project-tile__select"
                  onClick={() => setSelected(project.id)}
                >
                  مراقبة حية
                </button>
                <Link href={`/ide?project=${project.id}`}>
                  <h2>{project.name}</h2>
                  <div className="sub">
                    {project.slug} · {project.status}
                    {isFocus ? " · الوكيل هنا" : ""}
                  </div>
                  {(project.workspace_path || project.source_uri) && (
                    <div className="sub" dir="ltr" style={{ fontSize: "0.75rem", opacity: 0.8 }}>
                      {project.workspace_path || project.source_uri}
                    </div>
                  )}
                  <div className="meta">
                    {(project.frameworks || []).slice(0, 6).map((fw) => (
                      <span className="chip" key={fw}>
                        {fw}
                      </span>
                    ))}
                  </div>
                  <div className="progress" aria-label="تقدم الفهم">
                    <span style={{ width: `${progress}%` }} />
                  </div>
                </Link>
              </article>
            );
          })}
        </section>
      )}
    </div>
  );
}
