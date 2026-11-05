"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef } from "react";
import type { editor as MonacoEditor } from "monaco-editor";
import { fetchCompletions } from "@/lib/workspace";
import type { IdeProblem } from "./IdeBottomPanel";
import { languageForPath } from "./ideLanguage";

type Disposable = { dispose: () => void };

const Monaco = dynamic(() => import("@monaco-editor/react"), {
  ssr: false,
  loading: () => (
    <div className="ide-editor ide-editor--loading">
      <div className="ide-editor__spinner" />
      <span>تحميل المحرّر…</span>
    </div>
  ),
});

export type EditorCursorState = {
  line: number;
  column: number;
  selected: number;
};

type Props = {
  path: string;
  value: string;
  onChange: (value: string) => void;
  projectId?: string;
  wordWrap?: boolean;
  fontSize?: number;
  onCursorChange?: (state: EditorCursorState) => void;
  onProblems?: (problems: IdeProblem[]) => void;
  onReady?: (api: { format: () => void; focus: () => void; reveal: (line: number, column?: number) => void }) => void;
};

const SPIXA_THEME = "spixa-dark";

function defineSpixaTheme(monaco: typeof import("monaco-editor")) {
  monaco.editor.defineTheme(SPIXA_THEME, {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "", foreground: "E6EDF7" },
      { token: "comment", foreground: "6E7F96", fontStyle: "italic" },
      { token: "comment.doc", foreground: "7A8FA8", fontStyle: "italic" },
      { token: "string", foreground: "9DD68B" },
      { token: "string.escape", foreground: "E0C07A" },
      { token: "string.invalid", foreground: "FF7B72" },
      { token: "number", foreground: "F0B86A" },
      { token: "number.hex", foreground: "E8C07A" },
      { token: "number.float", foreground: "F0B86A" },
      { token: "regexp", foreground: "7EE0D4" },
      { token: "keyword", foreground: "C792EA" },
      { token: "keyword.control", foreground: "C792EA", fontStyle: "bold" },
      { token: "keyword.operator", foreground: "89DDFF" },
      { token: "keyword.flow", foreground: "FF79C6" },
      { token: "storage", foreground: "C792EA" },
      { token: "storage.type", foreground: "82AAFF" },
      { token: "type", foreground: "4EC9B0" },
      { token: "type.identifier", foreground: "4EC9B0" },
      { token: "class", foreground: "E8C07A" },
      { token: "class.identifier", foreground: "E8C07A" },
      { token: "interface", foreground: "4EC9B0" },
      { token: "enum", foreground: "E8C07A" },
      { token: "struct", foreground: "E8C07A" },
      { token: "function", foreground: "82AAFF" },
      { token: "function.call", foreground: "82B4FF" },
      { token: "method", foreground: "82AAFF" },
      { token: "member", foreground: "9CDCFE" },
      { token: "variable", foreground: "E6EDF7" },
      { token: "variable.name", foreground: "E6EDF7" },
      { token: "variable.predefined", foreground: "FFCB6B" },
      { token: "variable.parameter", foreground: "FFCB6B" },
      { token: "constant", foreground: "F0B86A" },
      { token: "constant.language", foreground: "FF79C6" },
      { token: "constant.numeric", foreground: "F0B86A" },
      { token: "tag", foreground: "F07178" },
      { token: "tag.id", foreground: "82AAFF" },
      { token: "tag.class", foreground: "E8C07A" },
      { token: "attribute.name", foreground: "C792EA" },
      { token: "attribute.value", foreground: "9DD68B" },
      { token: "attribute.value.html", foreground: "9DD68B" },
      { token: "delimiter", foreground: "A9B8CC" },
      { token: "delimiter.bracket", foreground: "FFD580" },
      { token: "delimiter.html", foreground: "A9B8CC" },
      { token: "operator", foreground: "89DDFF" },
      { token: "punctuation", foreground: "A9B8CC" },
      { token: "annotation", foreground: "C792EA" },
      { token: "decorator", foreground: "C792EA" },
      { token: "namespace", foreground: "4EC9B0" },
      { token: "module", foreground: "4EC9B0" },
      { token: "meta.preprocessor", foreground: "C792EA" },
      { token: "meta.embedded", foreground: "E6EDF7" },
      { token: "invalid", foreground: "FF7B72" },
    ],
    colors: {
      "editor.background": "#0A0E16",
      "editor.foreground": "#E6EDF7",
      "editorLineNumber.foreground": "#4A5A72",
      "editorLineNumber.activeForeground": "#D5E0F0",
      "editorCursor.foreground": "#89B4FF",
      "editorCursor.background": "#0A0E16",
      "editor.selectionBackground": "#3D5A99aa",
      "editor.inactiveSelectionBackground": "#2A3F6aaa",
      "editor.selectionHighlightBackground": "#3D5A9944",
      "editor.wordHighlightBackground": "#5A7AB633",
      "editor.wordHighlightStrongBackground": "#5A7AB655",
      "editor.findMatchBackground": "#E8C07A55",
      "editor.findMatchHighlightBackground": "#E8C07A33",
      "editor.lineHighlightBackground": "#121A28",
      "editor.lineHighlightBorder": "#00000000",
      "editorIndentGuide.background1": "#1E2A3C",
      "editorIndentGuide.activeBackground1": "#4A6088",
      "editorBracketHighlight.foreground1": "#FFD580",
      "editorBracketHighlight.foreground2": "#C792EA",
      "editorBracketHighlight.foreground3": "#7EE0D4",
      "editorBracketHighlight.foreground4": "#82AAFF",
      "editorBracketHighlight.foreground5": "#F07178",
      "editorBracketHighlight.foreground6": "#9DD68B",
      "editorWidget.background": "#101826",
      "editorWidget.border": "#2A3A55",
      "editorSuggestWidget.background": "#101826",
      "editorSuggestWidget.border": "#2A3A55",
      "editorSuggestWidget.selectedBackground": "#1E3358",
      "editorSuggestWidget.highlightForeground": "#89B4FF",
      "editorHoverWidget.background": "#101826",
      "editorHoverWidget.border": "#2A3A55",
      "editorGutter.background": "#0A0E16",
      "editorBracketMatch.background": "#2EC4B633",
      "editorBracketMatch.border": "#2EC4B6AA",
      "editorInlayHint.foreground": "#7A8FA8",
      "editorInlayHint.background": "#1A2436",
      "scrollbarSlider.background": "#ffffff14",
      "scrollbarSlider.hoverBackground": "#ffffff24",
      "scrollbarSlider.activeBackground": "#ffffff34",
      "minimap.background": "#0A0E16",
      "minimapSlider.background": "#ffffff10",
      "focusBorder": "#4F7CFF55",
    },
  });
}

function configureLanguages(monaco: typeof import("monaco-editor")) {
  const ts = (monaco.languages as unknown as {
    typescript?: {
      typescriptDefaults: {
        setDiagnosticsOptions: (o: Record<string, unknown>) => void;
        setCompilerOptions: (o: Record<string, unknown>) => void;
      };
      javascriptDefaults: {
        setDiagnosticsOptions: (o: Record<string, unknown>) => void;
      };
      ScriptTarget: { ESNext: number };
      ModuleResolutionKind: { NodeJs: number };
      ModuleKind: { ESNext: number };
      JsxEmit: { ReactJSX: number };
    };
  }).typescript;
  if (!ts) return;
  ts.typescriptDefaults.setDiagnosticsOptions({
    noSemanticValidation: true,
    noSyntaxValidation: false,
  });
  ts.javascriptDefaults.setDiagnosticsOptions({
    noSemanticValidation: true,
    noSyntaxValidation: false,
  });
  ts.typescriptDefaults.setCompilerOptions({
    target: ts.ScriptTarget.ESNext,
    allowNonTsExtensions: true,
    moduleResolution: ts.ModuleResolutionKind.NodeJs,
    module: ts.ModuleKind.ESNext,
    jsx: ts.JsxEmit.ReactJSX,
    allowJs: true,
  });
}

export function CodeEditor({
  path,
  value,
  onChange,
  projectId,
  wordWrap = true,
  fontSize = 15,
  onCursorChange,
  onProblems,
  onReady,
}: Props) {
  const language = useMemo(() => languageForPath(path), [path]);
  const editorRef = useRef<MonacoEditor.IStandaloneCodeEditor | null>(null);
  const disposables = useRef<Disposable[]>([]);
  const projectIdRef = useRef(projectId);
  const pathRef = useRef(path);
  const languageRef = useRef(language);
  const onProblemsRef = useRef(onProblems);
  projectIdRef.current = projectId;
  pathRef.current = path;
  languageRef.current = language;
  onProblemsRef.current = onProblems;
  const modelPath = useMemo(() => `spixa://workspace/${path.replace(/\\/g, "/")}`, [path]);

  useEffect(() => {
    const ed = editorRef.current;
    if (!ed) return;
    ed.updateOptions({
      wordWrap: wordWrap ? "on" : "off",
      fontSize,
    });
  }, [wordWrap, fontSize]);

  useEffect(() => {
    return () => {
      disposables.current.forEach((d) => d.dispose());
      disposables.current = [];
    };
  }, []);

  return (
    <div className="ide-monaco" dir="ltr">
      <Monaco
        height="100%"
        theme={SPIXA_THEME}
        language={language}
        value={value}
        path={modelPath}
        keepCurrentModel
        loading={
          <div className="ide-editor ide-editor--loading">
            <div className="ide-editor__spinner" />
            <span>تحميل المحرّر…</span>
          </div>
        }
        beforeMount={(monaco) => {
          defineSpixaTheme(monaco);
          configureLanguages(monaco);
          monaco.editor.setTheme(SPIXA_THEME);
        }}
        onMount={(editor, monaco) => {
          editorRef.current = editor;
          monaco.editor.setTheme(SPIXA_THEME);
          disposables.current.forEach((d) => d.dispose());
          disposables.current = [];

          const emitCursor = () => {
            const pos = editor.getPosition();
            const sel = editor.getSelection();
            const selected = sel ? Math.abs(editor.getModel()?.getValueLengthInRange(sel) || 0) : 0;
            onCursorChange?.({
              line: pos?.lineNumber || 1,
              column: pos?.column || 1,
              selected,
            });
          };
          emitCursor();
          disposables.current.push(editor.onDidChangeCursorPosition(emitCursor));
          disposables.current.push(editor.onDidChangeCursorSelection(emitCursor));

          const emitProblems = () => {
            const model = editor.getModel();
            if (!model || !onProblemsRef.current) return;
            const markers = monaco.editor.getModelMarkers({ resource: model.uri });
            onProblemsRef.current(
              markers.map((m: {
                startLineNumber: number;
                startColumn: number;
                severity: number;
                message: string;
              }) => ({
                path: pathRef.current,
                line: m.startLineNumber,
                column: m.startColumn,
                severity:
                  m.severity === monaco.MarkerSeverity.Error
                    ? "error"
                    : m.severity === monaco.MarkerSeverity.Warning
                      ? "warning"
                      : "info",
                message: m.message,
              })),
            );
          };
          emitProblems();
          disposables.current.push(monaco.editor.onDidChangeMarkers(() => emitProblems()));

          editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyMod.Shift | monaco.KeyCode.KeyF, () => {
            void editor.getAction("editor.action.formatDocument")?.run();
          });

          const provide = async (model: MonacoEditor.ITextModel, position: { lineNumber: number; column: number }) => {
            const pid = projectIdRef.current;
            if (!pid) return [];
            const offset = model.getOffsetAt(position);
            const full = model.getValue();
            const prefix = full.slice(0, offset);
            const suffix = full.slice(offset);
            try {
              return await fetchCompletions(pid, {
                path: pathRef.current,
                language: languageRef.current,
                prefix,
                suffix,
              });
            } catch {
              return [];
            }
          };

          disposables.current.push(
            monaco.languages.registerCompletionItemProvider(language, {
              triggerCharacters: [".", " ", "(", '"', "'", "/", "-"],
              provideCompletionItems: async (model: MonacoEditor.ITextModel, position: { lineNumber: number; column: number }) => {
                const suggestions = await provide(model, position);
                const word = model.getWordUntilPosition(position);
                const range = {
                  startLineNumber: position.lineNumber,
                  endLineNumber: position.lineNumber,
                  startColumn: word.startColumn,
                  endColumn: word.endColumn,
                };
                return {
                  suggestions: suggestions.map((s, i) => ({
                    label: s.label || s.insertText.slice(0, 40),
                    kind: monaco.languages.CompletionItemKind.Snippet,
                    insertText: s.insertText,
                    range,
                    sortText: String(i).padStart(2, "0"),
                    detail: "Spixa",
                  })),
                };
              },
            }),
          );

          if (typeof monaco.languages.registerInlineCompletionsProvider === "function") {
            disposables.current.push(
              monaco.languages.registerInlineCompletionsProvider(language, {
                provideInlineCompletions: async (
                  model: MonacoEditor.ITextModel,
                  position: { lineNumber: number; column: number },
                ) => {
                  const suggestions = await provide(model, position);
                  return {
                    items: suggestions.slice(0, 3).map((s) => ({
                      insertText: s.insertText,
                      range: {
                        startLineNumber: position.lineNumber,
                        startColumn: position.column,
                        endLineNumber: position.lineNumber,
                        endColumn: position.column,
                      },
                    })),
                  };
                },
                freeInlineCompletions: () => undefined,
              }),
            );
          }

          onReady?.({
            format: () => {
              void editor.getAction("editor.action.formatDocument")?.run();
            },
            focus: () => editor.focus(),
            reveal: (line, column = 1) => {
              editor.revealPositionInCenter({ lineNumber: line, column });
              editor.setPosition({ lineNumber: line, column });
              editor.focus();
            },
          });

          requestAnimationFrame(() => {
            editor.layout();
            editor.focus();
          });
        }}
        onChange={(v) => onChange(v ?? "")}
        options={{
          fontSize,
          fontFamily: "var(--mono), 'Cascadia Code', 'JetBrains Mono', Consolas, 'Courier New', monospace",
          fontLigatures: true,
          lineHeight: 24,
          letterSpacing: 0.35,
          inlineSuggest: { enabled: true },
          minimap: {
            enabled: true,
            scale: 1,
            showSlider: "mouseover",
            renderCharacters: false,
            maxColumn: 100,
          },
          lineNumbers: "on",
          lineNumbersMinChars: 3,
          glyphMargin: true,
          folding: true,
          foldingHighlight: true,
          showFoldingControls: "mouseover",
          wordWrap: wordWrap ? "on" : "off",
          wrappingIndent: "same",
          automaticLayout: true,
          scrollBeyondLastLine: false,
          smoothScrolling: true,
          cursorBlinking: "smooth",
          cursorSmoothCaretAnimation: "on",
          cursorWidth: 2,
          tabSize: 2,
          insertSpaces: true,
          detectIndentation: true,
          renderWhitespace: "selection",
          renderLineHighlight: "all",
          renderLineHighlightOnlyWhenFocus: false,
          padding: { top: 14, bottom: 18 },
          bracketPairColorization: { enabled: true, independentColorPoolPerBracketType: true },
          guides: {
            bracketPairs: true,
            bracketPairsHorizontal: "active",
            indentation: true,
            highlightActiveIndentation: true,
          },
          stickyScroll: { enabled: true, maxLineCount: 4 },
          scrollbar: {
            verticalScrollbarSize: 10,
            horizontalScrollbarSize: 10,
            useShadows: false,
          },
          overviewRulerBorder: false,
          hideCursorInOverviewRuler: true,
          fixedOverflowWidgets: true,
          quickSuggestions: { other: true, comments: false, strings: true },
          suggestOnTriggerCharacters: true,
          acceptSuggestionOnEnter: "on",
          tabCompletion: "on",
          snippetSuggestions: "inline",
          parameterHints: { enabled: true },
          autoClosingBrackets: "languageDefined",
          autoClosingQuotes: "languageDefined",
          autoIndent: "full",
          formatOnPaste: true,
          formatOnType: false,
          linkedEditing: true,
          matchBrackets: "always",
          colorDecorators: true,
          dragAndDrop: true,
          emptySelectionClipboard: true,
          copyWithSyntaxHighlighting: true,
          multiCursorModifier: "alt",
          accessibilitySupport: "auto",
          mouseWheelZoom: true,
          contextmenu: true,
          find: {
            addExtraSpaceOnTop: false,
            autoFindInSelection: "multiline",
            seedSearchStringFromSelection: "selection",
          },
        }}
      />
    </div>
  );
}
