"use client";

import { languageForPath, languageLabel } from "./ideLanguage";
import type { EditorCursorState } from "./CodeEditor";

type Props = {
  path: string | null;
  dirty?: boolean;
  cursor: EditorCursorState;
  wordWrap: boolean;
  onToggleWrap: () => void;
  onFormat?: () => void;
  onRun?: () => void;
  canRun?: boolean;
  problemCount?: number;
  onOpenProblems?: () => void;
  encoding?: string;
  eol?: string;
};

export function IdeStatusBar({
  path,
  dirty,
  cursor,
  wordWrap,
  onToggleWrap,
  onFormat,
  onRun,
  canRun,
  problemCount = 0,
  onOpenProblems,
  encoding = "UTF-8",
  eol = "LF",
}: Props) {
  const lang = path ? languageLabel(languageForPath(path)) : "—";
  const selection = cursor.selected > 0 ? ` · ${cursor.selected} sel` : "";

  return (
    <footer className="ide-statusbar" dir="ltr">
      <div className="ide-statusbar__left">
        <span className={`ide-statusbar__chip ${dirty ? "is-dirty" : ""}`}>
          {dirty ? "● Unsaved" : "Saved"}
        </span>
        <span className="ide-statusbar__chip" title="Cursor">
          Ln {cursor.line}, Col {cursor.column}
          {selection}
        </span>
        <button
          type="button"
          className={`ide-statusbar__btn ${problemCount ? "is-warn" : ""}`}
          onClick={onOpenProblems}
          title="Problems"
        >
          {problemCount ? `⚠ ${problemCount}` : "✓ Problems"}
        </button>
      </div>
      <div className="ide-statusbar__right">
        {onRun ? (
          <button
            type="button"
            className="ide-statusbar__btn is-run"
            disabled={!canRun}
            onClick={onRun}
            title="Run current file (Ctrl+Enter)"
          >
            ▶ Run
          </button>
        ) : null}
        <button type="button" className="ide-statusbar__btn" onClick={onToggleWrap} title="Word wrap">
          Wrap: {wordWrap ? "On" : "Off"}
        </button>
        {onFormat ? (
          <button type="button" className="ide-statusbar__btn" onClick={onFormat} title="Format (Ctrl+Shift+F)">
            Format
          </button>
        ) : null}
        <span className="ide-statusbar__chip">{eol}</span>
        <span className="ide-statusbar__chip">{encoding}</span>
        <span className="ide-statusbar__chip is-lang">{lang}</span>
      </div>
    </footer>
  );
}
