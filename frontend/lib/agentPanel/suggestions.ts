/** Contextual quick prompts for the agent composer. */

export type Suggestion = {
  id: string;
  label: string;
  prompt: string;
};

type Ctx = {
  activePath?: string | null;
  attachments?: string[];
  hasMessages?: boolean;
  lastAssistant?: string;
  mode?: "agent" | "ask" | "edit";
  lang?: "ar" | "de" | "en";
};

function extOf(path: string | null | undefined): string {
  if (!path) return "";
  const base = path.split(/[\\/]/).pop() || "";
  const i = base.lastIndexOf(".");
  return i >= 0 ? base.slice(i + 1).toLowerCase() : "";
}

const L = {
  ar: {
    plan: "خطّة تنفيذ",
    planPrompt: "ضع خطة تنفيذ مختصرة وواضحة للخطوة التالية، ثم ابدأ بأهم جزء فوراً.",
    explain: "شرح الملف",
    explainPrompt: (f: string) => `اشرح ملف ${f} باختصار: مسؤوليته، أهم الدوال، والمخاطر.`,
    improve: "حسّن الملف",
    improvePrompt: (f: string) =>
      `راجع ${f} وحسّنه بأقل تغيير صحيح (وضوح، أخطاء، أداء). طبّق التعديل في الملف.`,
    tests: "اختبارات",
    testsPrompt: (f: string | null) =>
      f
        ? `اكتب اختبارات مناسبة لـ ${f} وضعها في المسار الصحيح للمشروع.`
        : "أضف اختبارات للجزء الأهم من الكود المفتوح.",
    a11y: "إتاحة",
    a11yPrompt: (f: string) =>
      `حسّن إتاحة ووضوح واجهة ${f} دون تغيير الهوية البصرية جذرياً.`,
    fix: "أصلح الخطأ",
    fixPrompt: "حلّل آخر خطأ في المحادثة وأصلحه في الملفات المعنية مع تفسير قصير.",
    why: "لماذا هكذا؟",
    whyPrompt: "اشرح القرار التصميمي الأخير ولماذا هو الأنسب لهذا المشروع.",
    readme: "README",
    readmePrompt: "حدّث أو أنشئ README موجزاً يعكس حالة المشروع الحالية وطريقة التشغيل.",
  },
  de: {
    plan: "Plan",
    planPrompt:
      "Erstelle einen kurzen klaren Umsetzungsplan für den nächsten Schritt und starte sofort mit dem wichtigsten Teil.",
    explain: "Datei erklären",
    explainPrompt: (f: string) =>
      `Erkläre ${f} kurz: Verantwortung, wichtigste Funktionen, Risiken.`,
    improve: "Datei verbessern",
    improvePrompt: (f: string) =>
      `Prüfe ${f} und verbessere sie mit der kleinsten korrekten Änderung. Schreibe die Datei direkt.`,
    tests: "Tests",
    testsPrompt: (f: string | null) =>
      f
        ? `Schreibe passende Tests für ${f} und lege sie im richtigen Pfad ab.`
        : "Füge Tests für den wichtigsten offenen Code hinzu.",
    a11y: "Barrierefreiheit",
    a11yPrompt: (f: string) =>
      `Verbessere Barrierefreiheit und Klarheit von ${f}, ohne die visuelle Identität stark zu ändern.`,
    fix: "Fehler beheben",
    fixPrompt: "Analysiere den letzten Fehler im Chat und behebe ihn in den betroffenen Dateien.",
    why: "Warum so?",
    whyPrompt: "Erkläre die letzte Design-Entscheidung und warum sie hier passt.",
    readme: "README",
    readmePrompt:
      "Aktualisiere oder erstelle eine kurze README mit Status und Startanleitung.",
  },
  en: {
    plan: "Plan",
    planPrompt: "Write a short clear plan for the next step, then start the most important part now.",
    explain: "Explain file",
    explainPrompt: (f: string) => `Explain ${f} briefly: responsibility, key functions, risks.`,
    improve: "Improve file",
    improvePrompt: (f: string) =>
      `Review ${f} and improve it with the smallest correct change. Write the file directly.`,
    tests: "Tests",
    testsPrompt: (f: string | null) =>
      f ? `Write suitable tests for ${f} in the right project path.` : "Add tests for the most important open code.",
    a11y: "A11y",
    a11yPrompt: (f: string) =>
      `Improve accessibility and clarity of ${f} without drastically changing the visual identity.`,
    fix: "Fix error",
    fixPrompt: "Analyze the last chat error and fix it in the affected files with a short note.",
    why: "Why this?",
    whyPrompt: "Explain the latest design decision and why it fits this project.",
    readme: "README",
    readmePrompt: "Update or create a short README reflecting current status and how to run.",
  },
} as const;

export function buildSuggestions(ctx: Ctx): Suggestion[] {
  const lang = ctx.lang || "ar";
  const t = L[lang] || L.en;
  const path = ctx.activePath || ctx.attachments?.[0] || null;
  const ext = extOf(path);
  const file = path ? path.split(/[\\/]/).pop() || null : null;
  const out: Suggestion[] = [];

  if (!ctx.hasMessages) {
    out.push({ id: "plan", label: t.plan, prompt: t.planPrompt });
  }

  if (file) {
    out.push({ id: "explain", label: t.explain, prompt: t.explainPrompt(file) });
    out.push({ id: "improve", label: t.improve, prompt: t.improvePrompt(file) });
  }

  if (["ts", "tsx", "js", "jsx", "py", "go", "rs"].includes(ext)) {
    out.push({ id: "tests", label: t.tests, prompt: t.testsPrompt(file) });
  }

  if (["tsx", "jsx", "css", "scss", "html"].includes(ext)) {
    out.push({
      id: "a11y",
      label: t.a11y,
      prompt: t.a11yPrompt(file || (lang === "de" ? "der aktuellen UI" : "current UI")),
    });
  }

  const last = (ctx.lastAssistant || "").toLowerCase();
  if (/خطأ|error|fail|تعذّر|exception|traceback|fehler/.test(last)) {
    out.push({ id: "fix", label: t.fix, prompt: t.fixPrompt });
  }

  if (ctx.mode === "ask") {
    out.push({ id: "why", label: t.why, prompt: t.whyPrompt });
  } else {
    out.push({ id: "readme", label: t.readme, prompt: t.readmePrompt });
  }

  const seen = new Set<string>();
  return out.filter((s) => (seen.has(s.id) ? false : (seen.add(s.id), true))).slice(0, 6);
}
