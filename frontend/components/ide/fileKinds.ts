export type FileViewKind = "code" | "image" | "pdf" | "audio" | "video" | "binary";

const IMAGE = new Set(["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "ico", "avif"]);
const AUDIO = new Set(["mp3", "wav", "ogg", "m4a", "flac", "aac"]);
const VIDEO = new Set(["mp4", "webm", "mov", "mkv", "avi"]);
const PDF = new Set(["pdf"]);
const BINARY = new Set([
  "zip",
  "gz",
  "tgz",
  "rar",
  "7z",
  "exe",
  "dll",
  "so",
  "dylib",
  "bin",
  "wasm",
  "pyc",
  "pyo",
  "class",
  "o",
  "obj",
  "woff",
  "woff2",
  "ttf",
  "otf",
  "eot",
  "db",
  "sqlite",
  "sqlite3",
]);

export function extOf(path: string): string {
  const base = path.split(/[\\/]/).pop()?.toLowerCase() || "";
  if (!base.includes(".")) return "";
  return base.split(".").pop() || "";
}

export function viewKindForPath(path: string): FileViewKind {
  const ext = extOf(path);
  if (IMAGE.has(ext)) return "image";
  if (PDF.has(ext)) return "pdf";
  if (AUDIO.has(ext)) return "audio";
  if (VIDEO.has(ext)) return "video";
  if (BINARY.has(ext)) return "binary";
  return "code";
}

export function mimeForPath(path: string): string {
  const ext = extOf(path);
  const map: Record<string, string> = {
    png: "image/png",
    jpg: "image/jpeg",
    jpeg: "image/jpeg",
    gif: "image/gif",
    webp: "image/webp",
    svg: "image/svg+xml",
    bmp: "image/bmp",
    ico: "image/x-icon",
    avif: "image/avif",
    pdf: "application/pdf",
    mp3: "audio/mpeg",
    wav: "audio/wav",
    ogg: "audio/ogg",
    m4a: "audio/mp4",
    flac: "audio/flac",
    mp4: "video/mp4",
    webm: "video/webm",
    mov: "video/quicktime",
  };
  return map[ext] || "application/octet-stream";
}

export function formatBytes(n: number): string {
  if (!Number.isFinite(n) || n < 0) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}
