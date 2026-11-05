/**
 * Live speech-to-text for Spixa composer (Cursor-like).
 * Primary: Web Speech API — interim text appears while speaking.
 * Language: auto-detected from spoken script; no manual picker.
 */

export type DetectedSpeech = {
  text: string;
  language?: string | null;
  dir: "rtl" | "ltr";
};

export type SpeechSessionHandlers = {
  /** Partial hypothesis — update the live draft in the input. */
  onInterim?: (text: string) => void;
  /** Committed phrase. */
  onFinal?: (payload: DetectedSpeech) => void;
  onStart?: () => void;
  onEnd?: () => void;
  onError?: (message: string) => void;
  onLanguage?: (code: string, dir: "rtl" | "ltr") => void;
};

export type SpeechSession = {
  start: () => void;
  stop: () => void;
  active: () => boolean;
};

type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((ev: SpeechRecognitionEventLike) => void) | null;
  onerror: ((ev: { error?: string }) => void) | null;
  onend: (() => void) | null;
  onstart: (() => void) | null;
};

type SpeechRecognitionEventLike = {
  resultIndex: number;
  results: {
    length: number;
    [index: number]: { isFinal: boolean; 0: { transcript: string }; length: number };
  };
};

type SpeechWindow = Window & {
  SpeechRecognition?: new () => SpeechRecognitionLike;
  webkitSpeechRecognition?: new () => SpeechRecognitionLike;
};

const ARABIC_RE = /[\u0600-\u06FF]/;
const CYRILLIC_RE = /[\u0400-\u04FF]/;
const CJK_RE = /[\u4E00-\u9FFF]/;
const JP_RE = /[\u3040-\u30FF]/;
const HI_RE = /[\u0900-\u097F]/;

export function dirForLanguage(code?: string | null, sample = ""): "rtl" | "ltr" {
  const c = (code || "").toLowerCase();
  if (c.startsWith("ar") || c.startsWith("fa") || c.startsWith("ur") || c.startsWith("he")) return "rtl";
  if (ARABIC_RE.test(sample)) return "rtl";
  return "ltr";
}

export function detectLangFromText(text: string): string {
  if (ARABIC_RE.test(text)) return "ar";
  if (CYRILLIC_RE.test(text)) return "ru";
  if (JP_RE.test(text)) return "ja";
  if (CJK_RE.test(text)) return "zh";
  if (HI_RE.test(text)) return "hi";
  if (/[A-Za-zÄÖÜäöüß]/.test(text)) {
    // Prefer browser UI language for Latin scripts
    const nav = typeof navigator !== "undefined" ? (navigator.language || "en").split("-")[0] : "en";
    if (["de", "fr", "es", "it", "pt", "tr", "nl", "en"].includes(nav.toLowerCase())) return nav.toLowerCase();
    return "en";
  }
  return "auto";
}

function bcp47(code: string): string {
  const map: Record<string, string> = {
    ar: "ar-SA",
    en: "en-US",
    de: "de-DE",
    fr: "fr-FR",
    es: "es-ES",
    it: "it-IT",
    pt: "pt-BR",
    tr: "tr-TR",
    nl: "nl-NL",
    ru: "ru-RU",
    ja: "ja-JP",
    zh: "zh-CN",
    hi: "hi-IN",
  };
  return map[code] || code;
}

function getSpeechCtor(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === "undefined") return null;
  const w = window as SpeechWindow;
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export function speechSupported(): boolean {
  return Boolean(getSpeechCtor());
}

function initialLang(): string {
  if (typeof navigator === "undefined") return "ar-SA";
  const nav = navigator.language || "";
  // Spixa users often speak Arabic even when OS UI is DE/EN
  if (nav.toLowerCase().startsWith("ar")) return "ar-SA";
  // Start bilingual-friendly: Arabic first for this product, Web Speech will adapt
  return "ar-SA";
}

/**
 * Live Web Speech session with auto language adaptation.
 * Interim results fire continuously while the user speaks.
 */
export function createLiveSpeechSession(handlers: SpeechSessionHandlers): SpeechSession | null {
  const Ctor = getSpeechCtor();
  if (!Ctor) return null;

  let rec: SpeechRecognitionLike | null = null;
  let running = false;
  let stopping = false;
  let currentLang = initialLang();
  let restartLang: string | null = null;
  let startedOnce = false;

  const emitLang = (sample: string) => {
    const detected = detectLangFromText(sample);
    if (detected === "auto") return;
    const dir = dirForLanguage(detected, sample);
    handlers.onLanguage?.(detected, dir);
    const want = bcp47(detected);
    if (want.split("-")[0] !== currentLang.split("-")[0]) {
      // Switch language between phrases (not mid-word) for better accuracy
      restartLang = want;
    }
  };

  const attach = (lang: string) => {
    const next = new Ctor();
    next.lang = lang;
    next.continuous = true;
    next.interimResults = true;
    next.maxAlternatives = 1;
    currentLang = lang;

    next.onstart = () => {
      running = true;
      startedOnce = true;
      handlers.onStart?.();
      handlers.onLanguage?.("auto", dirForLanguage(lang));
    };

    next.onresult = (ev) => {
      let interim = "";
      let finals = "";
      for (let i = ev.resultIndex; i < ev.results.length; i += 1) {
        const row = ev.results[i];
        const piece = (row?.[0]?.transcript || "").trim();
        if (!piece) continue;
        if (row.isFinal) finals += (finals ? " " : "") + piece;
        else interim += (interim ? " " : "") + piece;
      }

      if (interim) {
        emitLang(interim);
        handlers.onInterim?.(interim);
      }
      if (finals) {
        emitLang(finals);
        handlers.onFinal?.({
          text: finals,
          language: detectLangFromText(finals),
          dir: dirForLanguage(detectLangFromText(finals), finals),
        });
        handlers.onInterim?.("");
        if (restartLang) {
          const nextLang = restartLang;
          restartLang = null;
          try {
            next.stop();
            // onend will restart with nextLang
            pendingRestartLang = nextLang;
          } catch {
            /* ignore */
          }
        }
      }
    };

    next.onerror = (ev) => {
      const code = ev.error || "error";
      if (code === "aborted" || code === "no-speech") return;
      if (code === "network") {
        // Chromium sometimes emits network; keep session if possible
        return;
      }
      const map: Record<string, string> = {
        "not-allowed": "اسمح بالوصول للميكروفون من إعدادات المتصفح (Chrome).",
        "service-not-allowed": "خدمة التعرف على الكلام غير متاحة.",
        "audio-capture": "لم يتم العثور على ميكروفون.",
        "language-not-supported": "اللغة غير مدعومة — سيتم التبديل تلقائياً.",
      };
      if (code === "language-not-supported") {
        pendingRestartLang = currentLang.startsWith("ar") ? "en-US" : "ar-SA";
        try {
          next.stop();
        } catch {
          /* ignore */
        }
        return;
      }
      handlers.onError?.(map[code] || `خطأ الميكروفون: ${code}`);
    };

    next.onend = () => {
      running = false;
      if (stopping) {
        handlers.onEnd?.();
        return;
      }
      const lang = pendingRestartLang || currentLang;
      pendingRestartLang = null;
      try {
        attach(lang);
        rec?.start();
      } catch {
        handlers.onEnd?.();
      }
    };

    rec = next;
  };

  let pendingRestartLang: string | null = null;
  attach(currentLang);

  return {
    start: () => {
      stopping = false;
      pendingRestartLang = null;
      try {
        if (!rec) attach(currentLang);
        rec!.start();
        // Some browsers don't fire onstart if already started — force UI
        if (!startedOnce) {
          window.setTimeout(() => {
            if (!running) handlers.onStart?.();
          }, 120);
        }
      } catch (err) {
        // InvalidStateError if already started — ignore
        const msg = err instanceof Error ? err.message : "";
        if (!/already started|InvalidState/i.test(msg)) {
          handlers.onError?.(msg || "تعذّر تشغيل الميكروفون.");
        }
      }
    },
    stop: () => {
      stopping = true;
      pendingRestartLang = null;
      restartLang = null;
      try {
        rec?.stop();
      } catch {
        /* ignore */
      }
      running = false;
      handlers.onInterim?.("");
      handlers.onEnd?.();
    },
    active: () => running,
  };
}

/** Preferred entry — live Web Speech with auto language. */
export async function createAutoSpeechSession(handlers: SpeechSessionHandlers): Promise<SpeechSession | null> {
  return createLiveSpeechSession(handlers);
}
