/** Parse agent replies for file edits and apply them into the workspace/IDE. */

export type FileEdit = {
  path: string;
  content: string;
  kind?: "file" | "dir";
  /** Workspace content before apply — keeps Cursor-style chat diffs after auto-write. */
  previousContent?: string;
};

const PATH_OK = /^[A-Za-z0-9_./\\-]+$/;
const FILE_PATHish = /^[A-Za-z0-9_./\\-]+\.[A-Za-z0-9]{1,12}$/;
const HASH_FILE = /^#\s*([A-Za-z0-9_./\\-]+\.[A-Za-z0-9]{1,12})\s*$/;
const JUNK_HASH = /^#\s*(spixa_edit|end_spixa_edit|SPIXA_EDIT|END_SPIXA_EDIT)\s*$/i;

/**
 * Supported forms:
 * 1) ```path/to/file.ext\n...\n```
 * 2) ```lang path/to/file.ext\n...\n```
 * 3) <<<SPIXA_EDIT path/to/file.ext>>> ... <<<END_SPIXA_EDIT>>>
 * 4) # path/to/file.ext\n...content...  (until next # file header)
 */
export function parseAgentEdits(reply: string): FileEdit[] {
  const edits: FileEdit[] = [];
  const blockRe =
    /<<<SPIXA_EDIT\s+([^\s>]+)\s*>>>\r?\n?([\s\S]*?)<<<END_SPIXA_EDIT>>>/gi;
  let m: RegExpExecArray | null;
  while ((m = blockRe.exec(reply)) !== null) {
    pushEdit(edits, m[1], m[2]);
  }

  const fenceRe = /```([^\n`]*)\r?\n([\s\S]*?)```/g;
  while ((m = fenceRe.exec(reply)) !== null) {
    const header = m[1].trim();
    const body = m[2].replace(/\r\n/g, "\n");
    if (!header) continue;
    const parts = header.split(/\s+/);
    let filePath = "";
    let kind: "file" | "dir" = "file";
    if (parts[0] === "dir" && parts[1]) {
      filePath = parts[1].replace(/\/+$/, "");
      kind = "dir";
    } else if (parts.length >= 2 && (parts[1].includes("/") || parts[1].includes("."))) {
      filePath = parts[1];
    } else if (parts[0].includes(".") || parts[0].includes("/")) {
      filePath = parts[0];
    }
    if (!filePath || filePath.length > 240 || !PATH_OK.test(filePath)) continue;
    edits.push({
      path: filePath.replace(/\\/g, "/"),
      content: kind === "dir" ? "" : body,
      kind,
    });
  }

  // Markdown-heading file dumps from small models: # README.md\n...
  parseHashFileSections(reply, edits);

  const map = new Map<string, FileEdit>();
  for (const e of edits) {
    if (!e.content.trim() && e.kind !== "dir") continue;
    map.set(e.path, e);
  }
  return [...map.values()];
}

function normalizeEditPath(pathRaw: string): string | null {
  let filePath = (pathRaw || "").replace(/\\/g, "/").trim();
  // Drop absolute Windows / Unix paths down to a workspace-relative tail when possible.
  if (/^[A-Za-z]:\//.test(filePath) || filePath.startsWith("/")) {
    const parts = filePath.split("/").filter(Boolean);
    const hit = parts.findIndex((p) =>
      /^(repo|src|app|frontend|backend|public|pages|components|styles)$/i.test(p),
    );
    if (hit >= 0) filePath = parts.slice(hit).join("/");
    else filePath = parts[parts.length - 1] || "";
  }
  filePath = filePath.replace(/^\.\//, "");
  if (!filePath || filePath.length > 240 || !PATH_OK.test(filePath)) return null;
  if (/^spixa_edit$/i.test(filePath)) return null;
  if (/^(next|node_modules|Users|Desktop)$/i.test(filePath)) return null;
  return filePath;
}

function pushEdit(edits: FileEdit[], pathRaw: string, body: string, kind: "file" | "dir" = "file") {
  const filePath = normalizeEditPath(pathRaw);
  if (!filePath) return;
  edits.push({
    path: filePath,
    content: kind === "dir" ? "" : body.replace(/\r\n/g, "\n"),
    kind,
  });
}

function parseHashFileSections(reply: string, edits: FileEdit[]) {
  const lines = (reply || "").split(/\r?\n/);
  let currentPath: string | null = null;
  let buf: string[] = [];
  const flush = () => {
    if (currentPath) pushEdit(edits, currentPath, buf.join("\n"));
    currentPath = null;
    buf = [];
  };
  for (const line of lines) {
    if (JUNK_HASH.test(line.trim())) {
      flush();
      continue;
    }
    const hm = line.trim().match(HASH_FILE);
    if (hm && FILE_PATHish.test(hm[1])) {
      flush();
      currentPath = hm[1];
      continue;
    }
    if (currentPath) buf.push(line);
  }
  flush();
}

/** If the model dumped filenames but no real bodies, provide a minimal app scaffold. */
export function ensureBuildEdits(
  reply: string,
  userMessage: string,
  edits: FileEdit[],
): FileEdit[] {
  const solid = edits.filter((e) => (e.content || "").trim().length > 0 || e.kind === "dir");
  if (solid.length) return solid;
  if (
    !looksLikeBuildAsk(userMessage) &&
    !looksLikeContinueAsk(userMessage) &&
    !looksLikeBrokenFileDump(reply)
  ) {
    return edits;
  }
  return minimalAppScaffold(userMessage);
}

export function looksLikeBuildAsk(message: string): boolean {
  const t = (message || "").toLowerCase();
  return /(bau|bauen|build|create|app|anwendung|projekt|موقع|تطبيق|برنامج|أنشئ|ابني|تبني|neues projekt|web\s?app|website)/i.test(
    t,
  );
}

function looksLikeBrokenFileDump(reply: string): boolean {
  const lines = (reply || "").split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  if (lines.length < 3) return false;
  const hashFiles = lines.filter((l) => HASH_FILE.test(l) || JUNK_HASH.test(l));
  return hashFiles.length >= 3 && hashFiles.length / lines.length >= 0.5;
}

export function minimalAppScaffold(userMessage: string): FileEdit[] {
  const lang = detectUserLang(userMessage);
  const title =
    lang === "de" ? "Meine App" : lang === "ar" ? "تطبيقي" : "My App";
  const blurb =
    lang === "de"
      ? "Minimal-App — von Spixa gestartet. Erweitere sie nach Bedarf."
      : lang === "ar"
        ? "تطبيق أولي من Spixa — طوّره حسب حاجتك."
        : "Minimal app scaffolded by Spixa — extend as needed.";
  const readme =
    lang === "de"
      ? `# ${title}\n\n${blurb}\n\n## Start\n\n\`\`\`bash\npython main.py\n\`\`\`\n`
      : lang === "ar"
        ? `# ${title}\n\n${blurb}\n\n## التشغيل\n\n\`\`\`bash\npython main.py\n\`\`\`\n`
        : `# ${title}\n\n${blurb}\n\n## Run\n\n\`\`\`bash\npython main.py\n\`\`\`\n`;
  const main = `"""${title} — starter"""\n\ndef main() -> None:\n    print(${JSON.stringify(blurb)})\n\n\nif __name__ == "__main__":\n    main()\n`;
  const html = `<!doctype html>
<html lang="${lang}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${title}</title>
  <link rel="stylesheet" href="styles.css" />
</head>
<body>
  <main>
    <h1>${title}</h1>
    <p>${blurb}</p>
  </main>
</body>
</html>
`;
  const css = `*{box-sizing:border-box}body{margin:0;font-family:system-ui,sans-serif;background:#0f141c;color:#e8eef8}
main{max-width:42rem;margin:4rem auto;padding:1.5rem}
h1{font-size:1.8rem;margin:0 0 .5rem}
button{margin-top:1rem;padding:.55rem 1rem;border:0;border-radius:8px;background:#3d8bfd;color:#fff;cursor:pointer}
button:focus-visible{outline:2px solid #9ec5ff;outline-offset:2px}
`;
  const js = `document.getElementById("action")?.addEventListener("click", () => {
  const el = document.getElementById("status");
  if (el) el.textContent = ${JSON.stringify(
    lang === "de" ? "Bereit." : lang === "ar" ? "جاهز." : "Ready.",
  )};
});
`;
  const htmlRich = html
    .replace(
      "</main>",
      `    <p id="status"></p>\n    <button type="button" id="action">${
        lang === "de" ? "Start" : lang === "ar" ? "ابدأ" : "Start"
      }</button>\n  </main>`,
    )
    .replace(
      "</body>",
      `  <script src="app.js"></script>\n</body>`,
    );
  return [
    { path: "README.md", content: readme },
    { path: "main.py", content: main },
    { path: "index.html", content: htmlRich },
    { path: "styles.css", content: css },
    { path: "app.js", content: js },
  ];
}

/** User-facing bubble: prose only — code already applied into the editor. */
export function displayAgentReply(reply: string, edits: FileEdit[] = [], userMessage = ""): string {
  let text = reply
    .replace(/<<<SPIXA_EDIT\s+[^\s>]+\s*>>>[\s\S]*?<<<END_SPIXA_EDIT>>>/gi, "")
    .replace(/```[^\n`]*\r?\n[\s\S]*?```/g, "")
    // Leaked absolute / broken SPIXA_EDIT lines (no closing marker)
    .replace(/^.*SPIXA_EDIT.*$/gim, "")
    .replace(/^.*END_SPIXA_EDIT.*$/gim, "")
    .replace(/^[A-Za-z]:\\[^\n]*$/gm, "")
    .replace(/^\/(?:next|Users|home)(?:\/[^\n]*)?$/gim, "")
    .replace(/_?وكلاء شاركوا:[\s\S]*$/u, "")
    .replace(/\b(FullstackDeveloper|IndependentCritic|UIDesigner|MasterOrchestrator|WeakAgent)\b/g, "")
    .replace(/\b(score|تقييم المدير|وكيل ضعيف|وكيل قوي|strong agent|weak agent)\s*[:=]?\s*[\w./-]*/gi, "")
    .replace(/\n*---\n*مقترح بانتظار موافقتك:[\s\S]*$/iu, "")
    .replace(/^.*مقترح بانتظار موافقتك:.*$/gim, "")
    .replace(/^.*الحالة:\s*awaiting_approval.*$/gim, "")
    .replace(/^.*بعد الاعتماد:.*$/gim, "")
    .replace(/^.*فهم الطلب\s*[←→].*$/gim, "")
    .replace(/^.*Never claim code was merged.*$/gim, "")
    .replace(/^.*Never mix this project's memory.*$/gim, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  const leak =
    /^(أنت وكيل|العقل الرئيس|وضع الوكيل|وضع السؤال|وضع التعديل|شجرة المشروع|الطلب يبدو|عدّل فقط|طلب المستخدم|Selected brain|Mode=|Project tree|LANGUAGE \(mandatory\)|=== USER MESSAGE|You are the Spixa|You are Spixa|:Context keys|Context keys|- knowledge:|- roadmap:|- files:|Specialist |Teacher grades|Structure:|Proposal drafted)/i;

  text = text
    .split(/\r?\n/)
    .filter((line) => {
      const s = line.trim();
      if (!s) return true;
      if (leak.test(s)) return false;
      if (HASH_FILE.test(s) || JUNK_HASH.test(s)) return false;
      if (/SPIXA_EDIT|END_SPIXA_EDIT/i.test(s)) return false;
      if (/^[A-Za-z]:\\/.test(s)) return false;
      if (/^\/(?:next|Users|home)(?:\/|$)/i.test(s)) return false;
      if (/^#\s*[A-Za-z0-9_./\\-]+$/.test(s) && s.length < 80) return false;
      if (/^#{1,6}$/.test(s)) return false;
      if (/^(python|javascript|typescript|js|ts|html|css|bash)\s*```?/i.test(s)) return false;
      if (/^#\s*Initialize the workspace/i.test(s)) return false;
      if (/^[-*]\s*(knowledge|roadmap|files)\s*:/i.test(s)) return false;
      if (/awaiting_approval|مقترح بانتظار|بعد الاعتماد|مركز التنفيذ/i.test(s)) return false;
      return true;
    })
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  // Collapse pathological repetition (same short line repeated).
  text = collapseRepeats(text);

  if (!text || looksLikeBrokenFileDump(reply) || looksLikeBrokenModelReply(text, reply)) {
    text = colleaguePlanReply(userMessage, edits);
  }
  return text;
}

export function looksLikeBrokenModelReply(clean: string, raw: string): boolean {
  const c = (clean || "").trim();
  const r = (raw || "").trim();
  if (!c && r) return true;
  if (/^#{1,6}\s*$/m.test(c)) return true;
  if (/^(python|javascript|js|ts|html|css)\s*```/i.test(c)) return true;
  if (/```\s*$/.test(c) && c.length < 40) return true;
  if (/^#\s*Initialize the workspace/i.test(c)) return true;
  if (c.length < 24 && /```|###|SPIXA/i.test(r)) return true;
  return false;
}

export function colleaguePlanReply(userMessage: string, edits: FileEdit[] = []): string {
  const lang = detectUserLang(userMessage);
  const n = edits.length;
  const continueAsk = looksLikeContinueAsk(userMessage);
  const planAsk = looksLikePlanAsk(userMessage);
  if (lang === "de") {
    if (planAsk && !continueAsk) {
      return [
        "Klar — hier ist der Plan:",
        "1) Ist-Zustand der offenen Dateien prüfen",
        "2) Kleine, sichere Verbesserungen umsetzen",
        "3) Kurz testen und README anpassen",
        n ? `Ich setze das jetzt um (${n} Datei(en)).` : "Sag Bescheid, dann starte ich die Umsetzung.",
      ].join("\n");
    }
    return [
      "Klar — wir machen weiter mit der Entwicklung.",
      "Plan:",
      "1) Aktuelle App-Dateien schärfen (UI/Logik)",
      "2) Fehlende Stücke ergänzen",
      "3) Kurz dokumentieren",
      n
        ? `Ich starte jetzt und schreibe ${n} Datei(en).`
        : "Ich starte jetzt mit dem wichtigsten Teil.",
    ].join("\n");
  }
  if (lang === "ar") {
    if (planAsk && !continueAsk) {
      return [
        "حسناً — هذه الخطة:",
        "1) مراجعة الملفات المفتوحة",
        "2) تحسينات صغيرة وآمنة",
        "3) توثيق سريع",
        n ? `أبدأ التنفيذ الآن (${n} ملف).` : "قل لي لأبدأ التنفيذ.",
      ].join("\n");
    }
    return [
      "حسناً — نكمل التطوير.",
      "الخطة:",
      "1) تحسين الواجهة والمنطق",
      "2) إكمال النواقص",
      "3) تحديث التوثيق",
      n ? `أبدأ الآن وأكتب ${n} ملف.` : "أبدأ الآن بأهم جزء.",
    ].join("\n");
  }
  return [
    "Got it — continuing development.",
    "Plan:",
    "1) Tighten current app files",
    "2) Fill gaps",
    "3) Update docs",
    n ? `Starting now — writing ${n} file(s).` : "Starting with the most important part.",
  ].join("\n");
}

export function looksLikeContinueAsk(message: string): boolean {
  return /(weiter|continue|نكمل|كمال|تطوير|entwicklung|keep going|go on|fortsetzen)/i.test(
    message || "",
  );
}

export function looksLikePlanAsk(message: string): boolean {
  return /\b(plan|planung|roadmap|خطة|خطه|خطّة)\b/i.test(message || "");
}

function collapseRepeats(text: string): string {
  const lines = text.split(/\r?\n/);
  const out: string[] = [];
  for (const line of lines) {
    const prev = out[out.length - 1];
    if (prev !== undefined && prev === line && line.trim().length < 60) continue;
    // drop cycling blocks of 2–4 identical short lines
    if (out.length >= 4) {
      const a = out[out.length - 4];
      const b = out[out.length - 3];
      const c = out[out.length - 2];
      const d = out[out.length - 1];
      if (line === a && b === c && line.trim().length < 60) continue;
      if (line === b && a === c && d === a) continue;
    }
    out.push(line);
  }
  return out.join("\n").trim();
}

export function detectUserLang(message: string): "ar" | "de" | "en" {
  const m = message || "";
  if (/[\u0600-\u06FF]/.test(m)) return "ar";
  if (
    /\b(ich|du|die|der|das|und|nicht|bitte|möchte|will|verbessern|projekt|anwendung|bau|bauen|mir|eine|app|für|mit|machen|erstellen|weiter|entwicklung|klar|können|plan|datei)\b/i.test(
      m,
    ) ||
    /[äöüß]/i.test(m)
  ) {
    return "de";
  }
  return "en";
}
