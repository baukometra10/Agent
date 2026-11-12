import { API_URL } from "@/lib/api";

/** Fire-and-forget maturity signals for owned specialties (coding first). */

export async function recordCodingTaskOutcome(success: boolean, source = "ide_ui"): Promise<void> {
  try {
    await fetch(`${API_URL}/system/intelligence/maturity/task-outcome`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ specialty: "coding", success, source }),
    });
  } catch {
    /* ignore */
  }
}

export async function recordCodingHumanAcceptance(
  accepted: boolean,
  note = "",
  actor = "ide-user",
): Promise<void> {
  try {
    await fetch(`${API_URL}/system/intelligence/maturity/human-acceptance`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ specialty: "coding", accepted, note, actor }),
    });
  } catch {
    /* ignore */
  }
}

/** Aggressive online learning after the user applies agent file edits. */
export async function rapidLearnFromIdeApply(input: {
  projectId: string;
  userText: string;
  assistantText?: string;
  files: string[];
  intent?: string;
}): Promise<void> {
  try {
    await fetch(`${API_URL}/system/ownership/handoff/rapid-learn`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: input.projectId,
        user_text: input.userText.slice(0, 4000),
        assistant_text: (input.assistantText || "").slice(0, 8000),
        files: input.files.slice(0, 40),
        intent: input.intent || "implement",
        store_standing: true,
        // Debounced server-side — keep apply path instant
        distill_memory: false,
      }),
    });
  } catch {
    /* ignore */
  }
}

export type OperationKind =
  | "chat_success"
  | "chat_error"
  | "chat_abort"
  | "edits_accepted"
  | "edits_rejected"
  | "edits_failed"
  | "preview_ok"
  | "preview_fail"
  | "build_ok"
  | "build_fail";

/** Fire-and-forget: every agent operation trains Spixa ASAP. */
export async function learnFromOperation(input: {
  kind: OperationKind;
  title?: string;
  detail?: string;
  projectId?: string;
  userText?: string;
  assistantText?: string;
  files?: string[];
  intent?: string;
  humanVerified?: boolean;
}): Promise<void> {
  try {
    await fetch(`${API_URL}/system/ownership/handoff/operation-outcome`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind: input.kind,
        title: (input.title || input.kind).slice(0, 200),
        detail: (input.detail || "").slice(0, 4000),
        project_id: input.projectId || null,
        user_text: (input.userText || "").slice(0, 8000),
        assistant_text: (input.assistantText || "").slice(0, 12000),
        files: (input.files || []).slice(0, 40),
        intent: input.intent || null,
        human_verified: Boolean(input.humanVerified),
      }),
    });
  } catch {
    /* ignore */
  }
}
