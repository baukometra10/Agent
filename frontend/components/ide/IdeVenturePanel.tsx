"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { TwinBlastViz } from "@/components/ide/TwinBlastViz";
import {
  approveVenture,
  createResearchExperiment,
  createVenture,
  decideResearchPromote,
  listPatterns,
  listResearchExperiments,
  listVentures,
  rebuildTwin,
  rejectVenture,
  requestResearchPromote,
  runResearchExperiment,
  simulateTwin,
  startCompanyOsDemo,
  type SpixaPattern,
  type VentureRun,
} from "@/lib/ventureApi";

type Props = {
  projectId: string;
  onLog?: (text: string) => void;
  seedBrief?: string | null;
  onSeedConsumed?: () => void;
};

const STATUS_AR: Record<string, string> = {
  pending: "معلّق",
  running: "يعمل",
  awaiting_approval: "بانتظار الموافقة",
  approved: "موافق",
  completed: "مكتمل",
  rejected: "مرفوض",
  failed: "فشل",
  skipped: "—",
  draft: "مسودة",
  cancelled: "أُلغي",
};

const PHASE_SHORT: Record<string, string> = {
  understand: "فهم",
  capabilities: "قدرات",
  architecture: "عمارة",
  prototype: "نموذج",
  simulate: "محاكاة",
  implement: "تنفيذ",
  monitor: "مراقبة",
};

export function IdeVenturePanel({ projectId, onLog, seedBrief = null, onSeedConsumed }: Props) {
  const [brief, setBrief] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [ventures, setVentures] = useState<VentureRun[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [selectedArch, setSelectedArch] = useState<string | null>(null);
  const [ackAdv, setAckAdv] = useState(false);
  const [twin, setTwin] = useState<Record<string, unknown> | null>(null);
  const [simResult, setSimResult] = useState<Record<string, unknown> | null>(null);
  const [patterns, setPatterns] = useState<SpixaPattern[]>([]);
  const [experiments, setExperiments] = useState<Record<string, unknown>[]>([]);
  const [tab, setTab] = useState<"venture" | "twin" | "patterns" | "research">("venture");
  const [composerOpen, setComposerOpen] = useState(true);

  const active = useMemo(
    () => ventures.find((v) => v.id === activeId) || ventures[0] || null,
    [ventures, activeId],
  );

  const refresh = useCallback(async () => {
    const rows = await listVentures(projectId);
    setVentures(rows);
    if (!activeId && rows[0]) setActiveId(rows[0].id);
    if (rows[0] && !seedBrief) setComposerOpen(false);
    const pats = await listPatterns();
    setPatterns(pats);
    const exps = await listResearchExperiments();
    setExperiments(exps);
  }, [projectId, activeId, seedBrief]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!seedBrief?.trim()) return;
    setBrief(seedBrief.trim());
    setTab("venture");
    setComposerOpen(true);
    onSeedConsumed?.();
  }, [seedBrief, onSeedConsumed]);

  useEffect(() => {
    const simPhase = active?.phases.find((p) => p.name === "simulate");
    const sim = (simPhase?.output?.simulation || null) as Record<string, unknown> | null;
    if (sim) setSimResult(sim);
  }, [active]);

  async function startVenture(textIn?: string) {
    const text = (textIn ?? brief).trim();
    if (text.length < 8) {
      setError("صِغ الهدف بوضوح أكبر (٨ أحرف على الأقل).");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const row = await createVenture(projectId, text);
      if (!row) {
        setError("تعذّر بدء Venture. حاول مجدداً.");
        return;
      }
      setActiveId(row.id);
      setVentures((prev) => [row, ...prev.filter((v) => v.id !== row.id)]);
      onLog?.(`venture started · ${row.title}`);
      setBrief("");
      setComposerOpen(false);
      setAckAdv(false);
      setComposerOpen(false);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function startDemo() {
    setBusy(true);
    setError("");
    try {
      const row = await startCompanyOsDemo(projectId);
      if (!row) {
        setError("Demo konnte nicht gestartet werden.");
        return;
      }
      setActiveId(row.id);
      setVentures((prev) => [row, ...prev.filter((v) => v.id !== row.id)]);
      setTab("venture");
      setComposerOpen(false);
      onLog?.(`demo Firmen-OS · ${row.status}`);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onApprove() {
    if (!active) return;
    setBusy(true);
    setError("");
    try {
      const row = await approveVenture(projectId, active.id, selectedArch, ackAdv);
      if (row) {
        setVentures((prev) => prev.map((v) => (v.id === row.id ? row : v)));
        onLog?.(`venture approved · ${row.current_phase}`);
        setAckAdv(false);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onReject() {
    if (!active) return;
    setBusy(true);
    try {
      const row = await rejectVenture(projectId, active.id, "user rejected");
      if (row) setVentures((prev) => prev.map((v) => (v.id === row.id ? row : v)));
    } finally {
      setBusy(false);
    }
  }

  const archPhase = active?.phases.find((p) => p.name === "architecture");
  const alts =
    ((archPhase?.output?.evolution as { alternatives?: Array<Record<string, unknown>> }) || {})
      .alternatives || [];
  const waiting = active?.phases.find((p) => p.status === "awaiting_approval");
  const adv = (waiting?.output?.adversarial || null) as Record<string, unknown> | null;
  const blocking = Boolean(adv?.blocking);

  return (
    <aside className="ide-venture" dir="ltr">
      <header className="ide-venture__head">
        <div className="ide-venture__head-row">
          <strong>Venture</strong>
          {active ? (
            <em className={`ide-venture__pill is-${active.status}`}>
              {STATUS_AR[active.status] || active.status}
            </em>
          ) : null}
        </div>
      </header>

      <nav className="ide-venture__tabs" aria-label="أقسام Venture">
        {(
          [
            ["venture", "المسار"],
            ["twin", "Twin"],
            ["patterns", "معرفة"],
            ["research", "مختبر"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={tab === id ? "is-on" : ""}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === "venture" ? (
        <div className="ide-venture__body">
          <p className="ide-venture__steps" aria-hidden>
            <span>١ هدف</span>
            <i>→</i>
            <span>٢ مراحل</span>
            <i>→</i>
            <span>٣ موافقة</span>
          </p>
          <div className="ide-venture__toolbar">
            <button
              type="button"
              className="ide-venture__ghost"
              disabled={busy}
              onClick={() => setComposerOpen((v) => !v)}
            >
              {composerOpen ? "إخفاء الهدف" : "هدف جديد"}
            </button>
            <button type="button" className="ide-venture__ghost" disabled={busy} onClick={() => void startDemo()}>
              عرض توضيحي
            </button>
          </div>

          {composerOpen ? (
            <div className="ide-venture__composer">
              <textarea
                value={brief}
                onChange={(e) => setBrief(e.target.value)}
                placeholder="هدف العمل… مثال: نظام تشغيلي يكتشف الاختناقات ويقترح تحسينات"
                rows={3}
                dir="auto"
              />
              <button
                type="button"
                className="ide-venture__primary"
                disabled={busy}
                onClick={() => void startVenture()}
              >
                {busy ? "يبدأ…" : "بدء المسار"}
              </button>
            </div>
          ) : null}

          {error ? <p className="ide-venture__error">{error}</p> : null}

          {ventures.length > 1 ? (
            <label className="ide-venture__field">
              <span>تشغيل</span>
              <select value={active?.id || ""} onChange={(e) => setActiveId(e.target.value)}>
                {ventures.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.title.length > 42 ? `${v.title.slice(0, 40)}…` : v.title}
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          {active ? (
            <>
              <p className="ide-venture__title" title={active.title} dir="auto">
                {active.title}
              </p>

              <ol className="ide-venture__phases">
                {active.phases.map((p) => (
                  <li key={p.id} className={`is-${p.status}`}>
                    <i />
                    <strong>{PHASE_SHORT[p.name] || p.label}</strong>
                    <span>{STATUS_AR[p.status] || p.status}</span>
                  </li>
                ))}
              </ol>

              {alts.length ? (
                <div className="ide-venture__alts">
                  <p>اختر العمارة</p>
                  {alts.map((a) => {
                    const id = String(a.id || "");
                    const on =
                      selectedArch === id ||
                      (!selectedArch && id === String(archPhase?.output?.selected_id || ""));
                    return (
                      <button
                        key={id}
                        type="button"
                        className={`ide-venture__alt ${on ? "is-on" : ""}`}
                        onClick={() => setSelectedArch(id)}
                      >
                        <strong>{String(a.style || "option")}</strong>
                        <span>{String(a.rank_score ?? "—")}</span>
                      </button>
                    );
                  })}
                </div>
              ) : null}

              {active.status === "awaiting_approval" ? (
                <div className="ide-venture__gates-block">
                  {blocking ? (
                    <label className="ide-venture__ack">
                      <input type="checkbox" checked={ackAdv} onChange={(e) => setAckAdv(e.target.checked)} />
                      أوافق على النتائج الحرجة وأكمل
                    </label>
                  ) : null}
                  {simResult ? <TwinBlastViz simulation={simResult} /> : null}
                  <div className="ide-venture__gates">
                    <button
                      type="button"
                      className="ide-venture__primary"
                      disabled={busy || (blocking && !ackAdv)}
                      onClick={() => void onApprove()}
                    >
                      موافقة
                    </button>
                    <button type="button" className="is-danger" disabled={busy} onClick={() => void onReject()}>
                      رفض
                    </button>
                  </div>
                </div>
              ) : null}
            </>
          ) : (
            <p className="ide-venture__hint">حدّد هدفاً ← مراحل ببوابات موافقة بشرية ← تنفيذ.</p>
          )}
        </div>
      ) : null}

      {tab === "twin" ? (
        <div className="ide-venture__body">
          <div className="ide-venture__gates">
            <button
              type="button"
              className="ide-venture__primary"
              disabled={busy}
              onClick={() => {
                setBusy(true);
                void rebuildTwin(projectId)
                  .then((t) => {
                    setTwin(t);
                    onLog?.("digital twin rebuilt");
                  })
                  .finally(() => setBusy(false));
              }}
            >
              Twin bauen
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                setBusy(true);
                void simulateTwin(projectId, brief || active?.brief || "proposed change", [
                  ".spixa/design",
                  "api",
                  "domain",
                ])
                  .then((r) => setSimResult(r))
                  .finally(() => setBusy(false));
              }}
            >
              Blast-Radius
            </button>
          </div>
          <TwinBlastViz simulation={simResult} />
          {twin ? (
            <pre className="ide-venture__pre">{JSON.stringify(twin, null, 2).slice(0, 900)}</pre>
          ) : null}
        </div>
      ) : null}

      {tab === "patterns" ? (
        <div className="ide-venture__body">
          <p className="ide-venture__hint">Freigegebene Muster — ohne Kundendaten.</p>
          <ul className="ide-venture__list">
            {patterns.map((p) => (
              <li key={p.id}>
                <strong>{p.title}</strong>
                <span>
                  {p.approved ? "approved" : "candidate"} · {p.category}
                </span>
                <em>{p.summary.slice(0, 140)}</em>
              </li>
            ))}
            {!patterns.length ? <li>Noch keine Muster</li> : null}
          </ul>
        </div>
      ) : null}

      {tab === "research" ? (
        <div className="ide-venture__body">
          <button
            type="button"
            className="ide-venture__primary"
            disabled={busy}
            onClick={() => {
              setBusy(true);
              void createResearchExperiment({
                title: "Sandbox routing compare",
                hypothesis: brief || "Compare two reasoning prompts for architecture briefs",
                kind: "prompt",
              })
                .then(async (ex) => {
                  if (!ex?.id) return;
                  await runResearchExperiment(String(ex.id));
                  await refresh();
                  onLog?.("research experiment completed");
                })
                .finally(() => setBusy(false));
            }}
          >
            Lab-Experiment
          </button>
          <ul className="ide-venture__list">
            {experiments.map((ex) => {
              const id = String(ex.id || "");
              return (
                <li key={id}>
                  <strong>{String(ex.title || id)}</strong>
                  <span>
                    {String(ex.status)} · promote={String(ex.promote_approved)}
                  </span>
                  <div className="ide-venture__gates">
                    <button type="button" onClick={() => void requestResearchPromote(id).then(() => refresh())}>
                      Anfragen
                    </button>
                    <button type="button" onClick={() => void decideResearchPromote(id, true).then(() => refresh())}>
                      OK
                    </button>
                    <button
                      type="button"
                      className="is-danger"
                      onClick={() => void decideResearchPromote(id, false).then(() => refresh())}
                    >
                      Nein
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </aside>
  );
}
