"use client";

import { useEffect, useState, type ReactNode } from "react";
import { CommandDock } from "./CommandDock";
import { IdeTopbarSlotProvider } from "./IdeTopbarSlot";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

const STORAGE_KEY = "evolve.navOpen";

export function AppShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === "1") setOpen(true);
    } catch {
      /* ignore */
    }
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    try {
      localStorage.setItem(STORAGE_KEY, open ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [open, ready]);

  return (
    <IdeTopbarSlotProvider>
      <div className={`app-shell ${open ? "nav-open" : "nav-collapsed"}`}>
        <Sidebar open={open} onClose={() => setOpen(false)} onToggle={() => setOpen((v) => !v)} />
        <div className="app-main">
          <Topbar navOpen={open} onToggleNav={() => setOpen((v) => !v)} />
          <div className="app-content workspace-surface">{children}</div>
        </div>
        <CommandDock />
      </div>
    </IdeTopbarSlotProvider>
  );
}
