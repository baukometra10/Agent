"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { IdeAgentPanel } from "@/components/ide/IdeAgentPanel";
import { PageHeader } from "@/components/ui/PageHeader";
import { SectionLinks } from "@/components/ui/SectionLinks";
import { applyAgentEdits } from "@/lib/applyAgentEdits";
import type { Project } from "@/lib/types";
import { fetchWorkspaceTree } from "@/lib/workspace";

type Props = {
  projects: Project[];
  initialProjectId?: string;
};

/**
 * Brain / project agent surface — same IdeAgentPanel as the IDE and CommandDock.
 * Sessions are shared per project across all three entry points.
 */
export function AgentWorkspace({ projects, initialProjectId }: Props) {
  const router = useRouter();
  const [projectId, setProjectId] = useState(initialProjectId || projects[0]?.id || "");
  const [treePaths, setTreePaths] = useState<string[]>([]);
  const [status, setStatus] = useState("");

  const project = projects.find((p) => p.id === projectId) || null;

  const reloadTree = useCallback(async (pid: string) => {
    if (!pid) {
      setTreePaths([]);
      return;
    }
    const tree = await fetchWorkspaceTree(pid);
    setTreePaths((tree.entries || []).filter((e) => e.type === "file").map((e) => e.path));
  }, []);

  useEffect(() => {
    void reloadTree(projectId);
  }, [projectId, reloadTree]);

  return (
    <div className="brain-agent">
      <PageHeader
        eyebrow="ذكاء اصطناعي"
        title="عقل الوكيل"
        subtitle="نفس وكيل مساحة العمل — الجلسات والتعديلات مشتركة مع المحرر ولوحة الوكيل."
        actions={
          projectId ? (
            <Link href={`/ide?project=${encodeURIComponent(projectId)}`} className="btn btn-primary">
              فتح في المحرر
            </Link>
          ) : null
        }
      />
      <SectionLinks sectionId="brain" />

      <div className="brain-agent__bar">
        <label htmlFor="brain-project">المشروع</label>
        <select
          id="brain-project"
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
        {status ? <span className="brain-agent__status">{status}</span> : null}
      </div>

      {!projects.length ? (
        <div className="brain-agent__empty">
          <p>اربط مشروعاً أولاً ليبدأ الوكيل بنفس تجربة المحرر.</p>
          <Link href="/projects" className="btn btn-primary">
            المشاريع
          </Link>
        </div>
      ) : projectId ? (
        <div className="brain-agent__panel">
          <IdeAgentPanel
            projectId={projectId}
            activePath={null}
            treePaths={treePaths}
            onApplyEdits={async (edits) => {
              const res = await applyAgentEdits(projectId, edits);
              if (!res.ok) {
                setStatus(String(res.error || "تعذّر تطبيق التعديلات"));
                return;
              }
              setStatus(
                edits.length
                  ? `طُبّقت ${edits.length} تعديلات على ${project?.name || "المشروع"}`
                  : "",
              );
              await reloadTree(projectId);
            }}
            onOpenPath={(path) => {
              router.push(
                `/ide?project=${encodeURIComponent(projectId)}&file=${encodeURIComponent(path)}`,
              );
            }}
            onLog={(text) => setStatus(text)}
            onStartVenture={(brief) => {
              router.push(
                `/ide?project=${encodeURIComponent(projectId)}&venture=${encodeURIComponent(brief.slice(0, 200))}`,
              );
            }}
          />
        </div>
      ) : null}
    </div>
  );
}
