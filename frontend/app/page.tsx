"use client";

import { useEffect, useState } from "react";
import { LiveDashboard } from "@/components/dashboard/LiveDashboard";
import { fetchProjects, fetchProposals } from "@/lib/api";
import type { Project, Proposal } from "@/lib/types";

export default function HomePage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const rows = await fetchProjects();
      if (cancelled) return;
      setProjects(rows);
      const props = rows[0] ? await fetchProposals(rows[0].id) : [];
      if (cancelled) return;
      setProposals(props);
      setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!ready) {
    return (
      <div className="route-loading" aria-busy="true">
        <div className="route-loading__bar" />
        <div className="route-loading__stack">
          <div className="route-loading__block is-title" />
          <div className="route-loading__block is-wide" />
        </div>
      </div>
    );
  }

  return <LiveDashboard projects={projects} initialProposals={proposals} />;
}
