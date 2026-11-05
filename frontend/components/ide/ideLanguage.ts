export function languageForPath(path: string): string {
  const base = path.split(/[\\/]/).pop()?.toLowerCase() || "";
  if (base === "dockerfile" || base.startsWith("dockerfile.")) return "dockerfile";
  if (base === "makefile") return "plaintext";
  const ext = base.includes(".") ? base.split(".").pop() || "" : "";
  const map: Record<string, string> = {
    ts: "typescript",
    tsx: "typescript",
    mts: "typescript",
    cts: "typescript",
    js: "javascript",
    jsx: "javascript",
    mjs: "javascript",
    cjs: "javascript",
    py: "python",
    pyi: "python",
    rs: "rust",
    go: "go",
    java: "java",
    json: "json",
    jsonc: "json",
    md: "markdown",
    mdx: "markdown",
    css: "css",
    scss: "scss",
    less: "less",
    html: "html",
    htm: "html",
    yml: "yaml",
    yaml: "yaml",
    toml: "ini",
    ini: "ini",
    sh: "shell",
    bash: "shell",
    zsh: "shell",
    ps1: "powershell",
    sql: "sql",
    xml: "xml",
    svg: "xml",
    c: "c",
    cpp: "cpp",
    cc: "cpp",
    cxx: "cpp",
    h: "c",
    hpp: "cpp",
    cs: "csharp",
    php: "php",
    rb: "ruby",
    kt: "kotlin",
    swift: "swift",
    vue: "html",
    svelte: "html",
  };
  return map[ext] || "plaintext";
}

export function languageLabel(lang: string): string {
  const labels: Record<string, string> = {
    typescript: "TypeScript",
    javascript: "JavaScript",
    python: "Python",
    rust: "Rust",
    go: "Go",
    java: "Java",
    json: "JSON",
    markdown: "Markdown",
    css: "CSS",
    scss: "SCSS",
    html: "HTML",
    yaml: "YAML",
    ini: "TOML/INI",
    shell: "Shell",
    powershell: "PowerShell",
    sql: "SQL",
    xml: "XML",
    c: "C",
    cpp: "C++",
    csharp: "C#",
    php: "PHP",
    ruby: "Ruby",
    kotlin: "Kotlin",
    swift: "Swift",
    dockerfile: "Dockerfile",
    plaintext: "Plain Text",
  };
  return labels[lang] || lang;
}

export function fileBadge(path: string): { label: string; kind: string } {
  const name = path.split(/[\\/]/).pop()?.toLowerCase() || "";
  if (name === "dockerfile" || name.startsWith("dockerfile.")) return { label: "D", kind: "docker" };
  if (name.startsWith(".env")) return { label: "*", kind: "env" };
  if (name === ".gitignore") return { label: "G", kind: "git" };
  const ext = name.includes(".") ? name.split(".").pop() || "" : "";
  const map: Record<string, { label: string; kind: string }> = {
    ts: { label: "TS", kind: "ts" },
    tsx: { label: "TS", kind: "ts" },
    js: { label: "JS", kind: "js" },
    jsx: { label: "JS", kind: "js" },
    py: { label: "PY", kind: "py" },
    rs: { label: "RS", kind: "rs" },
    go: { label: "GO", kind: "go" },
    json: { label: "{}", kind: "json" },
    md: { label: "MD", kind: "md" },
    css: { label: "#", kind: "css" },
    scss: { label: "#", kind: "css" },
    html: { label: "<>", kind: "html" },
    yml: { label: "Y", kind: "yml" },
    yaml: { label: "Y", kind: "yml" },
    toml: { label: "T", kind: "toml" },
    sql: { label: "Q", kind: "sql" },
    sh: { label: ">_", kind: "sh" },
    ps1: { label: ">_", kind: "sh" },
  };
  return map[ext] || { label: "·", kind: "file" };
}
