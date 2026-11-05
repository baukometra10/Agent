/** Persist Spixa IDE chrome layout across reloads. */

export type IdeRightPanel = "agent" | "venture" | null;

export type IdeLayoutState = {
  explorerOpen: boolean;
  terminalOpen: boolean;
  rightPanel: IdeRightPanel;
  explorerW: number;
  dockW: number;
};

export const IDE_LAYOUT_KEY = "spixa.ide.layout";

const DEFAULTS: IdeLayoutState = {
  explorerOpen: true,
  terminalOpen: false,
  rightPanel: null,
  explorerW: 240,
  dockW: 420,
};

function clamp(n: number, min: number, max: number) {
  return Math.min(max, Math.max(min, n));
}

export function loadIdeLayout(): IdeLayoutState {
  try {
    const raw = localStorage.getItem(IDE_LAYOUT_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<IdeLayoutState>;
      const right =
        parsed.rightPanel === "agent" || parsed.rightPanel === "venture" ? parsed.rightPanel : null;
      return {
        explorerOpen: parsed.explorerOpen !== false,
        terminalOpen: Boolean(parsed.terminalOpen),
        rightPanel: right,
        explorerW: clamp(Number(parsed.explorerW) || DEFAULTS.explorerW, 180, 520),
        dockW: clamp(Number(parsed.dockW) || DEFAULTS.dockW, 300, 720),
      };
    }
    // Legacy width keys
    const ew = Number(localStorage.getItem("spixa.ide.explorerW") || "");
    const dw = Number(localStorage.getItem("spixa.ide.dockW") || "");
    return {
      ...DEFAULTS,
      explorerW: ew >= 180 && ew <= 520 ? ew : DEFAULTS.explorerW,
      dockW: dw >= 300 && dw <= 720 ? dw : DEFAULTS.dockW,
    };
  } catch {
    return { ...DEFAULTS };
  }
}

export function saveIdeLayout(partial: Partial<IdeLayoutState>) {
  try {
    const cur = loadIdeLayout();
    const next: IdeLayoutState = {
      explorerOpen: partial.explorerOpen ?? cur.explorerOpen,
      terminalOpen: partial.terminalOpen ?? cur.terminalOpen,
      rightPanel:
        partial.rightPanel === undefined
          ? cur.rightPanel
          : partial.rightPanel === "agent" || partial.rightPanel === "venture"
            ? partial.rightPanel
            : null,
      explorerW: clamp(partial.explorerW ?? cur.explorerW, 180, 520),
      dockW: clamp(partial.dockW ?? cur.dockW, 300, 720),
    };
    localStorage.setItem(IDE_LAYOUT_KEY, JSON.stringify(next));
    localStorage.setItem("spixa.ide.explorerW", String(next.explorerW));
    localStorage.setItem("spixa.ide.dockW", String(next.dockW));
  } catch {
    /* ignore */
  }
}
