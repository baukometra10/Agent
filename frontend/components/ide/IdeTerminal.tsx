"use client";

import { useEffect, useRef, useState } from "react";
import { runWorkspaceCommand } from "@/lib/workspace";

type Line = { kind: "in" | "out" | "err" | "meta"; text: string };

type Props = {
  projectId: string;
  open: boolean;
  onToggle: () => void;
};

export function IdeTerminal({ projectId, open, onToggle }: Props) {
  const [cmd, setCmd] = useState("");
  const [busy, setBusy] = useState(false);
  const [lines, setLines] = useState<Line[]>([
    { kind: "meta", text: "Spixa Terminal — الأوامر تُنفَّذ داخل مجلد المشروع على جهازك." },
  ]);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines, open]);

  useEffect(() => {
    if (open) window.setTimeout(() => inputRef.current?.focus(), 50);
  }, [open]);

  async function run(raw?: string) {
    const command = (raw ?? cmd).trim();
    if (!command || busy || !projectId) return;
    if (command === "clear" || command === "cls") {
      setLines([{ kind: "meta", text: "تم مسح الشاشة." }]);
      setCmd("");
      return;
    }
    setBusy(true);
    setLines((all) => [...all, { kind: "in", text: `$ ${command}` }]);
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
          : `خطأ: ${res.error || "فشل الأمر"} (exit ${res.exit_code ?? "—"})`,
      });
    } else if (!res.ok) {
      next.push({
        kind: "meta",
        text: `exit ${res.exit_code ?? "—"} · ${res.error || "failed"}`,
      });
    }
    setLines((all) => [...all, ...next]);
    setBusy(false);
  }

  if (!open) {
    return (
      <button type="button" className="ide-term-tab" onClick={onToggle}>
        Terminal
      </button>
    );
  }

  return (
    <section className="ide-term" dir="ltr">
      <header className="ide-term__head">
        <strong>TERMINAL</strong>
        <span>{busy ? "running…" : "ready"}</span>
        <div className="ide-term__actions">
          <button type="button" className="ide-term__btn" onClick={() => setLines([])} title="مسح">
            Clear
          </button>
          <button type="button" className="ide-term__btn" onClick={onToggle} title="إخفاء">
            Hide
          </button>
        </div>
      </header>
      <div className="ide-term__body" onClick={() => inputRef.current?.focus()}>
        {lines.map((line, i) => (
          <pre key={`${i}-${line.kind}`} className={`ide-term__line is-${line.kind}`}>
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
            }
          }}
        />
        <button type="button" className="ide-term__run" disabled={busy || !cmd.trim()} onClick={() => void run()}>
          Run
        </button>
      </div>
    </section>
  );
}
