/** Local resume checkpoints after Stop. */

export type ResumeCheckpoint = {
  sessionId: string;
  userMessage: string;
  partialReply: string;
  attachments: string[];
  focusPath?: string | null;
  mode?: string;
  provider?: string;
  stoppedAt: string;
};

function key(projectId: string) {
  return `spixa.ide.resume.${projectId}`;
}

export function readCheckpoints(projectId: string): Record<string, ResumeCheckpoint> {
  try {
    const raw = JSON.parse(localStorage.getItem(key(projectId)) || "{}");
    return raw && typeof raw === "object" ? raw : {};
  } catch {
    return {};
  }
}

export function writeCheckpoint(projectId: string, cp: ResumeCheckpoint) {
  const all = readCheckpoints(projectId);
  all[cp.sessionId] = cp;
  try {
    localStorage.setItem(key(projectId), JSON.stringify(all));
  } catch {
    /* ignore */
  }
}

export function clearCheckpoint(projectId: string, sessionId: string) {
  const all = readCheckpoints(projectId);
  delete all[sessionId];
  try {
    localStorage.setItem(key(projectId), JSON.stringify(all));
  } catch {
    /* ignore */
  }
}

export function getCheckpoint(projectId: string, sessionId: string): ResumeCheckpoint | null {
  return readCheckpoints(projectId)[sessionId] || null;
}
