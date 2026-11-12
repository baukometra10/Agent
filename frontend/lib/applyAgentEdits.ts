import type { FileEdit } from "@/lib/agentEdits";
import { createWorkspaceEntry, saveWorkspaceFile } from "@/lib/workspace";

/** Shared apply path used by IDE and floating agent dock. */
export async function applyAgentEdits(
  projectId: string,
  edits: FileEdit[],
): Promise<{ ok: boolean; error?: string }> {
  if (!projectId || !edits.length) return { ok: true };
  for (const edit of edits) {
    if (edit.path.endsWith("/")) {
      const res = await createWorkspaceEntry(projectId, edit.path.replace(/\/+$/, ""), "dir");
      if (!res.ok) return res;
      continue;
    }
    const res = await saveWorkspaceFile(projectId, edit.path, edit.content);
    if (!res.ok) return res;
  }
  return { ok: true };
}
