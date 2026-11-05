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
        distill_memory: true,
      }),
    });
  } catch {
    /* ignore */
  }
}
