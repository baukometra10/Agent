"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

type IdeTopbarSlotValue = {
  host: HTMLElement | null;
  setHost: (el: HTMLElement | null) => void;
  active: boolean;
  setActive: (on: boolean) => void;
};

const IdeTopbarSlotContext = createContext<IdeTopbarSlotValue | null>(null);

export function IdeTopbarSlotProvider({ children }: { children: ReactNode }) {
  const [host, setHostState] = useState<HTMLElement | null>(null);
  const [active, setActive] = useState(false);
  const setHost = useCallback((el: HTMLElement | null) => {
    setHostState((prev) => (prev === el ? prev : el));
  }, []);
  const value = useMemo(
    () => ({ host, setHost, active, setActive }),
    [host, setHost, active],
  );
  return (
    <IdeTopbarSlotContext.Provider value={value}>{children}</IdeTopbarSlotContext.Provider>
  );
}

function useIdeTopbarSlot() {
  const ctx = useContext(IdeTopbarSlotContext);
  if (!ctx) {
    throw new Error("IdeTopbarSlotProvider missing");
  }
  return ctx;
}

/** Mount point inside the global topbar (empty space beside search). */
export function IdeTopbarHost() {
  const { setHost, active } = useIdeTopbarSlot();
  return (
    <div
      className={`topbar__ide ${active ? "is-active" : ""}`}
      ref={setHost}
      data-ide-slot={active ? "1" : "0"}
    />
  );
}

export function useIdeTopbarHost() {
  return useIdeTopbarSlot().host;
}

/** Marks IDE chrome as active while SpixaIde is mounted. */
export function useIdeTopbarActive(on = true) {
  const { setActive } = useIdeTopbarSlot();
  useEffect(() => {
    setActive(on);
    return () => setActive(false);
  }, [on, setActive]);
}
