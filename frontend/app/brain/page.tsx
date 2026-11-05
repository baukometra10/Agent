"use client";

import { useEffect, useState } from "react";
import { AgentWorkspace } from "@/components/brain/AgentWorkspace";
import { fetchProjects } from "@/lib/api";
import type { Project } from "@/lib/types";

export default function BrainPage() {
  const [projects, setProjects] = useState<Project[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchProjects().then((rows) => {
      if (!cancelled) setProjects(rows);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!projects) {
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

  return <AgentWorkspace projects={projects} />;
}
