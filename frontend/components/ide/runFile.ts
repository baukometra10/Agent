/** Build a sensible run command for a workspace-relative file path. */

export function runCommandForPath(path: string): string | null {
  const clean = path.replace(/\\/g, "/");
  const name = clean.split("/").pop()?.toLowerCase() || "";
  const ext = name.includes(".") ? name.split(".").pop() || "" : "";

  if (ext === "py") return `python "${clean}"`;
  if (ext === "js") return `node "${clean}"`;
  if (ext === "mjs") return `node "${clean}"`;
  if (ext === "ts") return `npx --yes tsx "${clean}"`;
  if (ext === "tsx") return `npx --yes tsx "${clean}"`;
  if (ext === "go") return `go run "${clean}"`;
  if (ext === "rs") return `cargo run`;
  if (ext === "ps1") return `powershell -ExecutionPolicy Bypass -File "${clean}"`;
  if (ext === "sh" || ext === "bash") return `bash "${clean}"`;
  if (ext === "bat" || ext === "cmd") return `"${clean}"`;
  if (name === "package.json") return "npm test";
  if (name === "pytest.ini" || name === "pyproject.toml") return "pytest -q";
  if (name === "dockerfile" || name.startsWith("dockerfile.")) return "docker build -t spixa-local .";
  return null;
}
