"use client";

import { useCallback, useEffect, useState } from "react";
import { GlassCard } from "@/components/ui/GlassCard";
import { PageHeader } from "@/components/ui/PageHeader";
import {
  API_URL,
  climbOwnershipCoverage,
  distillProjectHandoff,
  fetchCostEfficiency,
  fetchModelGateway,
  fetchOwnership,
  fetchOwnershipHandoff,
  fetchProjects,
  growSpecialtyDatasets,
  probeModelGateway,
  promoteAllSpecialties,
  restoreTeachers,
  retireTeachers,
  runLearningCycle,
  runOwnershipEval,
  seedCodingCurriculum,
  seedCodingTutor,
  trainProjectIntelLora,
  type ModelGatewayStatus,
} from "@/lib/api";
import { useRouter } from "next/navigation";
import { isAdmin, useUser } from "@/hooks/useUser";
import { ModelFactoryPanel } from "@/components/factory/ModelFactoryPanel";
import { IntelligenceOpsPanel } from "@/components/intelligence/IntelligenceOpsPanel";
import { SpixaEcosystemPanel } from "@/components/intelligence/SpixaEcosystemPanel";
import { RapidLearningPanel } from "@/components/learning/RapidLearningPanel";
import { initials } from "@/lib/user";

export default function SettingsPage() {
  const { user, update } = useUser();
  const router = useRouter();

  useEffect(() => {
    if (user.signedIn && !isAdmin(user)) router.replace("/console");
  }, [user, router]);
  const [gateway, setGateway] = useState<ModelGatewayStatus | null>(null);
  const [ownership, setOwnership] = useState<Record<string, unknown> | null>(null);
  const [costEff, setCostEff] = useState<Record<string, unknown> | null>(null);
  const [handoff, setHandoff] = useState<Record<string, unknown> | null>(null);
  const [probe, setProbe] = useState<Record<string, unknown> | null>(null);
  const [actionOut, setActionOut] = useState<Record<string, unknown> | null>(null);
  const [probing, setProbing] = useState(false);
  const [busy, setBusy] = useState(false);

  const reloadGateway = useCallback(async () => {
    setGateway(await fetchModelGateway());
    setOwnership(await fetchOwnership());
    setCostEff(await fetchCostEfficiency());
    setHandoff(await fetchOwnershipHandoff());
  }, []);

  useEffect(() => {
    reloadGateway();
  }, [reloadGateway]);

  async function onProbe() {
    setProbing(true);
    setProbe(await probeModelGateway("fast"));
    setProbing(false);
    await reloadGateway();
  }

  async function onEval() {
    setBusy(true);
    setActionOut(await runOwnershipEval("project_intelligence"));
    setBusy(false);
    await reloadGateway();
  }

  async function onTrainPi() {
    setBusy(true);
    setActionOut(await trainProjectIntelLora());
    setBusy(false);
    await reloadGateway();
  }

  async function onSeedCoding() {
    setBusy(true);
    setActionOut(await seedCodingCurriculum());
    setBusy(false);
    await reloadGateway();
  }

  async function onSeedCodingTutor() {
    setBusy(true);
    setActionOut(await seedCodingTutor());
    setBusy(false);
    await reloadGateway();
  }

  async function onGrow() {
    setBusy(true);
    setActionOut(await growSpecialtyDatasets());
    setBusy(false);
    await reloadGateway();
  }

  async function onPromoteAll() {
    setBusy(true);
    setActionOut(await promoteAllSpecialties());
    setBusy(false);
    await reloadGateway();
  }

  async function onLearningCycle() {
    setBusy(true);
    setActionOut(await runLearningCycle());
    setBusy(false);
    await reloadGateway();
  }

  async function onDistillHandoff() {
    setBusy(true);
    const projects = await fetchProjects();
    const first = projects[0];
    setActionOut(first ? await distillProjectHandoff(first.id) : { error: "no_project" });
    setBusy(false);
    await reloadGateway();
  }

  async function onRetireAllReady() {
    setBusy(true);
    setActionOut(await retireTeachers({ all_ready: true }));
    setBusy(false);
    await reloadGateway();
  }

  async function onClimbCoverage() {
    setBusy(true);
    setActionOut(await climbOwnershipCoverage({ n: 10 }));
    setBusy(false);
    await reloadGateway();
  }

  async function onRetireOne(specialty: string) {
    setBusy(true);
    setActionOut(await retireTeachers({ specialty }));
    setBusy(false);
    await reloadGateway();
  }

  async function onRestoreOne(specialty: string) {
    setBusy(true);
    setActionOut(await restoreTeachers(specialty));
    setBusy(false);
    await reloadGateway();
  }

  const providers = gateway?.providers || {};
  const metrics = (gateway?.router?.metrics || {}) as Record<string, unknown>;
  const coverage = Number(metrics.internal_coverage_ratio ?? 0);
  const readiness = (handoff?.readiness || {}) as Record<string, unknown>;
  const specialtyRows = (readiness.specialties || []) as Record<string, unknown>[];

  return (
    <div className="settings-page">
      <PageHeader
        eyebrow="Internal Intelligence First"
        title="ملكية النماذج والتدريب"
        subtitle="ملفّك أولًا، ثم الاتصال والبوابة، ثم عقيدة الملكية وعمليات التدريب — بترتيب واضح."
      />

      <p className="settings-section-label">1 · الملف الشخصي</p>
      <GlassCard title="الملف الشخصي">
        <div className="settings-profile">
          {user.avatarUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={user.avatarUrl} alt="" className="avatar avatar--xl avatar--img" />
          ) : (
            <div className="avatar avatar--xl" aria-hidden>
              {initials(user.name)}
            </div>
          )}
          <div className="settings-form">
            <label>
              الاسم
              <input
                value={user.name}
                onChange={(e) => update({ name: e.target.value })}
                placeholder="اسمك"
              />
            </label>
            <label>
              الدور
              <input
                value={user.role}
                onChange={(e) => update({ role: e.target.value })}
                placeholder="مدير النظام"
              />
            </label>
            <label>
              البريد
              <input
                type="email"
                value={user.email}
                onChange={(e) => update({ email: e.target.value })}
                placeholder="you@gmail.com"
                dir="ltr"
              />
            </label>
            <label>
              رابط صورة الملف
              <input
                value={user.avatarUrl}
                onChange={(e) => update({ avatarUrl: e.target.value })}
                placeholder="https://…"
                dir="ltr"
              />
            </label>
          </div>
        </div>
      </GlassCard>

      <p className="settings-section-label">2 · الاتصال وبوابة النماذج</p>
      <div className="page-grid page-grid--2">
        <GlassCard title="اتصال الواجهة">
          <p style={{ color: "var(--muted)", direction: "ltr", textAlign: "left", marginTop: 0 }}>
            API_URL = {API_URL}
          </p>
        </GlassCard>
        <GlassCard title="بوابة النماذج (معلّم / طالب)">
          <div className="fleet-kpis">
            <div>
              <span>OpenRouter</span>
              <strong style={{ fontSize: "0.95rem" }}>
                {providers.openrouter?.live
                  ? "مباشر"
                  : providers.openrouter?.configured
                    ? "مفتاح"
                    : "—"}
              </strong>
            </div>
            <div>
              <span>Cursor معلّم</span>
              <strong style={{ fontSize: "0.95rem" }}>
                {providers.cursor?.live
                  ? "مباشر"
                  : providers.cursor?.configured
                    ? "مفتاح"
                    : "—"}
              </strong>
            </div>
            <div>
              <span>OpenAI</span>
              <strong style={{ fontSize: "0.95rem" }}>
                {providers.openai?.live ? "مباشر" : providers.openai?.configured ? "مفتاح" : "—"}
              </strong>
            </div>
            <div>
              <span>Anthropic</span>
              <strong style={{ fontSize: "0.95rem" }}>
                {providers.anthropic?.live
                  ? "مباشر"
                  : providers.anthropic?.configured
                    ? "مفتاح"
                    : "—"}
              </strong>
            </div>
            <div>
              <span>داخلي</span>
              <strong style={{ fontSize: "0.95rem" }}>
                {providers.internal?.live ? "مستضاف" : "تجريبي"}
              </strong>
            </div>
            <div>
              <span>وضع البداية</span>
              <strong style={{ fontSize: "0.85rem" }}>
                {gateway?.teacher_bootstrap_first === false ? "داخلي أولاً" : "معلّم أولاً"}
              </strong>
            </div>
          </div>
          <p className="settings-hint" style={{ marginTop: 12 }}>
            المصدر:{" "}
            <span dir="ltr">{gateway?.teacher_upstream_active || gateway?.teacher_upstream || "auto"}</span>
            {gateway?.teacher_upstream_live ? " · متصل" : " · غير متصل"}
            . ضع <code dir="ltr">OPENROUTER_API_KEY</code> أو{" "}
            <code dir="ltr">CURSOR_API_KEY</code> في بيئة الخادم — في البداية يقود المعلّم الخارجي
            حتى تصبح التخصصات المملوكة جاهزة.
          </p>
          {gateway?.routes && (
            <ul className="checklist" style={{ marginTop: 8 }}>
              {Object.entries(gateway.routes).map(([role, model]) => (
                <li key={role}>
                  <span className="check">→</span>
                  <span>
                    معلّم · {role}: <span dir="ltr">{model}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
          <button type="button" className="btn btn-primary" disabled={probing} onClick={onProbe}>
            {probing ? "جاري الفحص…" : "فحص التوجيه"}
          </button>
          {probe && (
            <pre className="settings-pre">{JSON.stringify(probe, null, 2)}</pre>
          )}
          {gateway?.distillation && (
            <p className="settings-hint">
              أمثلة التقطير حسب التخصص:{" "}
              <span dir="ltr">
                {JSON.stringify(gateway.distillation.examples_by_specialty || {})}
              </span>
            </p>
          )}
        </GlassCard>
      </div>

      <p className="settings-section-label">3 · عقيدة الملكية والكفاءة</p>
      <div className="page-grid page-grid--2">
        <GlassCard title="عقيدة ملكية الذكاء">
          <p style={{ marginTop: 0 }}>
            {gateway?.ownership_goal?.doctrine ||
              "الذكاء الداخلي أولًا — معلّم خارجي ← طالب داخلي ← منظومة مملوكة"}
          </p>
          <div className="fleet-kpis">
            <div>
              <span>تغطية داخلية</span>
              <strong>{Math.round(coverage * 100)}%</strong>
            </div>
            <div>
              <span>الهدف</span>
              <strong>
                {Math.round((gateway?.ownership_goal?.target_internal_coverage ?? 0.85) * 100)}%
              </strong>
            </div>
            <div>
              <span>الأولوية محلياً</span>
              <strong style={{ fontSize: "0.9rem" }}>
                {gateway?.prefer_internal === false ? "إيقاف" : "مفعّل"}
              </strong>
            </div>
            <div>
              <span>تكلفة / مهمة</span>
              <strong style={{ fontSize: "0.9rem" }}>
                ${Number(metrics.cost_per_successful_task_usd ?? 0).toFixed(5)}
              </strong>
            </div>
          </div>
          <p className="settings-hint">
            القياس بعدد المهام الناجحة. المعلّم الخارجي للتصعيد بعد فشل الأدلة فقط.
          </p>
          {gateway?.internal_family && (
            <ul className="checklist">
              {gateway.internal_family.map((m) => (
                <li key={String(m.id)} className={m.ready ? "is-done" : ""}>
                  <span className="check">{m.ready ? "✓" : "○"}</span>
                  <span dir="ltr">
                    {String(m.id)} — {String(m.description)} ({String(m.host)})
                  </span>
                </li>
              ))}
            </ul>
          )}
        </GlassCard>

        <GlassCard title="كفاءة التكلفة">
          <p style={{ marginTop: 0, color: "var(--muted)" }}>
            {(costEff?.doctrine_ar as string) ||
              "أفضل جودة بأقل تكلفة إجمالية — لا توفير على حساب الذكاء."}
          </p>
          <div className="fleet-kpis">
            <div>
              <span>مؤشر الكفاءة</span>
              <strong>{Number(costEff?.score ?? 0).toFixed(0)}</strong>
            </div>
            <div>
              <span>مهام داخلية</span>
              <strong>{Math.round(Number(costEff?.internal_task_ratio ?? 0) * 100)}%</strong>
            </div>
            <div>
              <span>تكلفة خارجية</span>
              <strong style={{ fontSize: "0.95rem" }}>
                ${Number(costEff?.external_cost_usd ?? 0).toFixed(4)}
              </strong>
            </div>
            <div>
              <span>جودة وسطية</span>
              <strong>
                {costEff?.avg_quality == null
                  ? "—"
                  : `${Math.round(Number(costEff.avg_quality) * 100)}%`}
              </strong>
            </div>
          </div>
        </GlassCard>
      </div>

      <p className="settings-section-label">4 · عمليات التدريب</p>
      <GlassCard title="تدريب التخصصات وجاهزية النقل">
        <div className="settings-ops">
          <div>
            <h3 className="settings-ops__title">تقييم وبذور</h3>
            <div className="settings-ops__row">
              <button type="button" className="btn btn-primary" disabled={busy} onClick={onEval}>
                {busy ? "…" : "تقييم الجاهزية"}
              </button>
              <button type="button" className="btn btn-ghost" disabled={busy} onClick={onTrainPi}>
                ضبط دقيق · جاهزية
              </button>
              <button type="button" className="btn btn-ghost" disabled={busy} onClick={onSeedCoding}>
                بذرة البرمجة
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                disabled={busy}
                onClick={onSeedCodingTutor}
              >
                دروس خصوصية · مبرمج
              </button>
            </div>
          </div>
          <div>
            <h3 className="settings-ops__title">تنمية وترقية</h3>
            <div className="settings-ops__row">
              <button type="button" className="btn btn-ghost" disabled={busy} onClick={onGrow}>
                تنمية كل التخصصات
              </button>
              <button type="button" className="btn btn-primary" disabled={busy} onClick={onPromoteAll}>
                ترقية التخصصات
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                disabled={busy}
                onClick={onLearningCycle}
              >
                دورة تعلّم مستمر
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={busy}
                onClick={onDistillHandoff}
              >
                تقطير من ذاكرة المشروع
              </button>
            </div>
          </div>
          <div>
            <h3 className="settings-ops__title">تغطية ومعلّمون</h3>
            <div className="settings-ops__row">
              <button
                type="button"
                className="btn btn-primary"
                disabled={busy}
                onClick={onClimbCoverage}
              >
                رفع التغطية (10)
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={busy}
                onClick={onRetireAllReady}
              >
                إيقاف معلّمي الجاهزين
              </button>
            </div>
          </div>
        </div>

        {specialtyRows.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <h3 style={{ margin: "0 0 8px" }}>جاهزية النقل للوكلاء المملوكين</h3>
            <p className="settings-hint">
              جاهز: {String(readiness.specialties_ready ?? 0)}/
              {String(readiness.specialties_total ?? 5)} · متقاعد:{" "}
              {String(readiness.specialties_retired ?? 0)} · {String(readiness.next_action ?? "")}
            </p>
            <ul className="checklist">
              {specialtyRows.map((row) => (
                <li
                  key={String(row.specialty)}
                  className={row.teachers_retired || row.handoff_ready ? "is-done" : ""}
                >
                  <span className="check">
                    {row.teachers_retired ? "◆" : row.handoff_ready ? "✓" : "○"}
                  </span>
                  <span dir="ltr" style={{ flex: 1 }}>
                    {String(row.specialty)} — examples={String(row.examples)} · promoted=
                    {String(row.promoted)} · {String(row.teacher_policy)}
                  </span>
                  {row.teachers_retired ? (
                    <button
                      type="button"
                      className="btn btn-ghost"
                      style={{ fontSize: "0.75rem", padding: "2px 8px" }}
                      disabled={busy}
                      onClick={() => void onRestoreOne(String(row.specialty))}
                    >
                      استعادة معلّم
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="btn btn-ghost"
                      style={{ fontSize: "0.75rem", padding: "2px 8px" }}
                      disabled={busy || !row.handoff_ready}
                      onClick={() => void onRetireOne(String(row.specialty))}
                    >
                      إيقاف معلّم
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
        {ownership?.host != null && (
          <p className="settings-hint" dir="ltr" style={{ textAlign: "left" }}>
            host: {JSON.stringify(ownership.host)}
          </p>
        )}
        {actionOut && <pre className="settings-pre">{JSON.stringify(actionOut, null, 2)}</pre>}
      </GlassCard>

      <p className="settings-section-label">5 · منظومة الذكاء والمصنع</p>
      <SpixaEcosystemPanel />
      <IntelligenceOpsPanel />
      <ModelFactoryPanel />
      <RapidLearningPanel />

      <p className="settings-section-label">6 · بوابات الاستقلال</p>
      <GlassCard title="بوابات الاستقلال">
        <ul className="checklist">
          <li className="is-done">
            <span className="check">✓</span>
            فهم / تحليل / تخطيط تلقائي
          </li>
          <li className="is-done">
            <span className="check">✓</span>
            مسودة مقترحات من الدردشة والخارطة
          </li>
          <li className="is-active">
            <span className="check">●</span>
            التنفيذ على فرع Git بعد اعتماد بشري
          </li>
          <li>
            <span className="check" />
            الدمج والنشر — يدوي دائمًا
          </li>
        </ul>
      </GlassCard>
    </div>
  );
}
