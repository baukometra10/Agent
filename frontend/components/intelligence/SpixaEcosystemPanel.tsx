"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { GlassCard } from "@/components/ui/GlassCard";

type FamilyRow = {
  product?: string;
  specialty?: string;
  priority_ar?: string;
  role_ar?: string;
  ready?: boolean;
};

type RoadmapRow = {
  id?: string;
  name_ar?: string;
  name?: string;
  weeks?: string;
  status?: string;
};

export function SpixaEcosystemPanel() {
  const [bp, setBp] = useState<Record<string, unknown> | null>(null);

  const reload = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/system/intelligence/ecosystem`, { cache: "no-store" });
      if (res.ok) setBp(await res.json());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const family = (bp?.family || []) as FamilyRow[];
  const roadmap = (bp?.roadmap || []) as RoadmapRow[];
  const priorities = (bp?.priorities_ar || []) as string[];
  const nonGoal = (bp?.non_goal || {}) as { note_ar?: string };

  return (
    <div id="spixa-ecosystem" className="page-grid" style={{ gap: "1rem" }}>
      <GlassCard title="منظومة ذكاء Spixa المملوكة">
        <p style={{ marginTop: 0, color: "var(--muted)" }}>
          {(bp?.company_doctrine_ar as string) ||
            (bp?.ecosystem_ar as string) ||
            "Spixa Proprietary Intelligence Ecosystem"}
        </p>
        <ul className="rapid-layers">
          {priorities.map((p) => (
            <li key={p}>
              <strong>{p}</strong>
            </li>
          ))}
        </ul>
        <p style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
          المرحلة القادمة: {((bp?.next_chapter_ar as string[]) || []).join(" · ")}
        </p>
        <p style={{ color: "var(--muted)", fontSize: "0.85rem" }}>{nonGoal.note_ar}</p>
      </GlassCard>

      <GlassCard title="عائلة النماذج الستة">
        <ul className="rapid-layers">
          {family.map((f) => (
            <li key={String(f.specialty)}>
              <strong>
                {f.product}{" "}
                <span style={{ color: "var(--muted)", fontWeight: 400 }}>
                  ({f.specialty}) · {f.ready ? "جاهز" : "قيد التملك"}
                </span>
              </strong>
              <span>
                {f.role_ar} — أولوية: {f.priority_ar}
              </span>
            </li>
          ))}
        </ul>
      </GlassCard>

      <GlassCard title="خارطة طريق الذكاء (فوق المنصة)">
        <ol className="rapid-layers">
          {roadmap.map((r) => (
            <li key={String(r.id)}>
              <strong>
                {r.id}. {r.name_ar || r.name}
              </strong>
              <span>
                {r.weeks} · {r.status}
              </span>
            </li>
          ))}
        </ol>
      </GlassCard>
    </div>
  );
}
