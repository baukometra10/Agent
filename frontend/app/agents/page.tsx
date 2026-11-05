"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { API_URL, chiefSaturateDemo, fetchChiefStatus } from "@/lib/api";
import { GlassCard } from "@/components/ui/GlassCard";
import { PageHeader } from "@/components/ui/PageHeader";

type Agent = {
  name: string;
  department: string;
  description: string;
  model_role: string;
  tier: string;
  cursor_role: string;
  can_execute_code: boolean;
};

type Hierarchy = {
  conductor: { name: string; role: string };
  chief?: { name: string; role: string };
  critic: { name: string; role: string };
  intents: { intent: string; label_ar: string; specialists: string[]; include_critic: boolean }[];
};

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [hierarchy, setHierarchy] = useState<Hierarchy | null>(null);
  const [chief, setChief] = useState<Record<string, unknown> | null>(null);
  const [demoOut, setDemoOut] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);

  const reloadChief = useCallback(async () => {
    setChief(await fetchChiefStatus());
  }, []);

  useEffect(() => {
    fetch(`${API_URL}/system/agents`)
      .then((r) => r.json())
      .then((data) => {
        setAgents(data.agents || []);
        setHierarchy(data.hierarchy || null);
      })
      .catch(() => undefined);
    reloadChief();
  }, [reloadChief]);

  const byDept = useMemo(() => {
    const map = new Map<string, Agent[]>();
    for (const a of agents) {
      if (a.tier === "conductor" || a.tier === "critic") continue;
      const list = map.get(a.department) || [];
      list.push(a);
      map.set(a.department, list);
    }
    return [...map.entries()];
  }, [agents]);

  const conductor = agents.find((a) => a.tier === "conductor");
  const critic = agents.find((a) => a.tier === "critic");
  const pool = (chief?.pool || {}) as Record<string, number>;
  const workers = (chief?.workers || []) as Array<Record<string, unknown>>;

  async function onSaturate() {
    setBusy(true);
    setDemoOut(await chiefSaturateDemo(5));
    setBusy(false);
    await reloadChief();
  }

  return (
    <div>
      <PageHeader
        eyebrow="مساحة العمل"
        title="فريق الوكلاء"
        subtitle="Conductor وChief والمتخصصون — هيكل الأوركسترا الحية."
      />

      <div className="agents-hero">
        <GlassCard title="الوكيل الرئيس · ChiefAgent">
          <strong>{hierarchy?.chief?.name || "ChiefAgent"}</strong>
          <p>{hierarchy?.chief?.role || "General lead on owned models"}</p>
          <div className="fleet-kpis" style={{ marginTop: 12 }}>
            <div>
              <span>عمال</span>
              <strong>{pool.total ?? "—"}</strong>
            </div>
            <div>
              <span>خامل</span>
              <strong>{pool.idle ?? "—"}</strong>
            </div>
            <div>
              <span>مشغول</span>
              <strong>{pool.busy ?? "—"}</strong>
            </div>
          </div>
          <button
            type="button"
            className="btn btn-primary"
            style={{ marginTop: 12 }}
            disabled={busy}
            onClick={onSaturate}
          >
            {busy ? "…" : "تجربة: إشباع المجمع (إنشاء عمال)"}
          </button>
        </GlassCard>
        <GlassCard title="مقعد المحادثة">
          <strong>{conductor?.name || hierarchy?.conductor.name || "MasterOrchestrator"}</strong>
          <p>{hierarchy?.conductor.role || conductor?.description}</p>
          <span className="chip">Chat seat</span>
        </GlassCard>
        <GlassCard title="الناقد المستقل">
          <strong>{critic?.name || hierarchy?.critic.name || "IndependentCritic"}</strong>
          <p>{hierarchy?.critic.role || critic?.description}</p>
          <span className="chip">Reviewer</span>
        </GlassCard>
      </div>

      {workers.length > 0 && (
        <GlassCard title="مجمع العمال تحت الرئيس">
          <ul className="agent-list">
            {workers.map((w) => (
              <li key={String(w.id)}>
                <strong>{String(w.name)}</strong>
                <span>
                  {String(w.specialty)} · {String(w.status)}
                  {w.trained ? " · مدرَّب" : " · قيد التدريب"}
                </span>
                <p dir="ltr">
                  tasks={String(w.completed_tasks ?? 0)} · id={String(w.id)}
                </p>
              </li>
            ))}
          </ul>
          {demoOut && (
            <pre
              style={{
                marginTop: 12,
                whiteSpace: "pre-wrap",
                direction: "ltr",
                textAlign: "left",
                fontSize: "0.75rem",
                maxHeight: 200,
                overflow: "auto",
              }}
            >
              {JSON.stringify(
                {
                  spawned_workers: demoOut.spawned_workers,
                  pool: demoOut.pool,
                },
                null,
                2,
              )}
            </pre>
          )}
        </GlassCard>
      )}

      {hierarchy?.intents && (
        <GlassCard title="مسارات التوجيه حسب نية الطلب">
          <div className="intent-grid">
            {hierarchy.intents.map((i) => (
              <article key={i.intent} className="intent-card">
                <strong>{i.label_ar}</strong>
                <span>{i.intent}</span>
                <p>{i.specialists.slice(0, 4).join(" · ")}</p>
                {i.include_critic && <em>يشمل IndependentCritic</em>}
              </article>
            ))}
          </div>
        </GlassCard>
      )}

      <div className="dept-grid">
        {byDept.map(([dept, rows]) => (
          <GlassCard key={dept} title={dept}>
            <ul className="agent-list">
              {rows.map((a) => (
                <li key={a.name}>
                  <strong>{a.name}</strong>
                  <span>
                    {a.model_role}
                    {a.can_execute_code ? " · code" : ""}
                  </span>
                  <p>{a.description}</p>
                </li>
              ))}
            </ul>
          </GlassCard>
        ))}
      </div>
    </div>
  );
}
