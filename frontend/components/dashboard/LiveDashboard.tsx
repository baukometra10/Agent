"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { Project, Proposal } from "@/lib/types";
import { GlassCard } from "@/components/ui/GlassCard";
import { IconFolder, IconProjects, IconProposals, IconRocket } from "@/components/icons";
import { ProgressRing } from "./ProgressRing";
import { Sparkline } from "./Sparkline";
import { NeuralNet } from "@/components/brain/NeuralNet";
import { ThinkingStream } from "@/components/brain/ThinkingStream";
import { CodeStream } from "@/components/brain/CodeStream";
import { useAgentLive } from "@/hooks/useAgentLive";
import { approveProposal, fetchProposals } from "@/lib/api";

type Props = {
  projects: Project[];
  initialProposals?: Proposal[];
};

export function LiveDashboard({ projects, initialProposals = [] }: Props) {
  const featured = projects[0];
  const { events, focus, connected, codeEvents, thinkEvents, intensity } = useAgentLive(
    featured?.id,
  );
  const [proposals, setProposals] = useState(initialProposals);
  const [busyId, setBusyId] = useState<string | null>(null);

  const activeCount = projects.filter((p) => p.status !== "archived").length || projects.length;
  const featuredProgress = featured
    ? Math.round((featured.understanding_progress || 0) * 100)
    : 0;
  const pending = proposals.filter((p) =>
    ["awaiting_approval", "draft", "revision_requested"].includes(p.status),
  );
  const latestProposal = pending[0] || proposals[0];
  const active = focus.active;

  const planSteps = useMemo(() => {
    const phase = focus.phase || "idle";
    return [
      { title: "فهم المشروع", done: featuredProgress > 20, active: phase === "think" },
      { title: "تحليل وتخطيط", done: featuredProgress > 50, active: phase === "neural" || phase === "tool" },
      {
        title: "كتابة / تنفيذ",
        done: codeEvents.length > 0 && !active,
        active: phase === "code" || codeEvents.length > 0,
      },
      { title: "مراجعة واعتماد", done: false, active: phase === "decision" },
    ];
  }, [focus.phase, featuredProgress, codeEvents.length, active]);

  async function onApprove(id: string) {
    if (!featured) return;
    setBusyId(id);
    const updated = await approveProposal(featured.id, id);
    setBusyId(null);
    if (updated) {
      const rows = await fetchProposals(featured.id);
      setProposals(rows);
    }
  }

  return (
    <div className="dash dash--viewport">
      <section className="hero-row">
        <div className="welcome">
          <h1>مرحباً — Spixa جاهز</h1>
          <p>عقل حيّ + موافقة بشرية قبل كل دمج.</p>
          {focus.resume_hint && (
            <p className="welcome__resume">
              <strong>الاستئناف:</strong> {focus.resume_hint}
            </p>
          )}
        </div>

        <article className={`agent-banner ${active ? "is-live" : ""}`}>
          <div className="agent-banner__copy">
            <span className={`live-pill ${active ? "is-hot" : ""}`}>
              <i className="live-pill__dot" />
              {active ? "يعمل الآن" : connected ? "متصل" : "…"}
            </span>
            <h2>{active ? "الوكيل يعمل…" : "وضع الاستعداد"}</h2>
            <p>
              {focus.project_name
                ? `${focus.project_name} · ${focus.phase}`
                : "افتح عقل الوكيل لبدء النشاط الحي."}
            </p>
            <div className="agent-banner__actions">
              <Link href="/brain" className="btn btn-primary">
                عقل الوكيل
              </Link>
              <Link href="/execution" className="btn btn-ghost">
                التنفيذ
              </Link>
            </div>
          </div>
          <div className="agent-banner__visual agent-banner__visual--net">
            <NeuralNet active={active} intensity={intensity} />
          </div>
        </article>
      </section>

      <section className="brain-grid dash-live-grid">
        <ThinkingStream events={thinkEvents.length ? thinkEvents : events.slice(-8)} />
        <CodeStream events={codeEvents} />
      </section>

      <section className="kpi-row" aria-label="مؤشرات الأداء">
        <article className="kpi-card kpi-card--purple">
          <div className="kpi-card__meta">
            <span>أحداث</span>
            <strong>{events.length}</strong>
            <em className="delta delta--up">{connected ? "live" : "…"}</em>
          </div>
          <Sparkline
            values={events.slice(-8).map((e) => Math.round((e.intensity || 0.3) * 100))}
            color="#A78BFA"
          />
        </article>
        <article className="kpi-card kpi-card--green">
          <div className="kpi-card__meta">
            <span>ملفات</span>
            <strong>{codeEvents.length}</strong>
            <IconRocket size={16} />
          </div>
          <Sparkline values={[0, 1, 1, codeEvents.length]} color="#3DDC97" />
        </article>
        <article className="kpi-card kpi-card--blue">
          <div className="kpi-card__meta">
            <span>مشاريع</span>
            <strong>{activeCount}</strong>
            <IconFolder size={16} />
          </div>
          <Sparkline values={[1, 2, Math.max(2, activeCount)]} color="#4F7CFF" />
        </article>
        <article className="kpi-card kpi-card--gold">
          <div className="kpi-card__meta">
            <span>مقترحات</span>
            <strong>{pending.length}</strong>
            <IconProposals size={16} />
          </div>
          <Sparkline values={[0, pending.length, pending.length]} color="#FFC857" />
        </article>
      </section>

      <section className="widget-row">
        <GlassCard className="widget project-overview" title="المشروع النشط">
          <div className="project-overview__body">
            <div className="hex-logo" aria-hidden>
              <IconProjects size={18} />
            </div>
            <div className="project-overview__info">
              <h3>{featured?.name || "لا مشروع بعد"}</h3>
              <p>
                {featured
                  ? `${featured.status}`
                  : "أضف مشروعًا من إدارة المشاريع"}
              </p>
            </div>
            <ProgressRing value={featuredProgress} size={72} sublabel="فهم" />
          </div>
          <div className="bar-track" aria-hidden>
            <span style={{ width: `${featuredProgress}%` }} />
          </div>
          <Link
            href={featured ? `/projects/${featured.id}` : "/projects"}
            className="btn btn-primary project-overview__cta"
          >
            مساحة المشروع
          </Link>
        </GlassCard>

        <GlassCard className="widget" title="خطة التطوير">
          <ol className="plan-steps">
            {planSteps.map((step) => (
              <li
                key={step.title}
                className={[step.done ? "is-done" : "", step.active ? "is-active" : ""]
                  .filter(Boolean)
                  .join(" ")}
              >
                <span className="plan-steps__marker" />
                <div className="plan-steps__body">
                  <span>{step.title}</span>
                  {step.active && <em className="plan-pill">قيد التنفيذ</em>}
                  {step.done && <em className="plan-pill plan-pill--done">مكتمل</em>}
                </div>
              </li>
            ))}
          </ol>
        </GlassCard>

        <GlassCard className="widget proposal-card" title="أحدث مقترح">
          {latestProposal ? (
            <article className="proposal-panel">
              <span className="tag tag--warn">{latestProposal.status}</span>
              <h3>{latestProposal.title}</h3>
              <dl className="why-block">
                <div>
                  <dt>المقترح</dt>
                  <dd>{latestProposal.proposal}</dd>
                </div>
              </dl>
              {["awaiting_approval", "draft", "revision_requested"].includes(latestProposal.status) && (
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={busyId === latestProposal.id}
                  onClick={() => onApprove(latestProposal.id)}
                >
                  اعتماد
                </button>
              )}
              <Link href="/proposals" className="back-link dash-inline-link">
                كل المقترحات
              </Link>
            </article>
          ) : (
            <p className="empty">لا مقترحات بعد.</p>
          )}
        </GlassCard>
      </section>
    </div>
  );
}
