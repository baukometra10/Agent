"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { runWorkspaceCommand } from "@/lib/workspace";

export type IdeProblem = {
  path: string;
  line: number;
  column: number;
  severity: "error" | "warning" | "info";
  message: string;
};

export type IdeBottomPanelHandle = {
  run: (command: string) => Promise<void>;
  focusTerminal: () => void;
  appendOutput: (text: string, kind?: "out" | "err" | "meta") => void;
  showTab: (tab: PanelTab) => void;
};

type PanelTab = "terminal" | "problems" | "output";
type Line = { kind: "in" | "out" | "err" | "meta"; text: string };

type Props = {
  projectId: string;
  open: boolean;
  onToggle: () => void;
  problems: IdeProblem[];
  onOpenProblem?: (problem: IdeProblem) => void;
  activePath?: string | null;
};

export const IdeBottomPanel = forwardRef<IdeBottomPanelHandle, Props>(function IdeBottomPanel(
  { projectId, open, onToggle, problems, onOpenProblem, activePath },
  ref,
) {
  const [tab, setTab] = useState<PanelTab>("terminal");
  const [cmd, setCmd] = useState("");
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<string[]>([]);
  const [histIdx, setHistIdx] = useState(-1);
  const [panelH, setPanelH] = useState(240);
  const panelHRef = useRef(panelH);
  panelHRef.current = panelH;
  const dragRef = useRef<{ startY: number; startH: number } | null>(null);
  const [termLines, setTermLines] = useState<Line[]>([
    {
      kind: "meta",
      text: "Spixa Terminal — Befehle laufen im Projektordner. ↑/↓ Verlauf · clear zum Leeren.",
    },
  ]);
  const [outputLines, setOutputLines] = useState<Line[]>([
    { kind: "meta", text: "Output — Run-Ergebnisse und Agent-Logs erscheinen hier." },
  ]);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    try {
      const h = Number(localStorage.getItem("spixa.ide.bottomH") || "");
      if (h >= 140 && h <= 560) setPanelH(h);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    function onMove(ev: PointerEvent) {
      const drag = dragRef.current;
      if (!drag) return;
      const dy = drag.startY - ev.clientY;
      const next = Math.min(560, Math.max(140, drag.startH + dy));
      setPanelH(next);
    }
    function onUp() {
      if (!dragRef.current) return;
      dragRef.current = null;
      document.body.classList.remove("ide-resizing-y");
      try {
        localStorage.setItem("spixa.ide.bottomH", String(panelHRef.current));
      } catch {
        /* ignore */
      }
    }
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [termLines, outputLines, tab, open]);

  useEffect(() => {
    if (open && tab === "terminal") window.setTimeout(() => inputRef.current?.focus(), 40);
  }, [open, tab]);

  function beginResize(e: ReactPointerEvent) {
    e.preventDefault();
    dragRef.current = { startY: e.clientY, startH: panelHRef.current };
    document.body.classList.add("ide-resizing-y");
  }

  const appendOutput = useCallback((text: string, kind: "out" | "err" | "meta" = "out") => {
    setOutputLines((all) => [...all, { kind, text }]);
    setTab("output");
  }, []);

  const run = useCallback(
    async (raw?: string) => {
      const command = (raw ?? cmd).trim();
      if (!command || busy || !projectId) return;
      if (command === "clear" || command === "cls") {
        setTermLines([{ kind: "meta", text: "Terminal geleert." }]);
        setCmd("");
        return;
      }
      setBusy(true);
      setTab("terminal");
      setHistory((h) => {
        const next = [command, ...h.filter((x) => x !== command)].slice(0, 40);
        return next;
      });
      setHistIdx(-1);
      setTermLines((all) => [...all, { kind: "in", text: `$ ${command}` }]);
      setCmd("");
      const res = await runWorkspaceCommand(projectId, command);
      const next: Line[] = [];
      if (res.stdout) next.push({ kind: "out", text: res.stdout.replace(/\s+$/, "") });
      if (res.stderr) next.push({ kind: "err", text: res.stderr.replace(/\s+$/, "") });
      if (!res.stdout && !res.stderr) {
        next.push({
          kind: "meta",
          text: res.ok
            ? `(exit ${res.exit_code ?? 0})`
            : `Fehler: ${res.error || "fehlgeschlagen"} (exit ${res.exit_code ?? "—"})`,
        });
      } else if (!res.ok) {
        next.push({
          kind: "meta",
          text: `exit ${res.exit_code ?? "—"} · ${res.error || "failed"}`,
        });
      }
      setTermLines((all) => [...all, ...next]);
      setOutputLines((all) => [
        ...all,
        { kind: "in", text: `$ ${command}` },
        ...next,
      ]);
      setBusy(false);
    },
    [busy, cmd, projectId],
  );

  useImperativeHandle(
    ref,
    () => ({
      run: (command: string) => run(command),
      focusTerminal: () => {
        setTab("terminal");
        window.setTimeout(() => inputRef.current?.focus(), 40);
      },
      appendOutput,
      showTab: (t) => setTab(t),
    }),
    [appendOutput, run],
  );

  const errorCount = problems.filter((p) => p.severity === "error").length;
  const warnCount = problems.filter((p) => p.severity === "warning").length;

  if (!open) {
    return (
      <div className="ide-bottom-collapsed">
        <button type="button" className="ide-term-tab" onClick={onToggle}>
          Panel
        </button>
        <button type="button" className="ide-term-tab" onClick={() => { onToggle(); setTab("terminal"); }}>
          Terminal
        </button>
        <button type="button" className="ide-term-tab" onClick={() => { onToggle(); setTab("problems"); }}>
          Problems{problems.length ? ` (${problems.length})` : ""}
        </button>
      </div>
    );
  }

  return (
    <section className="ide-bottom" dir="ltr" style={{ height: `${panelH}px` }}>
      <div
        className="ide-sash ide-sash--bottom"
        role="separator"
        aria-orientation="horizontal"
        aria-label="تغيير ارتفاع اللوحة"
        onPointerDown={beginResize}
      />
      <header className="ide-bottom__head">
        <nav className="ide-bottom__tabs">
          <button
            type="button"
            className={tab === "terminal" ? "is-active" : ""}
            onClick={() => setTab("terminal")}
          >
            Terminal
          </button>
          <button
            type="button"
            className={tab === "problems" ? "is-active" : ""}
            onClick={() => setTab("problems")}
          >
            Problems
            {problems.length ? <i>{problems.length}</i> : null}
          </button>
          <button
            type="button"
            className={tab === "output" ? "is-active" : ""}
            onClick={() => setTab("output")}
          >
            Output
          </button>
        </nav>
        <div className="ide-bottom__meta">
          <span>{busy ? "running…" : "ready"}</span>
          {activePath ? <em title={activePath}>{activePath.split("/").pop()}</em> : null}
          <button type="button" className="ide-term__btn" onClick={onToggle}>
            Hide
          </button>
        </div>
      </header>

      {tab === "terminal" ? (
        <>
          <div className="ide-term__body" onClick={() => inputRef.current?.focus()}>
            {termLines.map((line, i) => (
              <pre key={`t-${i}`} className={`ide-term__line is-${line.kind}`}>
                {line.text}
              </pre>
            ))}
            <div ref={endRef} />
          </div>
          <div className="ide-term__prompt">
            <span>$</span>
            <input
              ref={inputRef}
              value={cmd}
              disabled={busy || !projectId}
              placeholder="python main.py · npm test · pytest · dir"
              onChange={(e) => setCmd(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  void run();
                } else if (e.key === "ArrowUp") {
                  e.preventDefault();
                  if (!history.length) return;
                  const next = Math.min(histIdx + 1, history.length - 1);
                  setHistIdx(next);
                  setCmd(history[next] || "");
                } else if (e.key === "ArrowDown") {
                  e.preventDefault();
                  if (histIdx <= 0) {
                    setHistIdx(-1);
                    setCmd("");
                    return;
                  }
                  const next = histIdx - 1;
                  setHistIdx(next);
                  setCmd(history[next] || "");
                }
              }}
            />
            <button
              type="button"
              className="ide-term__run"
              disabled={busy || !cmd.trim()}
              onClick={() => void run()}
            >
              Run
            </button>
          </div>
        </>
      ) : null}

      {tab === "problems" ? (
        <div className="ide-problems">
          {!problems.length ? (
            <p className="ide-problems__empty">Keine Probleme — Syntax-Hinweise erscheinen beim Tippen.</p>
          ) : (
            <ul>
              {problems.map((p, i) => (
                <li key={`${p.path}-${p.line}-${i}`}>
                  <button type="button" onClick={() => onOpenProblem?.(p)}>
                    <span className={`ide-problems__sev is-${p.severity}`}>{p.severity[0].toUpperCase()}</span>
                    <span className="ide-problems__msg">{p.message}</span>
                    <span className="ide-problems__loc" dir="ltr">
                      {p.path}:{p.line}:{p.column}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <footer className="ide-problems__foot">
            {errorCount} errors · {warnCount} warnings
          </footer>
        </div>
      ) : null}

      {tab === "output" ? (
        <div className="ide-term__body">
          {outputLines.map((line, i) => (
            <pre key={`o-${i}`} className={`ide-term__line is-${line.kind}`}>
              {line.text}
            </pre>
          ))}
          <div className="ide-bottom__output-actions">
            <button type="button" className="ide-term__btn" onClick={() => setOutputLines([])}>
              Clear Output
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
});
