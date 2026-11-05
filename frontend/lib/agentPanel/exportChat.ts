export type ExportMsg = {
  role: "user" | "assistant";
  text: string;
  agent?: string | null;
  model?: string | null;
  edits?: { path: string }[];
};

export function buildChatMarkdown(opts: {
  title: string;
  projectId: string;
  sessionId: string;
  messages: ExportMsg[];
}): string {
  const when = new Date().toISOString();
  const lines: string[] = [
    `# ${opts.title || "Agent chat"}`,
    "",
    `- Project: \`${opts.projectId}\``,
    `- Session: \`${opts.sessionId}\``,
    `- Exported: ${when}`,
    "",
    "---",
    "",
  ];
  for (const m of opts.messages) {
    const who = m.role === "user" ? "You" : m.agent || "Spixa";
    lines.push(`## ${who}`);
    if (m.model) lines.push(`*model: ${m.model}*`, "");
    lines.push((m.text || "").trim() || "_(empty)_", "");
    if (m.edits?.length) {
      lines.push("**Files:**");
      for (const e of m.edits) lines.push(`- \`${e.path}\``);
      lines.push("");
    }
  }
  return lines.join("\n");
}

export function downloadText(filename: string, content: string, mime = "text/markdown;charset=utf-8") {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function openPrintableHtml(opts: {
  title: string;
  markdownBody: string;
}) {
  const escaped = opts.markdownBody
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  const html = `<!doctype html><html lang="ar" dir="auto"><head><meta charset="utf-8"/><title>${opts.title}</title>
<style>
body{font:14px/1.55 system-ui,Segoe UI,sans-serif;max-width:820px;margin:2rem auto;padding:0 1rem;color:#111}
pre{white-space:pre-wrap;background:#f4f6f8;padding:1rem;border-radius:8px}
h1{font-size:1.4rem} @media print{body{margin:0}}
</style></head><body>
<h1>${opts.title}</h1>
<pre>${escaped}</pre>
<script>window.onload=()=>setTimeout(()=>window.print(),250)</script>
</body></html>`;
  const w = window.open("", "_blank");
  if (!w) return false;
  w.document.write(html);
  w.document.close();
  return true;
}
