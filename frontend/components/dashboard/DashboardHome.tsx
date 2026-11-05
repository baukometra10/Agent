import Image from "next/image";
import Link from "next/link";
import type { Project } from "@/lib/types";
import { GlassCard } from "@/components/ui/GlassCard";
import { IconFolder, IconProjects, IconProposals, IconRocket } from "@/components/icons";
import { ProposalActions } from "./ProposalActions";
import { ProgressRing } from "./ProgressRing";
import { Sparkline } from "./Sparkline";

type Props = {
  projects: Project[];
};

const planSteps = [
  { title: "إصلاح مشاكل الأداء", done: true },
  { title: "تحسين نظام الصلاحيات", done: true },
  { title: "إضافة التقارير المالية المتقدمة", done: false, active: true },
  { title: "تحسين تجربة المستخدم", done: false },
];

const workflowSteps = [
  { title: "تحليل المشروع", done: true },
  { title: "الخطة التفصيلية", done: true },
  { title: "تنفيذ التحسينات", done: false, active: true },
  { title: "مراجعة واعتماد", done: false },
];

const knowledgeTree = [
  { id: "root", label: "المنصة الرئيسية", children: ["finance", "comms", "hr", "reports"] },
];

const knowledgeNodes: Record<string, string> = {
  finance: "المحاسبة المالية",
  comms: "التواصل",
  hr: "إدارة الموظفين",
  reports: "التقارير والتحليلات",
};

const performance = [
  { day: "الأحد", value: 62 },
  { day: "الإثنين", value: 70 },
  { day: "الثلاثاء", value: 78 },
  { day: "الأربعاء", value: 85 },
  { day: "الخميس", value: 92 },
];

export function DashboardHome({ projects }: Props) {
  const activeCount = projects.filter((p) => p.status !== "archived").length || projects.length;
  const featured = projects[0];
  const featuredProgress = featured
    ? Math.round((featured.understanding_progress || 0) * 100) || 68
    : 68;

  return (
    <div className="dash">
      <section className="hero-row">
        <div className="welcome">
          <h1>
            مرحباً أحمد <span aria-hidden>👋</span>
          </h1>
          <p>منصتك الذكية لإدارة تطور البرمجيات عبر وكلاء الذكاء الاصطناعي — بموافقة بشرية في كل خطوة.</p>
        </div>

        <article className="agent-banner">
          <div className="agent-banner__copy">
            <span className="live-pill">
              <i className="live-pill__dot" />
              مباشر
            </span>
            <h2>الوكيل الذكي يعمل الآن…</h2>
            <p>يحلل المشروع النشط حاليًا ويبني خطة التطوير التالية اعتمادًا على خريطة المعرفة.</p>
          </div>
          <div className="agent-banner__visual">
            <div className="brain-pulse" aria-hidden />
            <Image
              src="/agent-brain.jpg"
              alt=""
              width={220}
              height={220}
              className="agent-brain"
              priority
            />
          </div>
        </article>
      </section>

      <section className="kpi-row" aria-label="مؤشرات الأداء">
        <article className="kpi-card kpi-card--purple">
          <div className="kpi-card__meta">
            <span>نجاح التحديثات</span>
            <strong>92%</strong>
            <em className="delta delta--up">+5%</em>
          </div>
          <Sparkline values={[70, 74, 78, 82, 86, 90, 92]} color="#A78BFA" />
        </article>
        <article className="kpi-card kpi-card--green">
          <div className="kpi-card__meta">
            <span>مهام قيد التنفيذ</span>
            <strong>3</strong>
            <IconRocket size={18} />
          </div>
          <Sparkline values={[1, 2, 2, 3, 2, 3, 3]} color="#3DDC97" />
        </article>
        <article className="kpi-card kpi-card--blue">
          <div className="kpi-card__meta">
            <span>مشاريع نشطة</span>
            <strong>{activeCount || 5}</strong>
            <IconFolder size={18} />
          </div>
          <Sparkline values={[2, 3, 3, 4, 4, 5, activeCount || 5]} color="#4F7CFF" />
        </article>
        <article className="kpi-card kpi-card--gold">
          <div className="kpi-card__meta">
            <span>مقترحات تطوير جديدة</span>
            <strong>12</strong>
            <IconProposals size={18} />
          </div>
          <Sparkline values={[4, 6, 7, 8, 9, 11, 12]} color="#FFC857" />
        </article>
      </section>

      <section className="widget-row">
        <GlassCard className="widget project-overview" title="نظرة عامة على المشروع النشط">
          <div className="project-overview__body">
            <div className="hex-logo" aria-hidden>
              <IconProjects size={22} />
            </div>
            <div className="project-overview__info">
              <h3>{featured?.name || "مشروع المنصة الرئيسية"}</h3>
              <p>
                تاريخ البدء 2025/01/01 · آخر تحديث منذ ساعة
                {featured?.status ? ` · ${featured.status}` : ""}
              </p>
            </div>
            <ProgressRing value={featuredProgress} size={108} sublabel="اكتمال الفهم" />
          </div>
          <div className="bar-track" aria-hidden>
            <span style={{ width: `${featuredProgress}%` }} />
          </div>
          <Link
            href={featured ? `/projects/${featured.id}` : "/projects"}
            className="btn btn-primary project-overview__cta"
          >
            عرض التفاصيل
          </Link>
        </GlassCard>

        <GlassCard className="widget" title="خطة التطوير الحالية">
          <ol className="plan-steps">
            {planSteps.map((step) => (
              <li
                key={step.title}
                className={[
                  step.done ? "is-done" : "",
                  step.active ? "is-active" : "",
                ]
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

        <GlassCard className="widget proposal-card" title="أحدث مقترح من الوكيل">
          <article className="proposal-panel">
            <span className="tag tag--warn">بانتظار الموافقة</span>
            <h3>تحسين نظام إدارة الموظفين</h3>
            <dl className="why-block">
              <div>
                <dt>ما المقترح؟</dt>
                <dd>إعادة هيكلة وحدة الموارد البشرية لتقليل التعقيد وتحسين صلاحيات الأدوار.</dd>
              </div>
              <div>
                <dt>لماذا؟</dt>
                <dd>
                  التحليل كشف تكرار منطق الصلاحيات عبر 4 وحدات، مما يزيد مخاطر الأخطاء الأمنية ويبطئ التطوير.
                </dd>
              </div>
            </dl>
            <ProposalActions />
          </article>
        </GlassCard>
      </section>

      <section className="widget-row">
        <GlassCard className="widget" title="أداء التطوير">
          <div className="perf-chart" role="img" aria-label="مخطط أداء التطوير يصل إلى 92%">
            <svg viewBox="0 0 360 160" className="perf-chart__svg">
              <defs>
                <linearGradient id="perfFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="rgba(79,124,255,0.35)" />
                  <stop offset="100%" stopColor="rgba(79,124,255,0)" />
                </linearGradient>
              </defs>
              {[0, 1, 2, 3].map((i) => (
                <line
                  key={i}
                  x1="24"
                  x2="340"
                  y1={20 + i * 35}
                  y2={20 + i * 35}
                  stroke="rgba(120,140,200,0.12)"
                />
              ))}
              <path
                d="M24,120 C70,110 100,95 140,88 C180,80 210,70 250,48 C290,28 320,24 340,18 L340,140 L24,140 Z"
                fill="url(#perfFill)"
              />
              <path
                d="M24,120 C70,110 100,95 140,88 C180,80 210,70 250,48 C290,28 320,24 340,18"
                fill="none"
                stroke="#4F7CFF"
                strokeWidth="3"
                strokeLinecap="round"
              />
              <circle cx="340" cy="18" r="5" fill="#5CE1FF" />
            </svg>
            <div className="perf-chart__axis">
              {performance.map((p) => (
                <span key={p.day}>{p.day}</span>
              ))}
            </div>
            <strong className="perf-chart__badge">92%</strong>
          </div>
        </GlassCard>

        <GlassCard className="widget workflow-card" title="سير العمل الحالي">
          <div className="workflow">
            <ProgressRing value={75} size={126} label="75%" sublabel="من الخطة" color="var(--cyan)" />
            <ul className="checklist">
              {workflowSteps.map((step) => (
                <li
                  key={step.title}
                  className={[
                    step.done ? "is-done" : "",
                    step.active ? "is-active" : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  <span className="check" aria-hidden>
                    {step.done ? "✓" : step.active ? "●" : ""}
                  </span>
                  {step.title}
                </li>
              ))}
            </ul>
          </div>
        </GlassCard>

        <GlassCard className="widget" title="خريطة معرفة المشروع">
          <div className="knowledge-tree">
            {knowledgeTree.map((root) => (
              <div key={root.id} className="knowledge-tree__root">
                <div className="tree-node tree-node--root">{root.label}</div>
                <svg className="knowledge-tree__connectors" viewBox="0 0 320 36" aria-hidden>
                  <path
                    d="M160 0 V12 M160 12 H40 V36 M160 12 H120 V36 M160 12 H200 V36 M160 12 H280 V36"
                    fill="none"
                    stroke="rgba(92,225,255,0.35)"
                    strokeWidth="1.5"
                  />
                  <circle cx="160" cy="12" r="3" fill="#5CE1FF" />
                </svg>
                <div className="knowledge-tree__branches">
                  {root.children.map((child) => (
                    <div key={child} className="tree-node">
                      {knowledgeNodes[child]}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </GlassCard>
      </section>
    </div>
  );
}
